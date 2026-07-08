import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.router import validators as v


def test_validate_number_basic():
    assert v.validate_number("42") is True
    assert v.validate_number("3.14") is True
    assert v.validate_number("  99 ") is True
    assert v.validate_number("forty-two") is False
    assert v.validate_number("") is False
    assert v.validate_number("42 or 43") is False


def test_validate_number_range():
    assert v.validate_number("50", min_value=0, max_value=100) is True
    assert v.validate_number("150", min_value=0, max_value=100) is False
    assert v.validate_number("-5", min_value=0) is False


def test_validate_regex_full_match():
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    assert v.validate_regex("2026-07-08", pattern) is True
    assert v.validate_regex("The date is 2026-07-08.", pattern) is False
    assert v.validate_regex("not a date", pattern) is False


def test_validate_regex_bad_pattern_fails_closed():
    assert v.validate_regex("x", "(unclosed") is False


def test_validate_choice():
    assert v.validate_choice("yes", ["yes", "no"]) is True
    assert v.validate_choice("Yes", ["yes", "no"]) is True  # case-insensitive default
    assert v.validate_choice("Yes", ["yes", "no"], case_sensitive=True) is False
    assert v.validate_choice("maybe", ["yes", "no"]) is False


def test_validate_length():
    assert v.validate_length("one two three", min_words=1, max_words=5) is True
    assert v.validate_length("one two three four five six", max_words=5) is False
    assert v.validate_length("", max_words=5) is False


def test_validate_format_dispatch():
    assert v.validate_format("anything", None) is True
    assert v.validate_format("42", {"type": "number", "min": 0, "max": 100}) is True
    assert v.validate_format("abc", {"type": "number"}) is False
    assert v.validate_format("no", {"type": "choice", "choices": ["yes", "no"]}) is True
    assert v.validate_format("short text", {"type": "length", "max_words": 10}) is True
    assert v.validate_format("anything", {"type": "some_future_type"}) is True  # fails open


def test_validate_format_integration_with_policy():
    """
    The key scenario validators.py exists for: a model can be highly
    confident AND still be structurally wrong. Confidence alone would
    miss this — validators.py catches it.
    """
    from src.router.policy import should_escalate

    local_response = {
        "answer": "forty-five",
        "confidence": 0.9,  # high confidence!
        "is_valid_format": True,  # local_client thought the JSON was fine
        "error": None,
    }
    task_expected_format = {"type": "number"}

    structurally_valid = v.validate_format(local_response["answer"], task_expected_format)
    local_response["is_valid_format"] = local_response["is_valid_format"] and structurally_valid

    assert structurally_valid is False
    assert should_escalate(local_response) is True