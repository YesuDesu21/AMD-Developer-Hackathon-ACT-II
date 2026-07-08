"""
main.py
-------
The orchestrator: ties local_client -> validators -> policy -> remote_client
-> logger together into one runnable pipeline for a single task.

NOTE: an earlier version of this file imported Policy/Validators/LocalClient/
RemoteClient/Logger as classes. None of those classes exist anywhere in the
codebase -- every module in src/ exposes plain functions (should_escalate,
validate_format, run_local, run_remote, log_decision), not classes. That
version couldn't even be imported. This version calls the real functions.

Pipeline for one task:
    task = {"task_id": str, "prompt": str, "expected_format": dict or None}

    1. local_client.run_local(prompt)
         -> {"answer", "confidence", "is_valid_format", "error"}
    2. validators.validate_format(answer, expected_format)
         -> combined (AND) into is_valid_format, since local_client only
            checks "is this valid JSON with the right fields", not
            "does the answer match what THIS task expects"
    3. policy.should_escalate(local_response)
         -> True/False
    4. If True: remote_client.run_remote(prompt) for the authoritative answer
       If False: keep the local answer (cost = 0)
    5. logger.log_decision(...) records the outcome either way
"""

from config.settings import LOCAL_MODEL_NAME
from src.models.local_client import run_local
from src.models.remote_client import run_remote
from src.router.policy import should_escalate
from src.router.validators import validate_format
from src.utils.logger import log_decision


def run_task(task: dict) -> dict:
    """
    Runs a single task through the full cascade router and logs the
    outcome.

    Args:
        task: {
            "task_id": str,
            "prompt": str,
            "expected_format": dict or None   # see validators.validate_format
        }

    Returns:
        dict: {
            "task_id": str,
            "answer": str,
            "model_used": str,
            "tokens_used": int,      # 0 if answered locally
            "escalated": bool,
            "confidence": float,     # the LOCAL model's self-reported confidence
        }
    """
    task_id = task.get("task_id", "unknown")
    prompt = task["prompt"]
    expected_format = task.get("expected_format")

    # Step 1: always try local first (free).
    local_response = run_local(prompt)

    # Step 2: layer in task-specific structural validation. local_client's
    # own is_valid_format only checks "did the model return well-formed
    # JSON with the fields we need" -- it knows nothing about what THIS
    # task expects the answer to look like. Combine both with AND.
    structurally_valid = validate_format(local_response.get("answer", ""), expected_format)
    local_response["is_valid_format"] = (
        local_response.get("is_valid_format", True) and structurally_valid
    )

    # Step 3: decide whether to escalate.
    escalated = should_escalate(local_response)

    # Step 4: escalate to Fireworks if needed, otherwise keep the local answer.
    if escalated:
        remote_response = run_remote(prompt)
        final_answer = remote_response["answer"]
        model_used = remote_response["model"]
        tokens_used = remote_response["tokens_used"]
        error = remote_response["error"]
    else:
        final_answer = local_response["answer"]
        model_used = LOCAL_MODEL_NAME
        tokens_used = 0  # local tokens are free per the competition rules
        error = local_response["error"]

    # Step 5: log the decision regardless of outcome.
    log_decision(
        task_id=task_id,
        model_used=model_used,
        tokens_used=tokens_used,
        confidence=local_response.get("confidence"),
        escalated=escalated,
        answer=final_answer,
        error=error,
    )

    return {
        "task_id": task_id,
        "answer": final_answer,
        "model_used": model_used,
        "tokens_used": tokens_used,
        "escalated": escalated,
        "confidence": local_response.get("confidence"),
    }


def main():
    # Manual smoke test for a single task. Once tests/placeholder_tasks.json
    # exists, eval_harness.py should loop run_task() over the whole batch
    # instead of this hardcoded example.
    sample_task = {
        "task_id": "sample-1",
        "prompt": "What is the capital of France?",
        "expected_format": None,
    }
    result = run_task(sample_task)
    print(result)


if __name__ == "__main__":
    main()