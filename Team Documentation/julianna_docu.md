
# Julianna's Documentation

Review + fix session against the official AMD Developer Hackathon Track 1 Participant
Guide, the Discord clarification posted for Track 1, and the kickoff-day announcement
publishing the real `ALLOWED_MODELS` list. Code changes this session: `main.py`,
`scripts/smoke_test.py`, `config/settings.py`, `Dockerfile`, `entrypoint.sh`,
`src/router/policy.py`, `src/models/remote_client.py`; everything else below is
findings/recommendations for the team.

Published `ALLOWED_MODELS` (Track 1, from the kickoff announcement):
`minimax-m3`, `kimi-k2p7-code`, `gemma-4-31b-it`, `gemma-4-26b-a4b-it`,
`gemma-4-31b-it-nvfp4`.

---
## What I created

- `Team Documentation/julianna_docu.md` (this file).
- `Hybrid Token-Efficient Routing Agent/scripts/smoke_test.py` — moved the manual
  "ask one question, print the result" dev check out of `main.py` into its own script
  (matches the existing `scripts/test_call_fireworks.py` convention). Run locally with
  `python scripts/smoke_test.py`; it is never imported or run by `main.py`.

## What I edited

- `Hybrid Token-Efficient Routing Agent/main.py` — rewrote to implement the actual
  submission I/O contract (see "Solutions" below). Previously it just ran one hardcoded
  question and printed to stdout; it did not read or write anything the grading harness
  expects. Also removed the hardcoded `router.route("What is the capital of France?")`
  smoke-test call that had been added back into `main()` after the first rewrite — see
  "P0 — main.py ran an extra hardcoded query on every execution" below.
- `Hybrid Token-Efficient Routing Agent/config/settings.py` — fixed `REMOTE_MODEL_NAME`
  to default from `ALLOWED_MODELS` instead of a hardcoded literal — see
  "P1 — `REMOTE_MODEL_NAME` default may not be a valid kickoff-day model" below. Also
  changed the `LOCAL_MODEL_NAME` default from `gemma2:9b` to `gemma2:2b` — see
  "P0 — Default local model exceeds the grading environment's RAM budget" below.
- `Dockerfile` — added a build-time step that starts `ollama serve`, waits for it to be
  ready, runs `ollama pull "${LOCAL_MODEL_NAME}"`, then stops the server, so the model
  weights are committed into the image layer instead of fetched at container startup.
  `LOCAL_MODEL_NAME` is now an `ARG`/`ENV` (default `gemma2:2b`) so the baked-in model
  and the runtime default in `settings.py` can't drift apart. See
  "P0 — Container pulls the local model at startup instead of bundling it" below.
- `entrypoint.sh` — removed the `ollama pull` call; it now only starts `ollama serve`,
  waits for readiness, and execs `main.py`. No network dependency at container startup.
  Also added a warm-up call (`ollama run "${LOCAL_MODEL_NAME}" "warm up"`) right before
  `exec python main.py` — see "P1 — First real task pays a cold-model-load cost" below.
- `Hybrid Token-Efficient Routing Agent/config/settings.py` — also tightened
  `REMOTE_TIMEOUT_SECONDS` (30→10) and `REMOTE_MAX_RETRIES` (2→1) — see
  "P1 — Remote timeout/retry budget could exceed the 30-second response limit" below.
- `Hybrid Token-Efficient Routing Agent/src/router/policy.py` — wired `Policy.threshold`
  and `should_escalate`'s default to `config.settings.CONFIDENCE_THRESHOLD` instead of a
  hardcoded `0.8`, and removed the `complexity_checker`-based pre-routing bypass. See
  "P1 — Confidence threshold is hardcoded" and "P2 — Complexity-based pre-routing may
  escalate too eagerly" below. Router owner's file — touched this session with the
  team's go-ahead, unlike earlier sessions where it was left flagged for Jasper.

## What I deleted

- Nothing deleted in this session. (Note: `logs/run_log.jsonl` was already removed from
  git tracking and `.gitignore` updated to cover `logs/` in an earlier merge from the
  docker-branch PR — not done by me, listing it here only so the history is clear.)

