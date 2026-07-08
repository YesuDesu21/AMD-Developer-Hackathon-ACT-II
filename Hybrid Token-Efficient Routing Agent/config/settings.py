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