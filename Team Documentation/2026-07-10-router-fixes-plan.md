# Jasper's 3 Router Fixes Implementation Plan

> **Status: Implemented (2026-07-10).** All 4 tasks executed via subagent-driven development, each passing its own task review plus a final whole-branch review (Ready to merge: Yes after one post-review fix). Committed directly to `main`, commits `516e648`..`1ee9c45`. See `Team Documentation/julianna_docu.md`'s 2026-07-10 session entry for the full writeup, including 3 bugs self-caught during implementation and the list of non-blocking minor findings left open for later.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dev-only interactive prompt loop, task-category-based remote model selection (with real model names surfaced instead of the literal string `"remote"`), and a token-budget guard that falls back to the local model when a remote call would be too expensive.

**Architecture:** Two new standalone modules (`src/router/classifier.py`, `src/router/budget.py`) provide pure functions with no side effects. `src/router/policy.py`'s `Policy.route()` is extended in place to call them at the existing escalation point. `eval_harness.py` gets a new `--interactive` entrypoint that reuses the same `Policy` class. `main.py` (the graded submission entrypoint) is never touched.

**Tech Stack:** Python 3, pytest, `unittest.mock` (patch/patch.object), no new dependencies.

## Global Constraints

- `main.py`'s I/O contract (read `/input/tasks.json`, write `/output/results.json`, exit 0/non-zero) must remain untouched — it's fixed by the grading harness.
- Only tokens routed through `FIREWORKS_BASE_URL` count against the score; local tokens are free. Both new budget settings (`MAX_TASK_PROMPT_TOKENS_ESTIMATE`, `MAX_REMOTE_TOKENS_BUDGET`) must default to effectively inert values so behavior doesn't change until the team opts in via env vars.
- An empty `ALLOWED_MODELS` list must fail **open** (any model allowed), matching the existing convention in `src/models/remote_client.py`'s `_is_model_allowed()` — never fail-closed.
- No new third-party dependencies. `requirements.txt` only has `requests>=2.31.0` and `python-dotenv>=1.0.0`; token estimation must stay a plain heuristic (chars/4), not a real tokenizer.
- Follow existing test conventions exactly: pytest with plain `assert` (no fixture files, no `conftest.py`), `sys.path.insert(0, str(Path(__file__).resolve().parents[1]))` as the first lines of every test file, `unittest.mock.patch`/`patch.object` for mocking network/model calls (see `tests/test_local_client.py`).
- All file paths below are relative to `Hybrid Token-Efficient Routing Agent/` (the actual submission subfolder — not the repo root).

---

### Task 1: Task classifier

**Files:**
- Create: `src/router/classifier.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- Produces: `classify_task(prompt: str) -> str`, returning one of `"code"`, `"math"`, `"reasoning"`, `"creative"`, `"factual_qa"`, or `"general"` (no match). Task 2 imports this directly.

- [x] **Step 1: Write the failing test**

Create `tests/test_classifier.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.classifier import classify_task


def test_code_prompt():
    assert classify_task("Debug this Python function that raises a syntax error") == "code"


def test_math_prompt_by_keyword():
    assert classify_task("Calculate the sum of 45 and 12") == "math"


def test_math_prompt_by_numeric_pattern():
    assert classify_task("What does 17 * 23 equal?") == "math"


def test_reasoning_prompt():
    assert classify_task("Explain why the sky is blue and infer the underlying cause") == "reasoning"


def test_creative_prompt():
    assert classify_task("Write a poem about the ocean") == "creative"


def test_factual_qa_prompt():
    assert classify_task("What is the capital of France?") == "factual_qa"


def test_unmatched_prompt_falls_back_to_general():
    assert classify_task("zzz qwerty asdf") == "general"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classifier.py -v`
Expected: FAIL (or ERROR) with `ModuleNotFoundError: No module named 'src.router.classifier'`

- [x] **Step 3: Write minimal implementation**

Create `src/router/classifier.py`:

```python
import re