---
## Issues / problems / bugs found

### P0 — `main.py` did not implement the required I/O contract
**Problem:** The guide requires the container to read tasks from `/input/tasks.json` on
startup and write `/output/results.json` (a list of `{"task_id", "answer"}` objects)
before exiting. The old `main.py` never touched either path — it hardcoded a single
question ("What is the capital of France?") and printed the answer to stdout. Per the
guide's troubleshooting table, a submission that never writes `/output/results.json`
scores `OUTPUT_MISSING` — zero, regardless of how good the routing logic is. This was
the single biggest blocker to getting any score at all, ahead of every other issue found
in earlier review sessions.

**Solution (applied):** Rewrote `main.py` to:
- Read `/input/tasks.json` (a JSON array of `{"task_id", "prompt"}` objects).
- Call `Policy.route(prompt)` per task (unchanged routing logic — no changes to
  `policy.py`, `local_client.py`, `remote_client.py`, or `validators.py`).
- Collect `{"task_id": ..., "answer": ...}` per task and write the full list to
  `/output/results.json` as valid JSON before exiting.
- Wrap each task in its own `try/except` so one malformed task (bad schema, a crash
  inside routing) can't take down the whole run and zero the entire submission —
  it logs to stderr and falls back to an empty answer for that task instead.
- Return exit code `0` on success and `1` if the input can't be read or the output
  can't be written, matching "exit code 0 on success, non-zero on failure."
- No answers are hardcoded or cached — every task is routed live through
  `Policy.route()`, per the "do not hardcode or cache answers" rule.

### P0 — `main.py` ran an extra hardcoded query on every execution
**Problem:** After the I/O contract rewrite above, a manual smoke-test snippet
(`router.route("What is the capital of France?")` plus four `print()` calls) was added
back into `main()`, ahead of the real task loop. Because it lived inside `main()`, it
would run on *every* execution of the container — including during actual grading.
Depending on the router's complexity/confidence checks, that extra call could escalate
to the Fireworks remote model and burn real tokens on a question that isn't even part
of the submission, directly hurting the token-efficiency ranking for no benefit. It also
adds unnecessary latency against the 10-minute runtime cap.

**Solution (applied):** Removed the snippet from `main()` and moved it into
`Hybrid Token-Efficient Routing Agent/scripts/smoke_test.py`, matching the existing
`scripts/test_call_fireworks.py` convention for dev-only scripts that are never imported
or executed by the submission entrypoint. Run it manually with
`python scripts/smoke_test.py` to sanity-check the router during development;
`main.py` now only does the task-loop I/O contract.

### P0 — Container pulls the local model at startup instead of bundling it
**Problem:** `entrypoint.sh` still runs `ollama serve`, waits for it to come up, then
does `ollama pull "${LOCAL_MODEL_NAME:-gemma2:9b}"` over the network before running
`main.py`. The guide requires the container to be ready within 60 seconds; pulling a
multi-GB model at startup will almost certainly blow that budget on its own, separate
from whether the grading sandbox even allows outbound network access. This also
contradicts AMD's Discord clarification for Track 1: "No Ollama or model runtime is
pre-installed: bundle model weights directly in your Docker image."

**Solution (applied):** `Dockerfile` now runs `ollama serve` in the background during
the build, waits for it to be ready (`until ollama list ...`, same pattern as
`entrypoint.sh`), runs `ollama pull "${LOCAL_MODEL_NAME}"`, then kills the build-time
server. The pulled weights land on disk as part of the image layer. `entrypoint.sh` was
simplified to only start `ollama serve`, wait for readiness, and `exec python main.py`
— no `ollama pull` at container startup, no network dependency during grading.

**Not yet verified:** Docker isn't available in this dev environment, so this hasn't
been confirmed with a real `docker build` / `docker run`. Someone with Docker needs to
build the image and check (a) the build-time pull actually succeeds and writes weights
under the image's Ollama model directory, (b) `entrypoint.sh` finds them without hitting
the network, and (c) container ready-time is comfortably under 60 seconds.

