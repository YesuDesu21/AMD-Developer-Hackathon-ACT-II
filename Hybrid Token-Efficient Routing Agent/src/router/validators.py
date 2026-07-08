# Regex, schema, and structural format checks



def extract_confidence(response: str) -> float:
    """
     parses the local model's structured output (e.g. {"answer":"...", "confidence":0.85}) to get self-reported confidence. Returns a default (say 0.0 or 0.5) if parsing fails.
    """
    pass

def validate_format(response: str, task_type: str = None) -> bool:
    """
    deterministic structural checks (non-empty, matches expected pattern, etc.).
    Configurable per task type.
    """
    pass