CODE_KEYWORDS = [
    "code", "function", "debug", "bug", "compile", "syntax",
    "algorithm", "python", "javascript", "class ", "def ", "error:",
]

MATH_KEYWORDS = [
    "calculate", "compute", "solve", "equation", "sum of",
    "how many", "how much",
]

REASONING_KEYWORDS = [
    "why", "explain", "prove", "infer", "logic", "if and only if",
    "therefore", "cause", "premise",
]

CREATIVE_KEYWORDS = [
    "write a", "poem", "story", "imagine", "compose", "creative",
]

FACTUAL_QA_KEYWORDS = [
    "what is", "who is", "when did", "where is", "capital of", "define",
]

MATH_PATTERN = re.compile(r"\d+\s*[\+\-\*/]\s*\d+")

CATEGORY_KEYWORDS = [
    ("code", CODE_KEYWORDS),
    ("math", MATH_KEYWORDS),
    ("reasoning", REASONING_KEYWORDS),
    ("creative", CREATIVE_KEYWORDS),
    ("factual_qa", FACTUAL_QA_KEYWORDS),
]


def classify_task(prompt: str) -> str:
    """
    Heuristic keyword-scoring classifier (same style as complexity.py's
    complexity_checker). Returns the category with the most keyword hits, or
    "general" if nothing matches. A numeric expression like "17 * 23" is a
    strong enough signal to short-circuit straight to "math".
    """
    text = prompt.lower().strip()

    if MATH_PATTERN.search(text):
        return "math"

    best_category = "general"
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS:
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classifier.py -v`
Expected: PASS (7 passed)

- [x] **Step 5: Commit**

```bash
git add "src/router/classifier.py" "tests/test_classifier.py"
git commit -m "feat: add heuristic task classifier for code/math/reasoning/creative/factual_qa"
```

---

### Task 2: Category-based remote model routing + real model names in output

**Files:**
- Modify: `config/settings.py` (append after line 43)
- Modify: `src/router/policy.py:1-5` (imports) and `:64-78` (escalation block)
- Modify: `eval_harness.py:73-96` (`print_summary`)
- Test: `tests/test_router.py` (currently just a placeholder comment — replace entirely)
- Test: `tests/test_eval_harness.py` (new)

**Interfaces:**
- Consumes: `classify_task(prompt: str) -> str` from Task 1.
- Produces: `Policy.route()`'s returned dict now has `model_used` set to the actual Fireworks model name string (e.g. `"kimi-k2p7-code"`) on escalation, instead of the literal `"remote"`. Task 3 builds directly on top of this same escalation block.

- [x] **Step 1: Write the failing tests**

Replace the entire contents of `tests/test_router.py`:

```python
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.policy import Policy
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient


def _low_confidence_local_result():
    return {"answer": "unsure", "confidence": 0.1, "is_valid_format": True, "error": None}


def test_escalation_uses_category_model_name():
    with patch("src.router.policy.ALLOWED_MODELS", ["kimi-k2p7-code", "minimax-m3"]):
        with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
            with patch.object(RemoteClient, "generate", return_value={
                "answer": "def foo(): pass", "tokens_used": 42, "model": "kimi-k2p7-code", "error": None,
            }) as mock_generate:
                router = Policy()
                result = router.route("Debug this Python function that raises a syntax error")

    assert result["model_used"] == "kimi-k2p7-code"
    assert mock_generate.call_args.kwargs["model_name"] == "kimi-k2p7-code"


def test_escalation_falls_back_when_mapped_model_not_allowed():
    with patch("src.router.policy.ALLOWED_MODELS", ["gemma-4-31b-it"]):
        with patch("src.router.policy.REMOTE_MODEL_NAME", "gemma-4-31b-it"):
            with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
                with patch.object(RemoteClient, "generate", return_value={
                    "answer": "n/a", "tokens_used": 10, "model": "gemma-4-31b-it", "error": None,
                }) as mock_generate:
                    router = Policy()
                    result = router.route("Debug this Python function that raises a syntax error")

    # classify_task picks "code" -> kimi-k2p7-code, but it's not in this
    # run's ALLOWED_MODELS -- must fall back to REMOTE_MODEL_NAME
    assert result["model_used"] == "gemma-4-31b-it"
    assert mock_generate.call_args.kwargs["model_name"] == "gemma-4-31b-it"


