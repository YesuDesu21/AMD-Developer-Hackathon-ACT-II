import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from src.models import local_client as lc
from src.router.policy import should_escalate


def _mock_response(json_body):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = json_body
    return mock_resp


def test_clean_valid_json():
    body = {"response": '{"answer": "Paris", "confidence": 0.95}'}
    with patch("requests.post", return_value=_mock_response(body)):
        result = lc.run_local("What is the capital of France?")
    assert result == {
        "answer": "Paris",
        "confidence": 0.95,
        "is_valid_format": True,
        "error": None,
    }
    assert should_escalate(result) is False  # confident + valid -> stay local


def test_markdown_fenced_json():
    body = {"response": '```json\n{"answer": "4", "confidence": 0.6}\n```'}
    with patch("requests.post", return_value=_mock_response(body)):
        result = lc.run_local("What is 2+2?")
    assert result["answer"] == "4"
    assert result["is_valid_format"] is True


def test_garbage_output_is_invalid():
    body = {"response": "uhh I don't know sorry"}
    with patch("requests.post", return_value=_mock_response(body)):
        result = lc.run_local("Some hard task")
    assert result["is_valid_format"] is False
    assert should_escalate(result) is True  # invalid format -> must escalate


def test_low_confidence_escalates():
    body = {"response": '{"answer": "maybe Paris?", "confidence": 0.4}'}
    with patch("requests.post", return_value=_mock_response(body)):
        result = lc.run_local("What is the capital of France?")
    assert should_escalate(result) is True  # below threshold -> escalate


def test_confidence_out_of_range_is_invalid():
    body = {"response": '{"answer": "x", "confidence": 5}'}
    with patch("requests.post", return_value=_mock_response(body)):
        result = lc.run_local("Task")
    assert result["is_valid_format"] is False


def test_connection_error_returns_error_not_raise():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        result = lc.run_local("Anything")
    assert result["error"] is not None
    assert result["answer"] == ""
    assert should_escalate(result) is True


def test_timeout_returns_error_not_raise():
    with patch("requests.post", side_effect=requests.exceptions.Timeout()):
        result = lc.run_local("Anything")
    assert result["error"] is not None
    assert should_escalate(result) is True