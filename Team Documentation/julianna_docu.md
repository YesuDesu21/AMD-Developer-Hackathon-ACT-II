
# Julianna's Documentation

Review + fix session against the official AMD Developer Hackathon Track 1 Participant
Guide, the Discord clarification posted for Track 1, and the kickoff-day announcement
publishing the real `ALLOWED_MODELS` list. Code changes this session: `main.py`,
`scripts/smoke_test.py`, `config/settings.py`, `Dockerfile`, `entrypoint.sh`; everything
else below is findings/recommendations for the team.

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

**Solution (not yet applied — flagged for the router owner):** Change
`self.threshold = 0.8` to `self.threshold = CONFIDENCE_THRESHOLD` (imported from
`config.settings`), or accept it as a constructor argument defaulting to that setting.

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
| Only call models in `ALLOWED_MODELS` | Fixed in this session (`config/settings.py`) — `REMOTE_MODEL_NAME` now defaults from `ALLOWED_MODELS` |
| Ready within 60 seconds | Fixed in this session (`Dockerfile` + `entrypoint.sh`) — not yet build-verified, no Docker in this dev environment (P0 above) |
| Fit within 4 GB RAM / 2 vCPU | Fixed in this session — default local model switched to `gemma2:2b` (P0 above), not yet benchmarked for accuracy |
| `linux/amd64` image manifest | Not verified this session — confirm build command includes `--platform linux/amd64` if building on Apple Silicon |
| Image ≤ 10 GB compressed | Not verified this session — worth checking once the model is bundled into the image |