### P1 — First real task pays a cold-model-load cost, risking the 30-second response limit
**Problem:** Discovered while testing the fixes above: `ollama serve` starting
successfully (what `entrypoint.sh`'s wait-loop checks) only means the server process is
up — it does not mean the model is loaded into memory. Ollama loads weights from disk
into RAM lazily, on the first inference call, and unloads idle models after ~5 minutes
(`keep_alive` default). Since the old `entrypoint.sh` went straight from "server ready"
to `exec python main.py`, the *first real task* in a grading run would have paid this
cold-load cost — risking a timeout against the guide's "under 30 seconds per response"
rule specifically on task #1, separate from the container-ready-within-60s rule (which
only covers the server starting, not a model being loaded).

**Verified locally:** Confirmed with `gemma2:2b` on this dev machine — `ollama ps`
showed no models loaded; a cold local-client call timed out at the 30s
`OLLAMA_TIMEOUT_SECONDS` ceiling. After running `ollama run gemma2:2b "warm up"`
(17.6s), `ollama ps` showed the model loaded in VRAM, and a subsequent real router call
completed in 3.8s.

**Solution (applied):** Added a warm-up call to `entrypoint.sh` —
`ollama run "${LOCAL_MODEL_NAME}" "warm up" > /dev/null 2>&1 || true` — right after the
server-ready wait loop and before `exec python main.py`. This pays the cold-load cost
during container startup (against the 60-second ready budget, which has headroom) so
every real task, including the first, hits an already-warm model. The `|| true` makes
it best-effort: if the warm-up call itself fails for any reason, `main.py` still runs
and just takes the cold-load hit on its own first task rather than the container
crashing outright.

**Not yet verified:** The ~17.6s warm-up time was measured on this dev machine with
`gemma2:2b`; actual timing on the grading VM's 4GB/2vCPU environment is unconfirmed and
could differ. Combined with `ollama serve` startup time, this should still land
comfortably under the 60-second ready budget, but worth checking once Docker is
available.

### P0 — Default local model (`gemma2:9b`) exceeds the grading environment's RAM budget
**Problem:** The guide states the grading environment is 4 GB RAM / 2 vCPU, that a 7B
4-bit model "fills the full RAM budget, leaving no room for agent code," and that
2B–3B 4-bit models are the safe range. `LOCAL_MODEL_NAME` defaults to `gemma2:9b` (9B),
well past that ceiling — a strong candidate for `RUNTIME_ERROR` (OOM) or `TIMEOUT`
during grading.

**Solution (applied):** Switched the default to `gemma2:2b` (2.6B, ~1.6GB at Ollama's
default Q4_0 quantization) in both `config/settings.py` and the `Dockerfile`
`ARG LOCAL_MODEL_NAME`, so it leaves real headroom under the 4GB/2vCPU grading budget
alongside the Python agent process. Not yet benchmarked against the 8 capability
categories in the guide — worth an `eval_harness.py` pass to confirm accuracy is
acceptable before locking this in; swapping to a different 2B–3B model later is a
one-line change in both files.

### P1 — Confidence threshold is hardcoded, ignoring the tunable env var
**Problem:** `Policy.__init__` in `src/router/policy.py` sets `self.threshold = 0.8`
directly, ignoring `config.settings.CONFIDENCE_THRESHOLD` (env-tunable, default 0.75).
The settings file comment says this value is meant to be tuned on kickoff day; right
now, changing the env var does nothing because `Policy` never reads it.

**Solution (applied):** `Policy.threshold` and `should_escalate()`'s default parameter
both now resolve from `config.settings.CONFIDENCE_THRESHOLD` instead of the hardcoded
literal. Verified locally: `Policy().threshold` resolves to `0.75` (the current default)
and tracks the env var if set. All 15 existing tests in `tests/` still pass.

