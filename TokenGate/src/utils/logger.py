import json
import time
from pathlib import Path

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
    if not LOG_FILE_PATH.exists():
        return []

    with open(LOG_FILE_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def clear_logs() -> None:
    if LOG_FILE_PATH.exists():
        LOG_FILE_PATH.unlink()


class Logger:
    def log(self, source: str, task) -> None:
        task_id = task if isinstance(task, str) else task.get("task_id", "unknown")
        log_decision(
            task_id=task_id,
            model_used=source,
            tokens_used=0,
            confidence=0.0,
            escalated=(source == "remote"),
            answer=None,
        )
