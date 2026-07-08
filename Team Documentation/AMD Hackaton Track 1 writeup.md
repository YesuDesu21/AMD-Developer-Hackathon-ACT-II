# AMD Developer Hackathon (Act II) — Track 1: Hybrid Token-Efficient Routing Agent

## Context

We're a 4-person team (with Claude and Gemini as coding copilots) entering the AMD Developer Hackathon Act II on **July 6**. We chose **Track 1: Hybrid Token-Efficient Routing Agent** — beginner-level, and our team already has Ollama experience, which is the core skill this track needs.

**Track 1 rules, as given:**

- Build an agent that completes kickoff-revealed tasks autonomously.
- For each task, decide in real time: run it on a **local model** or call a **remote model via Fireworks AI**.
- Goal: minimize cost while staying above an (unrevealed) accuracy threshold.
- Scoring runs on a **standardized environment** we don't control — local models must be sized to fit it, since dev/test hardware doesn't have to match.
- **Local tokens count as zero cost.** Only Fireworks (remote) usage counts toward the score.
- Judged on: **token count + output accuracy**.
- Prompt-based and fine-tuned routers are scored identically — no bonus for fine-tuning.
- Specific models to route between are revealed on launch day (July 6), not before.
- Submission must be **containerized** (Docker).

Because the exact models and tasks are unknown until kickoff, the winning move is to walk in with a **generic, pluggable cascade-router architecture** already built and tested against placeholder tasks/models — so on kickoff day we only need to swap in the real model names and task format, not design the system from scratch.

**Repo:** `C:\Users\Julianna\Project\Hackathon\AMD-Developer-Hackathon-ACT-II` (git-cloned, currently just a bare `README.md` — nothing else committed yet). Implementation work below happens in this repo. Per instruction, do not commit until the user has reviewed the changes.

## Strategy: Local-First Cascade Router

Core idea (this is the "FrugalGPT"/cascade pattern, well-suited to a beginner-friendly track):

1. **Always try the local model first** (free — zero score cost).
2. **Score the local answer's trustworthiness** using a cheap confidence signal.
3. **Escalate to Fireworks only if confidence is low** or the answer fails validation.
4. **Log every decision** (which model, tokens used, confidence) for our own eval and for the submission's cost/accuracy tracking.

This directly optimizes the stated judging criteria: it minimizes remote (scored) token usage while protecting accuracy by escalating only the hard cases.

### Confidence / escalation signal options (pick 1 primary + 1 fallback, test both)

- **Self-reported confidence**: prompt the local model to output a structured `{answer, confidence 0-1}` and threshold on it. Simplest, fastest to build.
- **Output validation**: if the task has checkable structure (format, expected type, regex, numeric range), validate deterministically — no LLM judge needed, near-zero cost.
- **Self-consistency**: sample the local model 2-3x at low cost and check agreement; disagreement → escalate. Costs extra local tokens (free) but adds latency.
- **Verifier pass**: a second, tiny local model scores the first's answer. Still free since it's local.

Start with self-reported confidence + deterministic validation (cheapest to implement, no training needed), add self-consistency as a stretch goal if accuracy is borderline.

### Architecture

```
Task input
   │
   ▼
[Local model via Ollama] ──► answer + confidence signal
   │
   ▼
[Escalation decision] ── confidence ≥ threshold? ──► YES ──► return local answer (cost = 0)
   │
   NO
   ▼
[Fireworks AI remote model] ──► answer ──► return remote answer (cost = tokens used)
   │
   ▼
[Logger] → records: task_id, model_used, tokens, confidence, latency
```

Key components to build:

1. **Local inference wrapper** — talks to Ollama, swappable model name via config/env var.
2. **Escalation policy module** — threshold-based decision logic, isolated so it's easy to tune fast on kickoff day.
3. **Fireworks client** — thin wrapper around the Fireworks API, only called on escalation.
4. **Eval harness** — runs a batch of (placeholder now, real on kickoff) tasks end-to-end, reports accuracy and total scored tokens, so we can tune the threshold _before_ submitting.
5. **Task adapter** — one clearly-isolated place to plug in the real task format/loader once revealed — everything else should not need to change.
6. **Dockerfile** — packages the router + Ollama + dependencies so the standardized scoring environment can run it standalone.

### Suggested tech stack

