
# AMD Hackathon Details — Track 1: Hybrid Token-Efficient Routing Agent

Reference doc for the official rules, constraints, and announcements that shape this
track. Source: original Track 1 project brief + Discord announcements (2026-07-07 and
2026-07-08) + the official Participant Guide PDF. Cross-reference
`Team Documentation/julianna_docu.md` for what's actually been fixed/verified in the
codebase against these rules.

---
## What we're building

Build an AI agent that gets the job done using the least tokens possible. Tasks are
revealed at kickoff. The agent must complete each one autonomously by deciding in real
time whether to use a local model or call a remote model via Fireworks AI credits.

**The goal:** pick the cheapest option every time, without falling below the accuracy
threshold.

## Scoring model

- Every submission is scored on a **standardized environment** — you can develop and
  test on any hardware, but final scoring only runs on that standardized environment.
  Local models must be sized to run within its constraints, so **routing intelligence
  wins, not raw compute power**.
- **All models and tokens used locally count as zero toward the final score.**
- Recommended: run a local eval step to check output quality before submitting.
- Prompt-based and fine-tuned router approaches are scored exactly the same way —
  token count and output accuracy. Fine-tuning the router is fair game.
- Models to be used are revealed on launch day (see Allowed Models below).

| Property | Value |
|---|---|
| Level | Beginner |
| Judging | Token count and output accuracy |
| Compute | Local mode + Fireworks AI API |

## Build idea (suggested approach)

**Model Router / cost optimizer** — a routing layer that reads each query and
instantly picks the cheapest, best-suited model from the available endpoints.

---
## Announcement timeline

### 2026-07-07 — Track 1: General-Purpose AI Agent

Build an agent that handles tasks across 8 categories (factual Q&A, math reasoning,
sentiment, summarization, NER, code debugging, logic puzzles, code generation) using
Fireworks AI models. Submit a Docker image. Scored on an accuracy gate, then ranked by
token efficiency.

**Allowed models (Track 1):**
- `minimax-m3`
- `kimi-k2p7-code`
- `gemma-4-31b-it`
- `gemma-4-26b-a4b-it`
- `gemma-4-31b-it-nvfp4`

**Keep in mind (all tracks):**
- Docker images (Tracks 1 & 2) must be publicly pullable and include a `linux/amd64`
  manifest
- Image size capped at 10GB
- No hardcoded/cached answers: evaluation uses unseen variants
- Submissions are rate-limited, so test locally before repeated submits

### 2026-07-08 — Official clarification + guide updates

**Local models are a valid scoring strategy:** your container can answer tasks using a
local model; those answers count fully toward accuracy. Only tokens routed through
`FIREWORKS_BASE_URL` count toward your token score. A local model that answers a task
correctly uses zero Fireworks tokens — the best possible outcome for ranking.

**Practical limits if you're using a local model:**
- Grading environment: **4 GB RAM, 2 vCPU** — 2B–3B 4-bit quantized models fit
  comfortably; a 7B 4-bit model fills the full RAM budget, leaving no room for your
  agent code
- No Ollama or model runtime is pre-installed: **bundle model weights directly in your
  Docker image**
- Image size limit remains 10 GB compressed

**Status:** Track 1 pipeline is live and scoring normally. If a submission failed, it's
due to a specific, fixable reason — see the troubleshooting table below (now in the
participant guide).

**What's new in the participant guide:**
- *Troubleshooting: why did my submission fail?* (Track 1, after the Scoring section) —
  a table explaining exactly what each failure status means and how to fix it.
- *Practice tasks* (Track 1, after "What to submit") — illustrative example tasks (not
  the real grading set), for validating container I/O handling locally before using a
  real submission slot.

---
## Full rules reference (from the official Participant Guide)

### Container contract
1. Read tasks from `/input/tasks.json` on startup —
   `[{"task_id": "t1", "prompt": "..."}]`
2. Write results to `/output/results.json` before exiting —
   `[{"task_id": "t1", "answer": "..."}]`

