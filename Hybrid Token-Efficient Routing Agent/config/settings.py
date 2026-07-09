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
REMOTE_TIMEOUT_SECONDS = float(os.getenv("REMOTE_TIMEOUT_SECONDS", 30))
REMOTE_MAX_RETRIES = int(os.getenv("REMOTE_MAX_RETRIES", 2))

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