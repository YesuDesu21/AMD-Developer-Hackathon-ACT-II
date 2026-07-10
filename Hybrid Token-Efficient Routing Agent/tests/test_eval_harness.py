import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_harness import print_summary


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
