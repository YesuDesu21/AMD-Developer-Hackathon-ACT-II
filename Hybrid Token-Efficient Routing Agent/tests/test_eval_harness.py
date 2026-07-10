import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_harness import print_summary, run_interactive
from src.router.policy import Policy


def test_print_summary_groups_by_real_model_name(capsys):
    results = [
        {"task_id": "t1", "model_used": "local", "tokens_used": 0, "correct": True, "answer": "ok", "prompt": "p", "expected": "ok"},
        {"task_id": "t2", "model_used": "kimi-k2p7-code", "tokens_used": 42, "correct": True, "answer": "ok", "prompt": "p", "expected": "ok"},
        {"task_id": "t3", "model_used": "minimax-m3", "tokens_used": 58, "correct": False, "answer": "no", "prompt": "p", "expected": "ok"},
    ]
    print_summary(results)
    captured = capsys.readouterr().out
    assert "Local answers:    1" in captured
    assert "Remote answers:   2" in captured
    assert "kimi-k2p7-code: 1" in captured
    assert "minimax-m3: 1" in captured
    assert "Remote tokens:    100" in captured


def test_interactive_stops_on_blank_input():
    with patch("builtins.input", side_effect=[""]):
        results = run_interactive()
    assert results == []


def test_interactive_stops_on_quit_keyword():
    with patch("builtins.input", side_effect=["quit"]):
        results = run_interactive()
    assert results == []


def test_interactive_records_typed_prompts():
    fake_route_result = {
        "answer": "Paris", "model_used": "local", "confidence": 0.9,
        "tokens_used": 0, "escalated": False, "error": None,
    }
    with patch("builtins.input", side_effect=["What is the capital of France?", "quit"]):
        with patch.object(Policy, "route", return_value=fake_route_result):
            results = run_interactive()

    assert len(results) == 1
    assert results[0]["prompt"] == "What is the capital of France?"
    assert results[0]["answer"] == "Paris"
    assert results[0]["model_used"] == "local"
    assert results[0]["task_id"] == "interactive_001"
