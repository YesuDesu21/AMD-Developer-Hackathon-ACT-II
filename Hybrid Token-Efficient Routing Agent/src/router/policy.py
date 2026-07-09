from config.settings import CONFIDENCE_THRESHOLD
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.validators import Validators
from src.utils.logger import log_decision


def should_escalate(result: dict, threshold: float = CONFIDENCE_THRESHOLD) -> bool:
    if result.get("error"):
        return True
    if not result.get("is_valid_format", False):
        return True
    if result.get("confidence", 0.0) < threshold:
        return True
    return False


class Policy:

    def __init__(self):
        self.local_client = LocalClient()
        self.remote_client = RemoteClient()
        self.validators = Validators()
        self.threshold = CONFIDENCE_THRESHOLD

    def route(self, task):
        task_id = task if isinstance(task, str) else task.get("task_id", "unknown")

        local_result = self.local_client.run_local(task)

        local_answer = local_result.get("answer", "")
        confidence = self.validators.extract_confidence(local_result)
        format_ok = self.validators.validate_format(local_answer)

        if confidence >= self.threshold and format_ok:
            log_decision(task_id=task_id, model_used="local", tokens_used=0,
                         confidence=confidence, escalated=False, answer=local_answer)
            return {
                "answer": local_answer,
                "model_used": "local",
                "confidence": confidence,
                "tokens_used": 0,
                "escalated": False,
                "error": None,
            }

        remote_result = self.remote_client.generate(task)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None

        log_decision(task_id=task_id, model_used="remote", tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": "remote",
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