### P1 — `REMOTE_MODEL_NAME` default was not a valid model, and could never be fixed by "just setting it on kickoff day"
**Problem:** `remote_client.py` defaulted to calling
`accounts/fireworks/models/gpt-oss-20b` (via `config.settings.REMOTE_MODEL_NAME`),
which is not one of the actual `ALLOWED_MODELS` published in the kickoff announcement
(`minimax-m3`, `kimi-k2p7-code`, `gemma-4-31b-it`, `gemma-4-26b-a4b-it`,
`gemma-4-31b-it-nvfp4`). `_is_model_allowed()` already guarded this correctly — it
refuses to call a disallowed model and returns a clear error instead of causing a
`MODEL_VIOLATION` — but that meant every escalation to remote silently errored out.

This turned out to be more than a "set it before submitting" reminder: `REMOTE_MODEL_NAME`
is **not** one of the three env vars the harness actually injects (only
`FIREWORKS_API_KEY`, `FIREWORKS_BASE_URL`, and `ALLOWED_MODELS` are), and `.env` is
correctly excluded from the Docker image per the guide. So during real grading,
`REMOTE_MODEL_NAME` would always be unset and fall back to the invalid hardcoded
literal, no matter what anyone configured locally — a code fix was required, not just
an environment-variable action item.

**Solution (applied):** `config/settings.py` now computes
`REMOTE_MODEL_NAME = os.getenv("REMOTE_MODEL_NAME") or (ALLOWED_MODELS[0] if ALLOWED_MODELS else <old literal fallback>)`,
with `ALLOWED_MODELS` parsed first so it's available for the default. Verified locally:
with `ALLOWED_MODELS` set (as the harness does) and no `REMOTE_MODEL_NAME` override,
it now resolves to `minimax-m3` (the first published model) instead of the old invalid
ID. `remote_client.py` needed no changes — it already imports `REMOTE_MODEL_NAME` from
settings as a function default, which now resolves correctly at import time.

Still a team judgment call: whether always picking `ALLOWED_MODELS[0]` is the right
choice, or whether a specific model should be preferred for certain task types (e.g.
`kimi-k2p7-code` for code debugging/generation categories) via an explicit
`REMOTE_MODEL_NAME` override.

### P0 — Bare model names from the announcement don't work as Fireworks model IDs
**Problem:** Discovered while testing the real escalation path end-to-end (with a real
`FIREWORKS_API_KEY` in `.env` for the first time this session). `remote_client.py` sends
whatever string is in `ALLOWED_MODELS`/`REMOTE_MODEL_NAME` straight to Fireworks' `model`
field. The kickoff announcement's published names (`minimax-m3`, `kimi-k2p7-code`, etc.)
are short display names, not full Fireworks model IDs — sending `"minimax-m3"` directly
gets a `404 Model not found, inaccessible, and/or not deployed` from Fireworks' real
API. If the actual grading harness injects `ALLOWED_MODELS` in this same short form
(unconfirmed either way — could not check against the real harness from here), **every
remote escalation during real grading would silently fail**, which is a much bigger risk
than anything else found this session: any task the local model can't handle well would
come back with an empty answer instead of a real one.

**Verified locally:** Direct API test confirmed the failure mode and the fix:
```
'minimax-m3'                              -> 404 Model not found
'accounts/fireworks/models/minimax-m3'    -> 200 success
```

**Solution (applied):** Added `_normalize_model_id()` to `remote_client.py` — if a model
string doesn't already start with `"accounts/"`, it prepends
`"accounts/fireworks/models/"` before building the Fireworks request payload. This is
applied only to the outgoing API call; `_is_model_allowed()`'s membership check against
`ALLOWED_MODELS` is untouched, so it still validates against whatever format the harness
actually declares. This makes the fix safe either way: if the harness injects short
names (like the announcement text), we now normalize them correctly; if it already
injects full paths, `_normalize_model_id()` is a no-op since they already start with
`"accounts/"`.

**Verified end-to-end after the fix:** Forced a real escalation through the actual
`Policy.route()` code path (temporarily set `threshold = 0.99` so no local answer could
clear the bar) and got a real, correct Fireworks response — `"The capital of France is
**Paris**."`, 161 real tokens, no error. All 15 existing tests still pass.

