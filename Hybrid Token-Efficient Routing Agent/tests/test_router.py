import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.policy import Policy
from src.models.local_client import LocalClient
from src.models.remote_client import RemoteClient


def _low_confidence_local_result():
    return {"answer": "unsure", "confidence": 0.1, "is_valid_format": True, "error": None}


def test_escalation_uses_category_model_name():
    with patch("src.router.policy.ALLOWED_MODELS", ["kimi-k2p7-code", "minimax-m3"]):
        with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
            with patch.object(RemoteClient, "generate", return_value={
                "answer": "def foo(): pass", "tokens_used": 42, "model": "kimi-k2p7-code", "error": None,
            }) as mock_generate:
                router = Policy()
                result = router.route("Debug this Python function that raises a syntax error")

    assert result["model_used"] == "kimi-k2p7-code"
    assert mock_generate.call_args.kwargs["model_name"] == "kimi-k2p7-code"


def test_escalation_falls_back_when_mapped_model_not_allowed():
    with patch("src.router.policy.ALLOWED_MODELS", ["gemma-4-31b-it"]):
        with patch("src.router.policy.REMOTE_MODEL_NAME", "gemma-4-31b-it"):
            with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
                with patch.object(RemoteClient, "generate", return_value={
                    "answer": "n/a", "tokens_used": 10, "model": "gemma-4-31b-it", "error": None,
                }) as mock_generate:
                    router = Policy()
                    result = router.route("Debug this Python function that raises a syntax error")

    # classify_task picks "code" -> kimi-k2p7-code, but it's not in this
    # run's ALLOWED_MODELS -- must fall back to REMOTE_MODEL_NAME
    assert result["model_used"] == "gemma-4-31b-it"
    assert mock_generate.call_args.kwargs["model_name"] == "gemma-4-31b-it"


def test_escalation_unmatched_category_uses_default_model():
    with patch("src.router.policy.ALLOWED_MODELS", []):
        with patch("src.router.policy.REMOTE_MODEL_NAME", "gemma-4-31b-it"):
            with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
                with patch.object(RemoteClient, "generate", return_value={
                    "answer": "n/a", "tokens_used": 10, "model": "gemma-4-31b-it", "error": None,
                }) as mock_generate:
                    router = Policy()
                    result = router.route("zzz qwerty asdf")

    assert result["model_used"] == "gemma-4-31b-it"
    assert mock_generate.call_args.kwargs["model_name"] == "gemma-4-31b-it"


def test_budget_task_cap_forces_local_fallback():
    long_prompt = "x " * 5000  # ~2500 estimated tokens, over the 2000 default cap
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate") as mock_generate:
            router = Policy()
            result = router.route(long_prompt)

    mock_generate.assert_not_called()
    assert result["model_used"] == "local"
    assert result["answer"] == "unsure"
    assert result["escalated"] is False


def test_budget_global_cap_forces_local_fallback():
    # NOTE: brief specified MAX_REMOTE_TOKENS_BUDGET=10 here, but
    # estimate_tokens("short prompt") == 3 and 5 + 3 = 8 does not exceed 10,
    # so that literal value never actually exercises the global-budget
    # branch. Using 7 instead so 5 + 3 = 8 > 7 trips it, preserving the
    # test's intent (see task-3-report.md for details).
    with patch("src.router.policy.MAX_REMOTE_TOKENS_BUDGET", 7):
        with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
            with patch.object(RemoteClient, "generate") as mock_generate:
                router = Policy()
                router.remote_tokens_spent = 5
                result = router.route("short prompt")

    mock_generate.assert_not_called()
    assert result["model_used"] == "local"


def test_budget_disabled_by_default_allows_remote():
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate", return_value={
            "answer": "ok", "tokens_used": 50, "model": "whatever", "error": None,
        }) as mock_generate:
            router = Policy()
            router.remote_tokens_spent = 999999  # would blow any real budget, but MAX_REMOTE_TOKENS_BUDGET defaults to 0 (unlimited)
            result = router.route("short prompt")

    mock_generate.assert_called_once()
    assert result["escalated"] is True


def test_remote_tokens_spent_accumulates_across_calls():
    with patch.object(LocalClient, "run_local", return_value=_low_confidence_local_result()):
        with patch.object(RemoteClient, "generate", return_value={
            "answer": "ok", "tokens_used": 50, "model": "whatever", "error": None,
        }):
            router = Policy()
            router.route("short prompt one")
            router.route("short prompt two")

    assert router.remote_tokens_spent == 100
