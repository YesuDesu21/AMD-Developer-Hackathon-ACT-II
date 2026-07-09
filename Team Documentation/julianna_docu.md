
# Julianna's Documentation

Review + fix session against the official AMD Developer Hackathon Track 1 Participant
Guide and the Discord clarification posted for Track 1. Scope of this session's code
change was limited to `main.py` only; everything else below is findings/recommendations
for the team.

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

**Solution (not yet applied — out of scope for this session, flagged for the Docker
owner):** Bake the model weights into the image at `docker build` time (e.g.
`ollama pull` during the build stage, or `COPY` in pre-downloaded weights), so
`entrypoint.sh` only has to start `ollama serve` and immediately run `main.py` — no
network pull during grading.

### P0 — Default local model (`gemma2:9b`) exceeds the grading environment's RAM budget
**Problem:** The guide states the grading environment is 4 GB RAM / 2 vCPU, that a 7B
4-bit model "fills the full RAM budget, leaving no room for agent code," and that
2B–3B 4-bit models are the safe range. `LOCAL_MODEL_NAME` defaults to `gemma2:9b` (9B),
well past that ceiling — a strong candidate for `RUNTIME_ERROR` (OOM) or `TIMEOUT`
during grading.

**Solution (not yet applied — flagged for the team to decide the actual model):**
Switch `LOCAL_MODEL_NAME` to a 2B–3B 4-bit quantized model that fits the budget
alongside the agent process (e.g. a 4-bit `gemma2:2b` / `llama3.2:3b`-class model —
exact choice should be benchmarked against the 8 capability categories in the guide).

### P1 — Confidence threshold is hardcoded, ignoring the tunable env var
**Problem:** `Policy.__init__` in `src/router/policy.py` sets `self.threshold = 0.8`
directly, ignoring `config.settings.CONFIDENCE_THRESHOLD` (env-tunable, default 0.75).
The settings file comment says this value is meant to be tuned on kickoff day; right
now, changing the env var does nothing because `Policy` never reads it.

**Solution (not yet applied — flagged for the router owner):** Change
`self.threshold = 0.8` to `self.threshold = CONFIDENCE_THRESHOLD` (imported from
`config.settings`), or accept it as a constructor argument defaulting to that setting.

### P1 — `REMOTE_MODEL_NAME` default may not be a valid kickoff-day model
**Problem:** `remote_client.py` defaults to calling
`accounts/fireworks/models/gpt-oss-20b` (via `config.settings.REMOTE_MODEL_NAME`),
which is not guaranteed to be one of the actual `ALLOWED_MODELS` published by AMD on
kickoff day. The good news: `_is_model_allowed()` already guards this correctly —
it refuses to call a disallowed model and returns a clear error instead of causing a
`MODEL_VIOLATION`. But until `REMOTE_MODEL_NAME` (or `ALLOWED_MODELS`) is set to match
the real list, every escalation to remote will silently error out.

**Solution (not yet applied — action item, not a code fix):** Once AMD publishes the
real `ALLOWED_MODELS` list on kickoff/launch day, set `REMOTE_MODEL_NAME` (and/or
`ALLOWED_MODELS`) in the environment to a model from that list before building/
submitting the image.

### P2 — Complexity-based pre-routing may escalate too eagerly
**Problem:** `src/router/complexity.py`'s `complexity_checker()` sends any task scoring
≥0.6 straight to the remote (Fireworks) model, bypassing the local model entirely, based
on keyword + length heuristics. Several trigger words ("explain", "write", "create",
"design", "describe") overlap heavily with ordinary phrasing in AMD's own capability
categories (e.g. category 1, "explaining concepts"; category 8, "code generation").
This risks routing tasks to remote that the local model could have answered correctly,
which increases token usage without an accuracy benefit — directly hurting rank on the
token-efficiency axis (submissions are ranked ascending by total tokens after clearing
the accuracy gate).

**Solution (not yet applied — recommendation, needs data before changing anything):**
Before tuning, run `eval_harness.py` against the practice tasks from the participant
guide with and without the complexity pre-routing step enabled, and compare token
totals vs. accuracy. If pre-routing isn't measurably improving accuracy, raise its
threshold or drop it in favor of relying purely on the existing post-hoc escalation
(confidence + format validation after a real local attempt).

---
## Compliance check against the AMD Track 1 guide (status after this session)

| Requirement | Status |
|---|---|
| Read `/input/tasks.json`, write `/output/results.json` | Fixed in this session (`main.py`) |
| Exit 0 on success / non-zero on failure | Fixed in this session (`main.py`) |
| Results JSON schema (`task_id` + `answer`) | Fixed in this session (`main.py`) |
| No hardcoded/cached answers | OK — routing is live per task |
| Route all Fireworks calls through `FIREWORKS_BASE_URL` | OK — `remote_client.py` already does this |
| Only call models in `ALLOWED_MODELS` | Guarded correctly, but needs `REMOTE_MODEL_NAME` set to a real allowed model on kickoff day (P1 above) |
| Ready within 60 seconds | **Not yet fixed** — runtime `ollama pull` in `entrypoint.sh` (P0 above) |
| Fit within 4 GB RAM / 2 vCPU | **Not yet fixed** — `gemma2:9b` default is too large (P0 above) |
| `linux/amd64` image manifest | Not verified this session — confirm build command includes `--platform linux/amd64` if building on Apple Silicon |
| Image ≤ 10 GB compressed | Not verified this session — worth checking once the model is bundled into the image |