def test_escalation_unmatched_category_uses_default_model():
    with patch("src.router.policy.ALLOWED_MODELS", []):
        with patch("src.router.policy.REMOTE_MODEL_NAME", "gemma-4-31b-it"):
            with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
                with patch.object(RemoteClient, "generate", return_value={
                    "answer": "n/a", "tokens_used": 10, "model": "gemma-4-31b-it", "error": None,
                }) as mock_generate:
                    router = Policy()
                    result = router.route("zzz qwerty asdf")

    assert result["model_used"] == "gemma-4-31b-it"
    assert mock_generate.call_args.kwargs["model_name"] == "gemma-4-31b-it"
```

Create `tests/test_eval_harness.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_harness import print_summary


def test_print_summary_groups_by_real_model_name(capsys):
    results = [
        {"task_id": "t1", "model_used": "local", "tokens_used": 0, "correct": True, "answer": "ok", "prompt": "p", "expected": "ok"},
        {"task_id": "t2", "model_used": "kimi-k2p7-code", "tokens_used": 42, "correct": True, "answer": "ok", "prompt": "p", "expected": "ok"},
        {"task_id": "t3", "model_used": "minimax-m3", "tokens_used": 58, "correct": False, "answer": "no", "prompt": "p", "expected": "ok"},
    ]
    print_summary(results)
    captured = capsys.readouterr().out
    assert "Local answers:    1" in captured
    assert "Remote answers:   2" in captured
    assert "kimi-k2p7-code: 1" in captured
    assert "minimax-m3: 1" in captured
    assert "Remote tokens:    100" in captured
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_router.py tests/test_eval_harness.py -v`
Expected: FAIL — `test_router.py` fails because `RemoteClient.generate` isn't called with a `model_name` kwarg yet (escalation still always calls `self.remote_client.generate(task)` with no category logic) and `model_used` is still the literal `"remote"`; `test_eval_harness.py` fails because `print_summary` doesn't print per-model breakdown lines.

- [x] **Step 3: Write minimal implementation**

In `config/settings.py`, append after the existing `REMOTE_MODEL_NAME` block (after line 43):

```python