**Independently reproduced (Julianna, own machine, `eval_harness.py --threshold 0.99`,
2 separate runs):** Zero `404`/error results across both runs (20 total task attempts,
8 remote per run) — every remote call succeeded with a real answer and real token count.
Accuracy went 75% (local-only, pre-fix baseline) → 87.5% → 100% across the two runs;
remote tokens per run were 2928 and 3065. The local/remote split for a couple of tasks
(`math_002`, `reasoning_002`) varied between the two runs even at the same
`threshold=0.99` — expected, not a bug: the local model's self-reported confidence
isn't perfectly deterministic call-to-call, so a task landing at confidence 1.00 one run
and 0.9x the next changes whether it clears the (unreachable-by-design) 0.99 bar. This
also gave a clean illustration of the earlier confidence-vs-correctness finding:
`reasoning_002` (feathers vs. steel) stayed local at 1.00 confidence in one run and got
it wrong ("a kilogram of steel"); in the other run it escalated instead and got it right
("same") — remote escalation is a real correctness safety net for this failure mode,
just not a guaranteed one given confidence's own variance.

**Still open — flagged for team confirmation, not fully resolved:** Whether the real
harness-injected `ALLOWED_MODELS` at grading time uses the short announcement names or
full `accounts/fireworks/models/...` paths is still unconfirmed. The fix above is safe
regardless, but worth checking the participant guide/Discord for the exact injected
format if it's stated anywhere, just to be certain.

### P1 — Remote timeout/retry budget could exceed the 30-second response limit
**Problem:** `REMOTE_TIMEOUT_SECONDS=30` (default) combined with `REMOTE_MAX_RETRIES=2`
(3 attempts total) plus exponential backoff meant a single escalated task could take up
to ~91.5 seconds worst case (three 30s timeouts + ~1.5s of backoff) — well past the
guide's "response time per request must be under 30 seconds" rule, and eating heavily
into the overall 10-minute container runtime budget.

**Solution (applied):** `config/settings.py` now defaults `REMOTE_TIMEOUT_SECONDS` to
`10` and `REMOTE_MAX_RETRIES` to `1` (2 attempts total). Worst case is now
10 + 10 + ~0.5s backoff ≈ 20.5 seconds — comfortably under the 30-second limit with
margin for network/parsing overhead. Both remain env-overridable if the team wants to
retune after seeing real Fireworks latency on kickoff day.

### P2 — Complexity-based pre-routing was escalating too eagerly
**Problem:** `src/router/complexity.py`'s `complexity_checker()` sent any task scoring
≥0.6 straight to the remote (Fireworks) model, bypassing the local model entirely, based
on keyword + length heuristics. Several trigger words ("explain", "write", "create",
"design", "describe", "debug") overlap heavily with ordinary phrasing in AMD's own
capability categories (e.g. category 6, "code debugging"; category 8, "code
generation"). This risked routing tasks to remote that the local model could have
answered correctly, increasing token usage without an accuracy benefit — directly
hurting rank on the token-efficiency axis.

**Data gathered:** `FIREWORKS_API_KEY` isn't configured in this dev environment, so a
live token/accuracy A/B run wasn't possible — but the trigger condition itself doesn't
need live API calls to test. Ran `complexity_checker()` directly against realistic
prompts modeled on the guide's 8 task categories (closer in length/detail to real
grading tasks than the short `eval_harness.py` practice stubs). Results:

| Task type | Score | Would bypass local? |
|---|---|---|
| Full code-debug prompt (with actual code included) | 1.00 | yes |
| Full code-gen prompt | 0.75 | yes |
| Full logic-puzzle prompt (with "explain your reasoning") | 1.00 | yes |

Three of the eight official task categories tripped the ≥0.6 bypass on realistic-length
prompts, confirming the original concern.