- Python (router, eval harness, Fireworks client — team already knows Ollama's Python ecosystem)
- **Ollama** for local model serving (already team-familiar)
- **Fireworks AI** Python SDK or plain REST calls (`requests`) for remote escalation
- **Docker** for the required container submission
- Small, plain-Python eval harness (no need for a heavy framework at this scope)

### Local model sizing

Since the scoring env is unknown but likely constrained, prep 2-3 candidate small Ollama models spanning a size range (e.g. ~1-3B and ~7-8B class, whatever's currently pulled and working, such as Llama 3.2 3B / Qwen2.5 7B / Phi-3.5-mini-class models) so we can pick the biggest one that still fits once the real environment specs or model list are revealed on launch day. Keep the model name behind one config value.

## Team split (4 people)

- **Router/decision logic** — escalation policy module + threshold tuning
- **Local model ops** — Ollama setup, candidate model shortlist, prompt template for self-reported confidence
- **Fireworks integration** — API client, error handling/retries, token accounting
- **Eval harness + Docker** — placeholder task set, accuracy/token scoring script, Dockerfile, end-to-end test that the container runs standalone

Roles are modular by design so all 4 can work in parallel before and during the hackathon without blocking each other — they meet at the same two interfaces (local wrapper's output format, Fireworks client's input format).

## Pre-hackathon prep (before July 6)

- [ ] Get Fireworks AI API access/credits set up and do one successful test call
- [ ] Confirm Ollama is installed and pull 2-3 candidate small models
- [ ] Build the skeleton router end-to-end against **placeholder tasks** (e.g. simple Q&A, a math problem, a summarization prompt) so the pipeline (local → confidence check → escalate → log) works before real tasks exist
- [ ] Write the eval harness (accuracy scoring will need to be generic — e.g. exact match / F1 / LLM-judge-lite — until we know the real task's grading shape)
- [ ] Build the Dockerfile and confirm the container runs the whole pipeline standalone (this is a hard submission requirement, don't leave it to the last hour)
- [ ] Check hackathon Discord/docs for any hints on the standardized scoring environment's hardware specs

## Kickoff-day plan (July 6)

1. Read the real task spec and revealed model list immediately.
2. Swap the task adapter and local/remote model names into the existing skeleton — architecture should not need to change.
3. Run the eval harness against a sample of real tasks, tune the escalation threshold to the sweet spot (max local-only rate without dropping below the accuracy threshold).
4. Rebuild and test the Docker container against the real setup.
5. Submit with time buffer for container sanity-check.

## Risks / open unknowns to watch for at kickoff

- Exact accuracy threshold and grading method — unknown until launch, harness must be easy to re-point at whatever grading is used.
- Standardized environment hardware specs — unknown, keep local model swappable and prefer smaller/quantized options if unsure.
- Fireworks credit budget/limits — confirm before hackathon so escalation testing doesn't run out of credits.

## Stretch goals (only if core pipeline is solid early)

- Fine-tune a small local router/classifier instead of pure prompting (scored the same, but may be more robust) — low priority since it's not rewarded extra.
- Multi-tier cascade: tiny local model → larger local model → Fireworks remote, instead of a single local/remote split.
- Self-consistency voting for higher-confidence local answers before considering escalation.

## Verification (do this before submitting, and ideally before kickoff on the skeleton)

1. Run the eval harness end-to-end on placeholder tasks; confirm it reports both **accuracy** and **total scored (remote) tokens**, matching the two judging axes.
2. Sanity check routing behavior: trivial tasks should resolve locally (0 cost), deliberately hard/ambiguous tasks should escalate — verify this by inspecting the logger output, not just final answers.
3. Build and run the Docker container in isolation (no host Python env, no local Ollama models pre-pulled outside the container) to confirm it's actually self-contained, since containerization is a hard submission requirement.
4. Once real tasks/models are revealed, re-run steps 1-3 against the real task set before final submission.

### The simple version

Think of the system as a relay race with 5 runners, passing a baton (the task) from one to the next:

1. **Runner 1 (Local Model)** tries to answer the question for free, using a small model running on our own computer (through a tool called Ollama). It also rates how confident it is in its own answer, from 0 to 1.
2. **Runner 2 (Validators)** double-checks the answer. If the task expects a specific kind of answer (like "must be a number" or "must be yes/no"), this runner checks whether the answer actually looks right — regardless of how confident Runner 1 said it was.
3. **Runner 3 (Policy)** looks at everything so far and makes one decision: "is this answer good enough to keep, or do we need to ask a bigger, paid model?" It says yes to keeping the free answer only if there was no error, the format checks passed, AND the confidence was high enough.
4. **Runner 4 (Remote Model)** only runs if Runner 3 says the free answer isn't good enough. This runner calls a paid model through Fireworks AI, and this is the ONLY step that costs us points, since only Fireworks usage counts toward the score.
5. **Runner 5 (Logger)** writes down what happened for every single task: which model actually answered, how many tokens it cost, how confident the local model was, and whether we had to escalate. This is our paper trail for tuning and for double-checking our own results.

`main.py` is the "race organizer" — it's the file that hands the baton from one runner to the next, in order, for one task at a time.

---

## Progress Update — July 8, 2026

### What has actually been built and works right now

- **The local model connector** — talks to Ollama, asks it to answer in a strict format (an answer plus a confidence score), and cleans up messy responses (like when the model wraps its answer in unwanted formatting). If Ollama is down or times out, this piece fails safely instead of crashing the whole program.
- **The remote (Fireworks) connector** — sends a task to a real Fireworks AI model when needed, reads back the answer and exactly how many tokens it used, and retries automatically if there's a temporary problem (like a rate limit). It also refuses to call the wrong model by mistake once we know which models we're allowed to use, so we don't accidentally waste our token budget on a model that isn't allowed.
- **The validators** — a set of simple, deterministic checks (does the answer look like a number? does it match a yes/no answer? is it within a word limit?) that don't need any AI to run and cost nothing.
- **The escalation policy** — the actual rule that decides "keep the free answer" vs. "pay for a better one," based on errors, format problems, and confidence.
- **The logger** — writes one line per task into a log file, recording everything we need to check our own performance later.
- **The orchestrator (`main.py`)** — actually connects all four pieces above into one working pipeline, for one task at a time. This has been run for real on a live machine and produced a correct result (the local model answered a question with full confidence, the system kept that free answer, and it was logged correctly — proof the whole chain works end-to-end, not just in theory).

### What has been tested

We have 15 automated checks (in the `tests/` folder) that all currently pass. These checks don't need Ollama or the internet to run — they use fake, pretend responses to make sure our code reacts correctly in different situations, such as:

- The local model gives a clear, confident, well-formatted answer → keep it, don't pay.
- The local model isn't sure → send it to the paid model instead.
- The local model sounds confident but gives an answer in the wrong shape (like words instead of a number) → still send it to the paid model, because being confident doesn't mean being right.
- Ollama or Fireworks is unreachable, times out, or sends back something broken → the program doesn't crash, it just reports the problem clearly.

We also caught and fixed a sneaky bug along the way: at one point, two different people had accidentally written a function with the exact same name (`validate_format`) in the same file. Python doesn't warn you when this happens — it just silently uses the second one and ignores the first. Since the second one was unfinished, this quietly broke the whole "does the answer look right" check without giving any error message. This has been found and fixed, and all 15 checks pass again.

### What has NOT been done yet

- **`eval_harness.py` is still empty.** This is the piece that's supposed to run a whole batch of tasks at once (instead of just one, like `main.py` does) and add up the total accuracy and total paid tokens across all of them. We need this to actually measure how well our system is doing before we submit.
- **`tests/placeholder_tasks.json` is still empty.** We don't have any sample tasks written down yet to test with (things like a simple question, a math problem, a short summary). Without these, we can't run the eval harness or properly rehearse for kickoff day.
- **`tests/test_router.py` is still empty.** We have some indirect tests that touch the escalation policy, but no dedicated, focused tests just for it.
- **There is no Dockerfile yet.** The competition requires our whole project to be packaged into a container so it can run on the judges' computer without needing anything installed by hand. This has not been started at all, and it's a hard requirement — a project that works perfectly on our laptops but isn't containerized cannot be submitted.
- **A leftover test file is quietly risky.** There's a file (`tests/test_call_fireworks.py`) that was written to manually check the Fireworks connection, but because of how it's named, our test tool runs it automatically every time we run our test suite — and it makes a real, paid call to Fireworks each time. This means simply running our tests repeatedly could slowly spend real money/credits without anyone noticing. This file should be moved out of the `tests` folder (for example into a new `scripts` folder) so it only runs when someone chooses to run it on purpose.
- **A generated log file got saved into the project by accident.** Every time we run `main.py`, it creates a record of what happened in a log file. That log file has ended up being saved into our shared project folder, which isn't ideal since it will just keep changing every time anyone runs anything and will cause messy, meaningless updates. It should instead be excluded from what we share, the same way we already exclude our `.env` file (the file holding our secret API key).

### What to do next, in order of priority

1. **Move `tests/test_call_fireworks.py` out of the tests folder** so we stop accidentally spending real Fireworks credits every time someone runs our tests.
2. **Stop saving the log file into the shared project**, the same way we already keep our `.env` secret file out of it.
3. **Write `tests/placeholder_tasks.json`** — a handful of pretend tasks (a factual question, a simple math problem, a short summary request) so we have something realistic to test against before the real tasks are revealed.
4. **Build `eval_harness.py`** — loop over all the placeholder tasks, run each one through `main.py`'s pipeline, and print out a summary: how many were answered locally for free, how many needed the paid model, how many tokens were spent in total, and how many were actually correct.
5. **Write `tests/test_router.py`** — a few small, focused tests specifically for the escalation decision, on top of the tests we already have.
6. **Build the Dockerfile** — package everything (our code, our dependencies, and Ollama itself) so the whole thing can run in one self-contained box, without relying on anything already being installed on the judges' computer. This should not be left until the last minute, since it's a hard requirement for submitting at all.
7. Once the real tasks and real model list are revealed at kickoff, swap those in and re-run steps 3–6 against the real thing before final submission.
