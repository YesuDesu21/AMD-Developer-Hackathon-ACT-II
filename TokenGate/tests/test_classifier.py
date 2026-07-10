import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router.classifier import classify_task


def test_code_prompt():
    assert classify_task("Debug this Python function that raises a syntax error") == "code"


def test_math_prompt_by_keyword():
    assert classify_task("Calculate the sum of 45 and 12") == "math"


def test_math_prompt_by_numeric_pattern():
    assert classify_task("What does 17 * 23 equal?") == "math"


def test_reasoning_prompt():
    assert classify_task("Explain why the sky is blue and infer the underlying cause") == "reasoning"


def test_creative_prompt():
    assert classify_task("Write a poem about the ocean") == "creative"


def test_factual_qa_prompt():
    assert classify_task("What is the capital of France?") == "factual_qa"


def test_unmatched_prompt_falls_back_to_general():
    assert classify_task("zzz qwerty asdf") == "general"