# Heuristic category -> Fireworks model map for task-based routing (added
# 2026-07-10). None of these assignments are benchmarked yet -- retune once
# the team has real per-category accuracy data. Falls back to
# REMOTE_MODEL_NAME for any category not listed here, or if the mapped model
# isn't in this run's ALLOWED_MODELS.
CATEGORY_MODEL_MAP = {
    "code": "kimi-k2p7-code",
    "math": "minimax-m3",
    "reasoning": "minimax-m3",
    "creative": "gemma-4-31b-it",
    "factual_qa": "gemma-4-26b-a4b-it",
    "general": REMOTE_MODEL_NAME,
}
```

In `src/router/policy.py`, replace the import block (lines 1-5):

```python
from config.settings import CONFIDENCE_THRESHOLD
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.validators import Validators, answers_agree
from src.utils.logger import log_decision
```

with:

```python
from config.settings import ALLOWED_MODELS, CATEGORY_MODEL_MAP, CONFIDENCE_THRESHOLD, REMOTE_MODEL_NAME
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.classifier import classify_task
from src.router.validators import Validators, answers_agree
from src.utils.logger import log_decision
```

Then replace the escalation block (lines 64-78 — everything from `remote_result = self.remote_client.generate(task)` to the end of `route()`):

```python
        remote_result = self.remote_client.generate(task)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None

        log_decision(task_id=task_id, model_used="remote", tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": "remote",
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
```

with:

```python
        category = classify_task(task)
        model_name = CATEGORY_MODEL_MAP.get(category, REMOTE_MODEL_NAME)
        if ALLOWED_MODELS and model_name not in ALLOWED_MODELS:
            model_name = REMOTE_MODEL_NAME

        remote_result = self.remote_client.generate(task, model_name=model_name)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None

        log_decision(task_id=task_id, model_used=model_name, tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": model_name,
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
```

In `eval_harness.py`, replace `print_summary` (lines 73-96):

```python
def print_summary(results):
    graded = [r for r in results if r["correct"] is not None]
    correct = [r for r in graded if r["correct"]]
    total_local = sum(1 for r in results if r["model_used"] == "local")
    total_remote = sum(1 for r in results if r["model_used"] == "remote")
    total_remote_tokens = sum(r["tokens_used"] for r in results if r["model_used"] == "remote")
    accuracy = len(correct) / len(graded) if graded else None

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total tasks:      {len(results)}")
    print(f"  Local answers:    {total_local}")
    print(f"  Remote answers:   {total_remote}")
    print(f"  Remote tokens:    {total_remote_tokens}")
    print(f"  Graded tasks:     {len(graded)}")
    print(f"  Correct:          {len(correct)}")
    print(f"  Accuracy:         {accuracy:.1%}" if accuracy is not None else "  Accuracy:         N/A (no expected values)")
    print(f"{'=' * 70}\n")

    for r in results:
        correct_str = "?" if r["correct"] is None else ("PASS" if r["correct"] else "FAIL")
        print(f"  [{correct_str}] [{r['model_used']:>6}] {r['task_id']}: {r['answer'][:60]}")
    print()
```

with:

```python
def print_summary(results):
    graded = [r for r in results if r["correct"] is not None]
    correct = [r for r in graded if r["correct"]]
    total_local = sum(1 for r in results if r["model_used"] == "local")
    total_remote = len(results) - total_local
    total_remote_tokens = sum(r["tokens_used"] for r in results if r["model_used"] != "local")
    accuracy = len(correct) / len(graded) if graded else None

    remote_model_counts = {}
    for r in results:
        if r["model_used"] != "local":
            remote_model_counts[r["model_used"]] = remote_model_counts.get(r["model_used"], 0) + 1

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Total tasks:      {len(results)}")
    print(f"  Local answers:    {total_local}")
    print(f"  Remote answers:   {total_remote}")
    for model_name, count in sorted(remote_model_counts.items()):
        print(f"    - {model_name}: {count}")
    print(f"  Remote tokens:    {total_remote_tokens}")
    print(f"  Graded tasks:     {len(graded)}")
    print(f"  Correct:          {len(correct)}")
    print(f"  Accuracy:         {accuracy:.1%}" if accuracy is not None else "  Accuracy:         N/A (no expected values)")
    print(f"{'=' * 70}\n")

    for r in results:
        correct_str = "?" if r["correct"] is None else ("PASS" if r["correct"] else "FAIL")
        print(f"  [{correct_str}] [{r['model_used']:>14}] {r['task_id']}: {r['answer'][:60]}")
    print()
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_router.py tests/test_eval_harness.py tests/test_classifier.py -v`
Expected: PASS (all tests green)

- [x] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS — in particular `tests/test_validators.py::test_validate_format_integration_with_policy` and all of `tests/test_local_client.py` must still pass unchanged, since `should_escalate()` wasn't touched.

- [x] **Step 6: Commit**

```bash
git add "config/settings.py" "src/router/policy.py" "eval_harness.py" "tests/test_router.py" "tests/test_eval_harness.py"
git commit -m "feat: route escalations to a category-specific remote model, surface real model names in output"
```

---

### Task 3: Token-budget fallback to local

**Files:**
- Create: `src/router/budget.py`
- Modify: `config/settings.py` (append after Task 2's `CATEGORY_MODEL_MAP` block)
- Modify: `src/router/policy.py` (imports, `__init__`, and the escalation block from Task 2)
- Test: `tests/test_budget.py` (new)
- Test: `tests/test_router.py` (append)

**Interfaces:**
- Consumes: the escalation block from Task 2 (`category`, `model_name` already computed before this task's insertion point).
- Produces: `estimate_tokens(text: str) -> int` from `src.router.budget`; `Policy.remote_tokens_spent` instance attribute (starts at 0, accumulates real remote token spend across the life of one `Policy` instance — i.e. across one full `tasks.json` batch in `main.py`, or one full interactive session in Task 4).

- [x] **Step 1: Write the failing tests**

Create `tests/test_budget.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.budget import estimate_tokens


def test_estimate_tokens_basic():
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 40) == 10


def test_estimate_tokens_minimum_one():
    assert estimate_tokens("") == 1
    assert estimate_tokens("a") == 1
```

Append to `tests/test_router.py`:

```python
def test_budget_task_cap_forces_local_fallback():
    long_prompt = "x " * 5000  # ~2500 estimated tokens, over the 2000 default cap
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate") as mock_generate:
            router = Policy()
            result = router.route(long_prompt)

    mock_generate.assert_not_called()
    assert result["model_used"] == "local"
    assert result["answer"] == "unsure"
    assert result["escalated"] is False


def test_budget_global_cap_forces_local_fallback():
    with patch("src.router.policy.MAX_REMOTE_TOKENS_BUDGET", 10):
        with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
            with patch.object(RemoteClient, "generate") as mock_generate:
                router = Policy()
                router.remote_tokens_spent = 5
                result = router.route("short prompt")

    mock_generate.assert_not_called()
    assert result["model_used"] == "local"


def test_budget_disabled_by_default_allows_remote():
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate", return_value={
            "answer": "ok", "tokens_used": 50, "model": "whatever", "error": None,
        }) as mock_generate:
            router = Policy()
            router.remote_tokens_spent = 999999  # would blow any real budget, but MAX_REMOTE_TOKENS_BUDGET defaults to 0 (unlimited)
            result = router.route("short prompt")

    mock_generate.assert_called_once()
    assert result["escalated"] is True


