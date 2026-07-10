# Design: Jasper's 3 router requests (2026-07-10)

> **Status: Implemented (2026-07-10).** See `Team Documentation/2026-07-10-router-fixes-plan.md` for the executed implementation plan and `Team Documentation/julianna_docu.md`'s 2026-07-10 session entry for the full writeup.

Jasper (router/policy owner) requested three changes. This spec covers all three;
implementation will follow in a separate plan.

## 1. Interactive prompt loop (dev tool only)

**Why:** `eval_harness.py` currently only runs a hardcoded `DEFAULT_TASKS` list (or a
`--tasks` JSON file). Jasper wants to type prompts ad hoc during development instead of
editing that list every time.

**Not in main.py.** `main.py` has a fixed I/O contract required by the grading harness
(read `/input/tasks.json`, write `/output/results.json`, exit 0/non-zero) — making it
interactive would break submission scoring. This loop is a dev-only addition to
`eval_harness.py`.

**Design:** add an `--interactive` flag to `eval_harness.py`. When set:

```python
router = Policy()
results = []
while True:
    prompt = input("What's on your mind right now?: ").strip()
    if not prompt or prompt.lower() in ("quit", "exit"):
        break
    r = router.route(prompt)
    # reuse the existing per-task print block (answer/model/conf/tokens/error)
    results.append({...})  # same shape eval_harness already builds
print_summary(results)
```

One `Policy()` instance persists for the whole interactive session — this also gives
feature 3's running token budget somewhere to live across multiple typed prompts.
`smoke_test.py` is unchanged (stays a single hardcoded sanity check).

## 2. Task classification → per-category remote model routing

**Why:** Jasper wants escalation to call whichever of the 5 allowed Fireworks models is
best suited to the task's category, and wants logs/output to show the actual model name
used instead of the generic string `"remote"`.

**Caveat (documented, not solved by this spec):** none of the 5 allowed models
(`minimax-m3`, `kimi-k2p7-code`, `gemma-4-31b-it`, `gemma-4-26b-a4b-it`,
`gemma-4-31b-it-nvfp4`) are benchmarked anywhere in this repo for "best at X." The
mapping below is a heuristic starting point (mostly from model naming), explicitly meant
to be retuned once the team has real accuracy data per category.

**New module** `src/router/classifier.py` (sibling to `complexity.py`, same
keyword-scoring style):

```python
CATEGORY_KEYWORDS = {
    "code":       ["code", "function", "debug", "bug", "compile", "syntax",
                    "algorithm", "python", "javascript", "class ", "def ", "error:"],
    "math":       ["calculate", "compute", "solve", "equation", "sum of",
                    "how many", "how much", r"\d+\s*[\+\-\*/]\s*\d+"],
    "reasoning":  ["why", "explain", "prove", "infer", "logic", "if and only if",
                    "therefore", "cause", "premise"],
    "creative":   ["write a", "poem", "story", "imagine", "compose", "creative"],
    "factual_qa": ["what is", "who is", "when did", "where is", "capital of", "define"],
}

def classify_task(prompt: str) -> str:
    """Returns the highest-scoring category name, or "general" if nothing matches."""
```

**New config** (`config/settings.py`), heuristic and clearly commented as a guess:

```python
CATEGORY_MODEL_MAP = {
    "code":       "kimi-k2p7-code",       # only code-named model in the allowed list
    "math":       "minimax-m3",
    "reasoning":  "minimax-m3",
    "creative":   "gemma-4-31b-it",
    "factual_qa": "gemma-4-26b-a4b-it",   # smaller active-param MoE, cheaper for lookups
    "general":    REMOTE_MODEL_NAME,       # existing default/fallback
}
```

**`policy.py` change:** at the existing `self.remote_client.generate(task)` call site:

```python
category = classify_task(task)
model_name = CATEGORY_MODEL_MAP.get(category, REMOTE_MODEL_NAME)
if model_name not in ALLOWED_MODELS:      # heuristic map could point at something not
    model_name = REMOTE_MODEL_NAME        # on this run's actual allowed list
remote_result = self.remote_client.generate(task, model_name=model_name)
```