### Environment variables (harness-injected — read at runtime, never hardcode)
| Variable | Description |
|---|---|
| `FIREWORKS_API_KEY` | Provided by the harness — use this key, not your own |
| `FIREWORKS_BASE_URL` | Base URL for all Fireworks API calls — must be used to configure your client |
| `ALLOWED_MODELS` | Comma-separated list of permitted Fireworks AI model IDs, published on launch day |

All API calls must go through `FIREWORKS_BASE_URL`; calls that bypass it aren't
recorded and score zero tokens. Never hardcode model IDs — read from `ALLOWED_MODELS`
at runtime.

### Rules
- Exit code 0 on success, non-zero on failure
- Maximum runtime: **10 minutes**
- Only models in `ALLOWED_MODELS` are permitted — calls to other models invalidate the
  submission
- `/output/results.json` must be valid JSON — malformed output scores zero
- Local models/tokens count as zero for the final score; all Fireworks calls must go
  through `FIREWORKS_BASE_URL`; local inference counts toward accuracy, not tokens
- Do not hardcode or cache answers — evaluation uses unseen prompt variants
- Image compressed size must not exceed **10GB** — larger images are rejected before
  pulling
- Submissions are rate-limited to **10 per hour per team**
- Grading environment: **4 GB RAM, 2 vCPU** (2B–3B 4-bit models safe; 7B 4-bit leaves no
  room for agent code)

### General rules (all tracks)
- Container must start and be ready within **60 seconds**
- Response time per request must be under **30 seconds**
- All responses must be in English
- Do not hardcode or cache answers to specific inputs
- Container images must be publicly pullable at submission time

### Image architecture requirement
The judging VM runs `linux/amd64`. Image must include a `linux/amd64` manifest or it
fails to pull and scores zero. If building on Apple Silicon:
```
docker buildx build --platform linux/amd64 --tag your-image:latest --push .
```
Standard `linux/amd64` builds (Intel/AMD, GitHub Actions) need no changes.

### Scoring
1. **Accuracy gate:** LLM-Judge evaluates each answer against expected intent.
   Submissions below the accuracy threshold are excluded from the leaderboard.
2. **Token efficiency:** submissions that pass the gate are ranked ascending by total
   tokens recorded by the judging proxy. Fewer tokens = higher rank.

Note on token counting: task prompts are identical for every team, but your own system
prompt (verbosity, formatting instructions) affects input tokens, and response length
affects output tokens. Don't over-optimize output length early — focus on routing logic
and local model choice first; output-length tuning is a good later-stage optimization.

### Troubleshooting: why did my submission fail?

| Status | What it means & how to fix it |
|---|---|
| `PULL_ERROR` | Couldn't pull your Docker image. Confirm it's public and includes a `linux/amd64` manifest. |
| `RUNTIME_ERROR` | Container ran but exited non-zero. Check container logs locally — something in your agent code crashed. |
| `TIMEOUT` | Didn't finish within the 10-minute limit. Check for hangs, infinite loops, or excessive retries. |
| `OUTPUT_MISSING` | Container exited cleanly but never wrote `/output/results.json`. Confirm your code writes this file before exiting. |
| `INVALID_RESULTS_SCHEMA` | `/output/results.json` isn't in the right format. Each entry needs both `task_id` and `answer`. |
| `MODEL_VIOLATION` | Called a Fireworks model not in the published `ALLOWED_MODELS` list. Read the list from the env var at runtime, don't hardcode it. |
| `IMAGE_TOO_LARGE` | Image is over the 10 GB compressed limit. Trim unnecessary layers/dependencies. |
| `ACCURACY_GATE_FAILED` | Container ran fine, but answers scored below the accuracy threshold — a quality issue, not infrastructure. |

**Note:** a `flagged: ZERO_API_CALLS` marker is *not* a failure — it just means the
submission made zero calls through the Fireworks proxy (e.g. a local-model-only agent),
which is a valid strategy per the local-models rule above.

---
## Where this leaves our codebase

See `Team Documentation/julianna_docu.md` for the running log of what's been checked,
fixed, and still open against these rules (I/O contract, Docker model bundling, local
model sizing, confidence threshold wiring, `REMOTE_MODEL_NAME`/`ALLOWED_MODELS`
handling). See `Team Documentation/jasper_docu.md` for module ownership and the router
file structure.