def test_remote_tokens_spent_accumulates_across_calls():
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate", return_value={
            "answer": "ok", "tokens_used": 50, "model": "whatever", "error": None,
        }):
            router = Policy()
            router.route("short prompt one")
            router.route("short prompt two")

    assert router.remote_tokens_spent == 100
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_budget.py tests/test_router.py -v`
Expected: FAIL — `test_budget.py` fails with `ModuleNotFoundError`; the new `test_router.py` budget tests fail because `Policy` has no budget check yet (`mock_generate.assert_not_called()` fails since it's still called every time).

- [x] **Step 3: Write minimal implementation**

Create `src/router/budget.py`:

```python
def estimate_tokens(text: str) -> int:
    """
    Rough token-count estimate (chars/4 heuristic). No tokenizer dependency
    is installed (requirements.txt only has requests + python-dotenv), and
    the 5 allowed Fireworks models don't share a single tokenizer anyway --
    this is an approximation used only to decide whether to skip a remote
    call, not an exact count.
    """
    return max(1, len(text) // 4)
```

In `config/settings.py`, append after Task 2's `CATEGORY_MODEL_MAP` block:

```python

# Token-budget guard for escalation (added 2026-07-10). Both inert by
# default -- 2000 is generous and 0 disables the global cap -- until the team
# sets these deliberately via env vars.
MAX_TASK_PROMPT_TOKENS_ESTIMATE = int(os.getenv("MAX_TASK_PROMPT_TOKENS_ESTIMATE", 2000))
MAX_REMOTE_TOKENS_BUDGET = int(os.getenv("MAX_REMOTE_TOKENS_BUDGET", 0))  # 0 = unlimited
```

In `src/router/policy.py`, replace the import block (as left by Task 2):

```python
from config.settings import ALLOWED_MODELS, CATEGORY_MODEL_MAP, CONFIDENCE_THRESHOLD, REMOTE_MODEL_NAME
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.classifier import classify_task
from src.router.validators import Validators, answers_agree
from src.utils.logger import log_decision
```

with:

```python
from config.settings import (
    ALLOWED_MODELS,
    CATEGORY_MODEL_MAP,
    CONFIDENCE_THRESHOLD,
    MAX_REMOTE_TOKENS_BUDGET,
    MAX_TASK_PROMPT_TOKENS_ESTIMATE,
    REMOTE_MODEL_NAME,
)
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.budget import estimate_tokens
from src.router.classifier import classify_task
from src.router.validators import Validators, answers_agree
from src.utils.logger import log_decision
```

Replace `Policy.__init__`:

```python
    def __init__(self):
        self.local_client = LocalClient()
        self.remote_client = RemoteClient()
        self.validators = Validators()
        self.threshold = CONFIDENCE_THRESHOLD
```

with:

```python
    def __init__(self):
        self.local_client = LocalClient()
        self.remote_client = RemoteClient()
        self.validators = Validators()
        self.threshold = CONFIDENCE_THRESHOLD
        self.remote_tokens_spent = 0
```

Replace the escalation block (as left by Task 2):

```python
        category = classify_task(task)
        model_name = CATEGORY_MODEL_MAP.get(category, REMOTE_MODEL_NAME)
        if ALLOWED_MODELS and model_name not in ALLOWED_MODELS:
            model_name = REMOTE_MODEL_NAME

        remote_result = self.remote_client.generate(task, model_name=model_name)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None

        log_decision(task_id=task_id, model_used=model_name, tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": model_name,
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
```

with:

```python
        category = classify_task(task)
        model_name = CATEGORY_MODEL_MAP.get(category, REMOTE_MODEL_NAME)
        if ALLOWED_MODELS and model_name not in ALLOWED_MODELS:
            model_name = REMOTE_MODEL_NAME

        estimated = estimate_tokens(task)
        over_task_cap = estimated > MAX_TASK_PROMPT_TOKENS_ESTIMATE
        over_budget = (
            MAX_REMOTE_TOKENS_BUDGET > 0
            and self.remote_tokens_spent + estimated > MAX_REMOTE_TOKENS_BUDGET
        )

        if over_task_cap or over_budget:
            reason = "task cap" if over_task_cap else "budget"
            log_decision(task_id=task_id, model_used="local", tokens_used=0,
                         confidence=confidence, escalated=False, answer=local_answer,
                         error=f"remote skipped: {reason} exceeded")
            return {
                "answer": local_answer,
                "model_used": "local",
                "confidence": confidence,
                "tokens_used": 0,
                "escalated": False,
                "error": None,
            }

        remote_result = self.remote_client.generate(task, model_name=model_name)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None
        self.remote_tokens_spent += remote_tokens

        log_decision(task_id=task_id, model_used=model_name, tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": model_name,
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_budget.py tests/test_router.py -v`
Expected: PASS (all tests green)

- [x] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS

- [x] **Step 6: Commit**

```bash
git add "src/router/budget.py" "config/settings.py" "src/router/policy.py" "tests/test_budget.py" "tests/test_router.py"
git commit -m "feat: fall back to local when a remote call would exceed the per-task or batch token budget"
```

---

### Task 4: Interactive prompt loop in eval_harness.py

**Files:**
- Modify: `eval_harness.py` (add `run_interactive()`, wire `--interactive` flag into `main()`)
- Test: `tests/test_eval_harness.py` (append)

**Interfaces:**
- Consumes: `Policy` (from Task 2/3's `src/router/policy.py`, unchanged interface — `Policy().route(prompt: str) -> dict`).
- Produces: `run_interactive() -> list[dict]`, same result-dict shape `run_eval` already produces (`task_id`, `prompt`, `expected`, `answer`, `model_used`, `confidence`, `tokens_used`, `correct`), so it can be passed straight into the existing `print_summary()`.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_eval_harness.py`:

```python
from unittest.mock import patch
from eval_harness import run_interactive
from src.router.policy import Policy


def test_interactive_stops_on_blank_input():
    with patch("builtins.input", side_effect=[""]):
        results = run_interactive()
    assert results == []


def test_interactive_stops_on_quit_keyword():
    with patch("builtins.input", side_effect=["quit"]):
        results = run_interactive()
    assert results == []


def test_interactive_records_typed_prompts():
    fake_route_result = {
        "answer": "Paris", "model_used": "local", "confidence": 0.9,
        "tokens_used": 0, "escalated": False, "error": None,
    }
    with patch("builtins.input", side_effect=["What is the capital of France?", "quit"]):
        with patch.object(Policy, "route", return_value=fake_route_result):
            results = run_interactive()

    assert len(results) == 1
    assert results[0]["prompt"] == "What is the capital of France?"
    assert results[0]["answer"] == "Paris"
    assert results[0]["model_used"] == "local"
    assert results[0]["task_id"] == "interactive_001"
```

- [x] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_harness.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_interactive' from 'eval_harness'`

- [x] **Step 3: Write minimal implementation**

In `eval_harness.py`, add `run_interactive()` right before `def print_summary(results):`:

```python
def run_interactive():
    router = Policy()
    results = []
    task_num = 0

    while True:
        prompt = input("What's on your mind right now?: ").strip()
        if not prompt or prompt.lower() in ("quit", "exit"):
            break

        task_num += 1
        task_id = f"interactive_{task_num:03d}"
        r = router.route(prompt)

        print(f"\n  [{task_id}] {prompt}")
        print(f"  {'-' * 60}")
        print(f"  Answer: {r['answer'][:80]}")
        print(f"  Model:  {r['model_used']}")
        print(f"  Conf:   {r['confidence']:.2f}")
        print(f"  Tokens: {r['tokens_used']}")
        if r.get("error"):
            print(f"  Error:  {r['error']}")

        results.append({
            "task_id": task_id,
            "prompt": prompt,
            "expected": None,
            "answer": r["answer"],
            "model_used": r["model_used"],
            "confidence": r["confidence"],
            "tokens_used": r["tokens_used"],
            "correct": None,
        })

    return results
```

Replace `main()`:

```python
def main():
    parser = argparse.ArgumentParser(description="Batch-evaluate the cascade router")
    parser.add_argument("--tasks", type=str, help="JSON file with task list")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true", help="Skip local/remote calls")
    args = parser.parse_args()

    if args.tasks:
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    else:
        tasks = DEFAULT_TASKS

    print(f"Running {len(tasks)} tasks (threshold={args.threshold})...")
    results = run_eval(tasks, args.threshold, args.dry_run)
    print_summary(results)
```

with:

```python
def main():
    parser = argparse.ArgumentParser(description="Batch-evaluate the cascade router")
    parser.add_argument("--tasks", type=str, help="JSON file with task list")
    parser.add_argument("--threshold", type=float, default=0.8, help="Confidence threshold (default: 0.8)")
    parser.add_argument("--dry-run", action="store_true", help="Skip local/remote calls")
    parser.add_argument("--interactive", action="store_true", help="Prompt for tasks one at a time instead of running a fixed list")
    args = parser.parse_args()

    if args.interactive:
        results = run_interactive()
        print_summary(results)
        return

    if args.tasks:
        tasks = json.loads(Path(args.tasks).read_text(encoding="utf-8"))
    else:
        tasks = DEFAULT_TASKS

    print(f"Running {len(tasks)} tasks (threshold={args.threshold})...")
    results = run_eval(tasks, args.threshold, args.dry_run)
    print_summary(results)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_harness.py -v`
Expected: PASS (all tests green)

- [x] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS — every test across `test_classifier.py`, `test_router.py`, `test_budget.py`, `test_eval_harness.py`, `test_validators.py`, `test_local_client.py` green.

- [x] **Step 6: Manual smoke check (real Ollama, not mocked)**

Run: `python eval_harness.py --interactive`
Type: `What is the capital of France?` then `quit`
Expected: prints Answer/Model/Conf/Tokens for the typed prompt, then a summary showing 1 total task, then exits cleanly.

- [x] **Step 7: Commit**

```bash
git add "eval_harness.py" "tests/test_eval_harness.py"
git commit -m "feat: add --interactive flag to eval_harness.py for ad-hoc dev prompts"
```
