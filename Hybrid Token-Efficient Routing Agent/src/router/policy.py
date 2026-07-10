from config.settings import (
    ALLOWED_MODELS,
    CATEGORY_MODEL_MAP,
    CONFIDENCE_THRESHOLD,
    MAX_REMOTE_TOKENS_BUDGET,
    MAX_TASK_PROMPT_TOKENS_ESTIMATE,
    REMOTE_MODEL_NAME,
)
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient
from src.router.budget import estimate_tokens
from src.router.classifier import classify_task
from src.router.validators import Validators, answers_agree
from src.utils.logger import log_decision

# Second sample's temperature for the self-consistency check below -- high
# enough to actually get an independent sample (the first call uses 0.2,
# close to deterministic) without being so high the model rambles off-topic.
CONSISTENCY_CHECK_TEMPERATURE = 0.7


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
        self.remote_tokens_spent = 0

    def route(self, task):
        task_id = task if isinstance(task, str) else task.get("task_id", "unknown")

        local_result = self.local_client.run_local(task)

        local_answer = local_result.get("answer", "")
        confidence = self.validators.extract_confidence(local_result)
        format_ok = self.validators.validate_format(local_answer)

        if confidence >= self.threshold and format_ok:
            # Self-consistency check: a single sample can self-report high
            # confidence while still being confidently wrong (seen directly
            # on trick questions like "kilogram of feathers vs steel", where
            # the model reported 1.0 confidence on a wrong answer). Re-ask at
            # a different temperature; if the two independent samples don't
            # agree, that's real uncertainty the self-reported number missed
            # -- fall through to remote instead of trusting the first answer.
            check_result = self.local_client.run_local(task, temperature=CONSISTENCY_CHECK_TEMPERATURE)
            check_answer = check_result.get("answer", "")
            consistent = not check_result.get("error") and answers_agree(local_answer, check_answer)

            if consistent:
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

        category = classify_task(task)
        model_name = CATEGORY_MODEL_MAP.get(category, REMOTE_MODEL_NAME)
        if ALLOWED_MODELS and model_name not in ALLOWED_MODELS:
            model_name = REMOTE_MODEL_NAME

        estimated = estimate_tokens(task)
        over_task_cap = estimated > MAX_TASK_PROMPT_TOKENS_ESTIMATE
        over_budget = (
            MAX_REMOTE_TOKENS_BUDGET > 0
            and self.remote_tokens_spent + estimated > MAX_REMOTE_TOKENS_BUDGET
        )

        if over_task_cap or over_budget:
            reason = "task cap" if over_task_cap else "budget"
            log_decision(task_id=task_id, model_used="local", tokens_used=0,
                         confidence=confidence, escalated=False, answer=local_answer,
                         error=f"remote skipped: {reason} exceeded")
            return {
                "answer": local_answer,
                "model_used": "local",
                "confidence": confidence,
                "tokens_used": 0,
                "escalated": False,
                "error": None,
            }

        remote_result = self.remote_client.generate(task, model_name=model_name)
        remote_answer = remote_result.get("answer", "") if isinstance(remote_result, dict) else str(remote_result)
        remote_tokens = remote_result.get("tokens_used", 0) if isinstance(remote_result, dict) else 0
        error = remote_result.get("error") if isinstance(remote_result, dict) else None
        self.remote_tokens_spent += remote_tokens

        log_decision(task_id=task_id, model_used=model_name, tokens_used=remote_tokens,
                     confidence=confidence, escalated=True, answer=remote_answer, error=error)
        return {
            "answer": remote_answer,
            "model_used": model_name,
            "confidence": confidence,
            "tokens_used": remote_tokens,
            "escalated": True,
            "error": error,
        }
