# (Eval teammate) Logs task_id, model used, tokens, confidence

# (Eval teammate) Logs task_id, model used, tokens, confidence
"""
logger.py
---------
Logs every routing decision (one per task) so we can:
  - Verify correct behavior during dev/testing (inspect which tasks
    escalated and why, instead of only looking at final answers)
  - Feed eval_harness.py to compute accuracy vs. total scored tokens

Each call to log_decision() appends one JSON object as a single line
(JSONL format) to LOG_FILE_PATH. JSONL (rather than one big JSON array)
is used so:
  - a crash mid-run doesn't corrupt already-logged entries
  - eval_harness.py can stream/parse line-by-line without loading
    everything into memory at once
"""

import json
import time
from pathlib import Path

# Resolves to <repo_root>/logs/run_log.jsonl regardless of which directory
# a script is run from -- mirrors the same parents[2] pattern used in
# config/settings.py to find the repo root .env file.
LOG_FILE_PATH = Path(__file__).resolve().parents[2] / "logs" / "run_log.jsonl"


def log_decision(
    task_id: str,
    model_used: str,
    tokens_used: int,
    confidence: float,
    escalated: bool,
    answer: str = None,
    error: str = None,
) -> dict:
    """
    Appends one routing decision to the log file.

    Args:
        task_id: identifier for the task (from the task definition).
        model_used: which model actually produced the final answer
            (LOCAL_MODEL_NAME if not escalated, or the Fireworks model
            name if escalated).
        tokens_used: scored tokens spent on this task. 0 if answered
            locally, since local tokens are free per the competition rules.
        confidence: the local model's self-reported confidence for this
            task (logged even when escalated, since it's useful for
            tuning CONFIDENCE_THRESHOLD later).
        escalated: whether this task was escalated to Fireworks.
        answer: the final answer returned to the caller (local or remote).
        error: any error string from local_client/remote_client, if the
            task failed outright.

    Returns:
        dict: the exact entry that was written, in case the caller
        (e.g. main.py) wants to print/inspect it immediately.
    """
    entry = {
        "timestamp": time.time(),
        "task_id": task_id,
        "model_used": model_used,
        "tokens_used": tokens_used,
        "confidence": confidence,
        "escalated": escalated,
        "answer": answer,
        "error": error,
    }

    LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return entry


def read_logs() -> list:
    """
    Reads back every logged entry as a list of dicts, in the order they
    were written. Used by eval_harness.py to compute total scored tokens
    and accuracy across a batch run. Returns an empty list if no runs
    have been logged yet (rather than raising), so a fresh checkout
    doesn't crash on first import.
    """
    if not LOG_FILE_PATH.exists():
        return []

    with open(LOG_FILE_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def clear_logs() -> None:
    """
    Deletes the log file. Useful at the start of a fresh eval_harness.py
    run so results from a previous run don't get mixed into new totals.
    """
    if LOG_FILE_PATH.exists():
        LOG_FILE_PATH.unlink()


if __name__ == "__main__":
    # Quick manual smoke test:  python -m src.utils.logger
    clear_logs()
    log_decision(
        task_id="demo-1",
        model_used="gemma2:9b",
        tokens_used=0,
        confidence=0.95,
        escalated=False,
        answer="Paris",
    )
    log_decision(
        task_id="demo-2",
        model_used="accounts/fireworks/models/gpt-oss-20b",
        tokens_used=42,
        confidence=0.3,
        escalated=True,
        answer="Paris",
    )
    print(json.dumps(read_logs(), indent=2))