`result["model_used"]` becomes the actual model name (e.g. `"kimi-k2p7-code"`) on
escalation instead of the literal string `"remote"`. Local path keeps `model_used ==
"local"` (showing the raw Ollama tag instead is a separate concern, not one of the three
asks). `log_decision` and `eval_harness.py` already just print whatever's in
`model_used`; `eval_harness.py`'s summary local/remote counts change from a hardcoded
`== "remote"` check to grouping by actual distinct values.

## 3. Token-budget fallback to local

**Why:** Jasper wants remote calls that would "exceed the required tokens" to route to
local instead. Fireworks doesn't expose completion-token cost before a call completes —
only prompt length is knowable upfront — so this is necessarily an estimate-based guard,
not an exact one.

**Scope (per user decision): both a per-task cap and a running batch-wide budget.**

**New settings** (`config/settings.py`):

```python
MAX_TASK_PROMPT_TOKENS_ESTIMATE = int(os.getenv("MAX_TASK_PROMPT_TOKENS_ESTIMATE", 2000))
MAX_REMOTE_TOKENS_BUDGET = int(os.getenv("MAX_REMOTE_TOKENS_BUDGET", 0))  # 0 = unlimited
```

Both default to effectively inert (2000 is generous; 0 disables the global cap) so no
one is forced into a behavior change until they set these env vars deliberately.

**New helper** `src/router/budget.py`:

```python
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)  # chars/4 heuristic -- no tokenizer dep in
                                     # requirements.txt, and Fireworks' 5 allowed models
                                     # don't share one tokenizer anyway
```

**`policy.py` change:** `Policy.__init__` gains `self.remote_tokens_spent = 0` — since
`main.py` constructs one `Policy()` per run over the whole `tasks.json` batch, this
instance attribute naturally IS the "global running budget across the batch." Right
after computing `category`/`model_name` (and before calling remote):

```python
estimated = estimate_tokens(task)
over_task_cap = estimated > MAX_TASK_PROMPT_TOKENS_ESTIMATE
over_budget = (MAX_REMOTE_TOKENS_BUDGET > 0
               and self.remote_tokens_spent + estimated > MAX_REMOTE_TOKENS_BUDGET)

if over_task_cap or over_budget:
    log_decision(task_id=task_id, model_used="local", tokens_used=0,
                 confidence=confidence, escalated=False, answer=local_answer,
                 error=f"remote skipped: {'task cap' if over_task_cap else 'budget'} exceeded")
    return {"answer": local_answer, "model_used": "local", "confidence": confidence,
            "tokens_used": 0, "escalated": False, "error": None}
```

This returns local's first-pass answer even if it was below the confidence threshold —
an explicit accuracy-for-token-score tradeoff, not a silent one (the `error` field says
why). After every real remote call, `self.remote_tokens_spent += remote_tokens` so later
tasks in the same batch see an accurate running total.

## Error handling

- Classifier match failure (no keywords hit) → falls back to `"general"` category →
  `REMOTE_MODEL_NAME` — same behavior as today, never a hard error.
- Heuristic model map pointing at a model not in this run's actual `ALLOWED_MODELS` →
  falls back to `REMOTE_MODEL_NAME` before the call is ever made (never trips
  `remote_client`'s existing `_is_model_allowed` rejection path).
- Budget/cap trip → falls back to local's already-computed answer, not a retry or an
  error state; logged with a reason string so it's visible in `logs/run_log.jsonl` and
  `eval_harness.py` output.

## Testing

- `tests/test_router.py`: extend for (a) category classification picks the expected
  model per a handful of representative prompts per category, (b) task-cap trip forces
  local even when local confidence was low, (c) budget trip forces local once cumulative
  spend + estimate crosses `MAX_REMOTE_TOKENS_BUDGET`, (d) heuristic map miss falls back
  to `REMOTE_MODEL_NAME` safely.
- New `tests/test_classifier.py` for `classify_task()` in isolation.
- Manual dev check: run `eval_harness.py --interactive`, type a code-shaped prompt and a
  creative-shaped prompt, confirm `model_used` differs between them in the printed
  output.
