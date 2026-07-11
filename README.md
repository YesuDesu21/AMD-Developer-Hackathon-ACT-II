# Token Gate

## Track 1: Hybrid LLM Router (Ollama + Cloud Fallback)

An intelligent, cost-optimized AI orchestration router that dynamically triages prompts between a lightweight local model (`gemma2:2b` via Ollama) and a premium cloud model (Fireworks API). Local inference costs zero tokens toward the leaderboard score; cloud escalation is reserved for tasks the local model cannot handle confidently.

---

## Team Members
- **Feil Jasper Doria** - Lead AI Engineer / Router Architecture
- **Julianna Raine Lacaden** - AI Developer / Local & Cloud model ops
- **Francie Galapate** - AI Developer / Frontend & UI/UX
- **Vincent Rafael Fajardo** - AI Developer / Prompt Complexity & Docker

---

## Project Description

The router balances token efficiency with accuracy by applying a keyword-based classifier, a local model confidence check, a self-consistency cross-check, and a format validator before deciding whether to escalate to the Fireworks API.

### Routing Pipeline

1. **Task Classification (`classifier.py`)**: Incoming prompt is categorized via keyword scoring into one of: `code`, `math`, `reasoning`, `creative`, `factual_qa`, or `general`.

2. **Token Estimation (`budget.py`)**: Rough character-based estimate to avoid exceeding per-task caps or the global remote token budget.

3. **Direct-to-Remote Shortcut**: If the category is creative/general and the *estimated answer* is long (>= 750 tokens), the task goes straight to a remote Fireworks model — these tasks benefit from the cloud model's verbosity and quality.

4. **Local Model Execution (`local_client.py`)**: Most tasks first go to the local Ollama model (`gemma2:2b`). The model is prompted to return a JSON response with `{"answer": "...", "confidence": 0.0-1.0}`.

5. **Confidence & Format Check**: If the local model's self-reported confidence is below the threshold (default 0.75) or the response isn't parseable, the task escalates to remote.

6. **Self-Consistency Check**: For math and reasoning tasks (always), or other tasks with confidence below 0.85, the prompt is re-asked at a higher temperature (0.4). If the two answers disagree, the task escalates to remote.

7. **Cloud Escalation (`remote_client.py`)**: Escalated tasks are sent to Fireworks API. The model is selected per-category (e.g., `kimi-k2p7-code` for code, `minimax-m3` for math/reasoning/creative/factual). Only models in `ALLOWED_MODELS` can be called.

8. **Budget Guard**: If the global remote token budget or per-task prompt cap would be exceeded, escalation is blocked and the local answer is returned as-is.

---

## Getting Started

### Prerequisites
- Python 3.10 or higher
- [Ollama](https://ollama.com/) installed and running locally
- Local model pulled: `ollama pull gemma2:2b`
- Fireworks API key (for cloud escalation)

### Installation

```bash
git clone https://github.com/YesuDesu21/AMD-Developer-Hackathon-ACT-II
cd TokenGate
pip install -r requirements.txt
```

### Running

**Batch mode** (reads `/input/tasks.json`, writes `/output/results.json`):
```bash
python main.py
```

**Interactive CLI evaluation**:
```bash
python eval_harness.py --interactive
```

**Streamlit UI** (requires `streamlit` installed separately):
```bash
streamlit run app.py
```

### Docker

```bash
# -- After pulling from Docker Hub
docker pull vincechilling/hybrid-router:latest

# Build with default model (gemma2:2b)
docker compose build

docker compose up -d
```

### Configuration

Key environment variables (in `.env` or docker-compose):

| Variable | Default | Description |
|----------|---------|-------------|
| `FIREWORKS_API_KEY` | — | Fireworks API key (required for remote) |
| `ALLOWED_MODELS` | — | Comma-separated Fireworks model IDs |
| `LOCAL_MODEL_NAME` | `gemma2:2b` | Local Ollama model |
| `CONFIDENCE_THRESHOLD` | `0.75` | Minimum confidence to accept local answer |
| `REMOTE_TIMEOUT_SECONDS` | `10` | Fireworks request timeout |
| `MAX_REMOTE_TOKENS_BUDGET` | `0` | Global remote token cap (0 = unlimited) |
