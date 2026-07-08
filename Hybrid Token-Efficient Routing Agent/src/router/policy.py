# Core escalation logic (threshold checks)

# src/router/policy.py
from config.settings import CONFIDENCE_THRESHOLD

def should_escalate(local_response: dict) -> bool:
    """
    Analyzes the local model's response payload to determine if 
    we need to escalate to the remote Fireworks AI instance.
    
    Expected local_response format:
    {
        "answer": str,
        "confidence": float,      # Range 0.0 to 1.0
        "is_valid_format": bool,  # Programmatic structural verification
        "error": str or None      # Any execution/timeout errors
    }
    
    Returns:
        bool: True if we should escalate to Fireworks, False to keep local answer.
    """
    # Rule 1: Emergency Fallback (System crashed, timed out, or returned empty)
    if local_response.get("error") is not None or not local_response.get("answer"):
        return True

    # Rule 2: Structural / Validation failure (Hallucinated or broke schema)
    if not local_response.get("is_valid_format", True):
        return True

    # Rule 3: Confidence Score Check
    local_confidence = local_response.get("confidence", 0.0)
    if local_confidence < CONFIDENCE_THRESHOLD:
        return True

    # If all checks pass, keep the free local token answer!
    return False