**Solution (applied):** Removed the `complexity_checker`-based pre-routing gate from
`Policy.route()` entirely, per the original recommendation ("if pre-routing isn't
measurably improving accuracy, drop it in favor of relying purely on the existing
post-hoc escalation"). Every task now gets a real local attempt first; the existing
confidence + format-validity check (already in `route()`, unchanged) still escalates to
remote whenever the local answer doesn't meet the bar — so no safety net was removed,
just the premature keyword-based one. `complexity_checker()` and `complexity.py` are
left in place (unused for now) rather than deleted, in case the team wants to repurpose
the category tags it already computes (e.g. for model selection) later. All 15 existing
tests still pass.

### Observation (not a bug, no fix applied) — self-reported confidence doesn't reliably catch wrong answers on trick questions
**What we saw:** Ran `eval_harness.py` against the 10 practice tasks with a warm local
model (`llama3.2:latest` for this run). All 10 tasks stayed local (0 remote calls, 0
tokens) — expected, confirms the P2 fix above. Accuracy came out to 75% (6/8 graded
correct; 2 tasks have no fixed expected answer). Both failures were the same pattern:
`reasoning_001` ("a farmer has 17 sheep, all but 9 die, how many are left?" — correct
answer 9, model said 8) and `reasoning_002` ("kilogram of feathers vs. kilogram of
steel, which is heavier?" — correct answer "same," model said "a kilogram of steel").
Both are classic trick questions small models are known to get wrong. On both, the
model self-reported **0.90 and 1.00 confidence** — well above `CONFIDENCE_THRESHOLD`
(0.75) — so `Policy.route()` had no signal to escalate either one to remote.

**Why this matters:** No threshold value fixes this — the model isn't uncertain, it's
confidently wrong, so raising or lowering `CONFIDENCE_THRESHOLD` doesn't help on this
task shape. This is a real risk to the accuracy gate specifically for trick-question /
classic-riddle-shaped prompts, separate from anything the routing logic controls.

**Not applied — flagged for team discussion, no action taken:** Possible directions if
this turns out to matter for real grading tasks: a small set of known trick-question
patterns checked independent of the model's self-reported confidence, or a lightweight
second-pass/verifier step for certain prompt shapes. Needs the team to decide whether
this is worth the added complexity before kickoff, or whether it's an acceptable
accuracy trade-off given local answers are free (zero token cost) even when occasionally
wrong.

**Dev-environment note (not a bug):** The first inference call to any just-selected
Ollama model (right after `ollama pull`, or right after switching `LOCAL_MODEL_NAME`)
can exceed `OLLAMA_TIMEOUT_SECONDS` (30s default; cold-load time can run close to or
past that) and show up as a
false "escalated to remote" result. Ollama keeps loading the model server-side even
after the client times out, so the second call is fast. Always throw away the first
call to a freshly-selected model when testing locally.

---
## Compliance check against the AMD Track 1 guide (status after this session)

| Requirement | Status |
|---|---|
| Read `/input/tasks.json`, write `/output/results.json` | Fixed in this session (`main.py`) |
| Exit 0 on success / non-zero on failure | Fixed in this session (`main.py`) |
| Results JSON schema (`task_id` + `answer`) | Fixed in this session (`main.py`) |
| No hardcoded/cached answers | OK — routing is live per task |
| Route all Fireworks calls through `FIREWORKS_BASE_URL` | OK — `remote_client.py` already does this |
| Only call models in `ALLOWED_MODELS` | Fixed in this session (`config/settings.py`) — `REMOTE_MODEL_NAME` now defaults from `ALLOWED_MODELS` |
| Ready within 60 seconds | Fixed in this session (`Dockerfile` + `entrypoint.sh`) — not yet build-verified, no Docker in this dev environment (P0 above) |
| Fit within 4 GB RAM / 2 vCPU | Fixed in this session — default local model switched to `gemma2:2b` (P0 above), not yet benchmarked for accuracy |
| Response time per request under 30 seconds | Fixed in this session — remote timeout/retry budget tightened from ~91.5s worst case to ~20.5s (P1 above) |
| Confidence threshold actually tunable via env var | Fixed in this session — `Policy.threshold` now reads `CONFIDENCE_THRESHOLD` (P1 above) |
| `linux/amd64` image manifest | Not verified this session — confirm build command includes `--platform linux/amd64` if building on Apple Silicon |
| Image ≤ 10 GB compressed | Not verified this session — worth checking once the model is bundled into the image |
