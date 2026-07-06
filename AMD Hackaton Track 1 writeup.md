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
4. **Eval harness** — runs a batch of (placeholder now, real on kickoff) tasks end-to-end, reports accuracy and total scored tokens, so we can tune the threshold *before* submitting.
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
