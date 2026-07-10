import os
from pathlib import Path
from dotenv import load_dotenv

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_ENV_PATH)

# Routing Configurations
# On kickoff day, you will tune this value (e.g., between 0.0 and 1.0)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.75))

# Model names (will be updated on launch day)
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma2:2b")

# Ollama (local model runtime) connection settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", 30))

# Fireworks API
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
# 10s timeout x up to 2 attempts (1 retry) + backoff (~0.5s) ~= 20.5s worst
# case, comfortably under the guide's 30-second-per-response limit. The old
# defaults (30s x 3 attempts) could take up to ~91.5s worst case, which would
# blow that limit on a single escalated task.
REMOTE_TIMEOUT_SECONDS = float(os.getenv("REMOTE_TIMEOUT_SECONDS", 10))
REMOTE_MAX_RETRIES = int(os.getenv("REMOTE_MAX_RETRIES", 1))

# ALLOWED_MODELS is injected by the harness at grading time (comma-separated
# Fireworks model IDs) -- this is the source of truth for what's callable.
ALLOWED_MODELS = [
    m.strip() for m in os.getenv("ALLOWED_MODELS", "").split(",") if m.strip()
]

# REMOTE_MODEL_NAME is our own local-dev override, not something the harness
# sets. Default it to the first allowed model so a real submission always
# calls a valid model even when REMOTE_MODEL_NAME was never explicitly
# configured (the harness never injects it, and .env is not bundled into the
# image, so relying on a fixed literal here silently breaks every escalation
# during grading).
REMOTE_MODEL_NAME = os.getenv("REMOTE_MODEL_NAME") or (
    ALLOWED_MODELS[0] if ALLOWED_MODELS else "accounts/fireworks/models/gpt-oss-20b"
)

# Heuristic category -> Fireworks model map for task-based routing (added
# 2026-07-10). None of these assignments are benchmarked yet -- retune once
# the team has real per-category accuracy data. Falls back to
# REMOTE_MODEL_NAME for any category not listed here, or if the mapped model
# isn't in this run's ALLOWED_MODELS.
#
# "creative" and "factual_qa" were originally mapped to gemma-4-31b-it and
# gemma-4-26b-a4b-it respectively, but live testing against the real
# Fireworks API on 2026-07-10 got a 404 "Model not found, inaccessible,
# and/or not deployed" for both -- confirmed twice each, not a fluke. Only
# kimi-k2p7-code and minimax-m3 were confirmed actually callable. Remapped
# both broken categories to minimax-m3 (the same model REMOTE_MODEL_NAME
# already falls back to) so category routing can never be worse than no
# routing at all. Re-test the gemma models closer to kickoff in case this was
# a temporary deployment/account-provisioning issue rather than a wrong ID.
CATEGORY_MODEL_MAP = {
    "code": "kimi-k2p7-code",
    "math": "minimax-m3",
    "reasoning": "minimax-m3",
    "creative": "minimax-m3",
    "factual_qa": "minimax-m3",
}

# Token-budget guard for escalation (added 2026-07-10). Both inert by
# default -- 2000 is generous and 0 disables the global cap -- until the team
# sets these deliberately via env vars.
MAX_TASK_PROMPT_TOKENS_ESTIMATE = int(os.getenv("MAX_TASK_PROMPT_TOKENS_ESTIMATE", 2000))
MAX_REMOTE_TOKENS_BUDGET = int(os.getenv("MAX_REMOTE_TOKENS_BUDGET", 0))  # 0 = unlimited