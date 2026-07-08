import os

# Routing Configurations
# On kickoff day, you will tune this value (e.g., between 0.0 and 1.0)
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", 0.75))

# Model names (will be updated on launch day)
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "gemma2:9b")
REMOTE_MODEL_NAME = os.getenv("REMOTE_MODEL_NAME", "accounts/fireworks/models/llama-v3p1-70b-instruct")

# Ollama (local model runtime) connection settings
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", 30))

# Fireworks API
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY", "")
FIREWORKS_BASE_URL = os.getenv("FIREWORKS_BASE_URL", "https://api.fireworks.ai/inference/v1")
REMOTE_TIMEOUT_SECONDS = float(os.getenv("REMOTE_TIMEOUT_SECONDS", 30))
REMOTE_MAX_RETRIES = int(os.getenv("REMOTE_MAX_RETRIES", 2))

ALLOWED_MODELS = [
    m.strip() for m in os.getenv("ALLOWED_MODELS", "").split(",") if m.strip()
]