# Regex, schema, and structural format checks

"""
validators.py
--------------
Deterministic, task-aware checks on a model's *answer content* — separate
from local_client.py's job, which only checks whether the model returned
well-formed JSON with the right fields.

Why this exists (from the team writeup's "Output validation" idea):
self-reported confidence is cheap but can be wrong — a model can be
confidently incorrect. If a task has any checkable structure (a number,
a date, one of a fixed set of choices, a regex-matchable pattern), we can
verify the answer deterministically at zero cost, with no LLM judge
needed. This is a stronger, more trustworthy signal than confidence
alone, so it should be combined with it, not replace it.

How this plugs into the pipeline:
    task = {"prompt": "...", "expected_format": {"type": "number", "min": 0, "max": 100}}
    local_response = local_client.run_local(task["prompt"])
    structurally_valid = validators.validate_format(
        local_response["answer"], task.get("expected_format")
    )
    local_response["is_valid_format"] = (
        local_response["is_valid_format"] and structurally_valid
    )
    escalate = policy.should_escalate(local_response)

If a task has no "expected_format" (e.g. open-ended Q&A or summarization,
where there's nothing deterministic to check), validate_format() simply
returns True and the escalation decision falls back to confidence alone.
"""

import re

# Reasonable default choices for a yes/no style task, exposed as a constant
# so callers can reuse it without retyping the list.
YES_NO_CHOICES = ["yes", "no"]


def validate_number(answer: str, min_value: float = None, max_value: float = None) -> bool:
    """
    True if `answer` parses as a number (int or float), optionally within
    [min_value, max_value] inclusive when those bounds are given.

    Accepts surrounding whitespace and a leading +/- sign. Rejects empty
    strings, words, or multiple numbers ("42 or 43" is NOT a clean number).
    """
    if not isinstance(answer, str) or not answer.strip():
        return False

    text = answer.strip()
    try:
        value = float(text)
    except ValueError:
        return False

    if min_value is not None and value < min_value:
        return False
    if max_value is not None and value > max_value:
        return False
    return True


def validate_regex(answer: str, pattern: str) -> bool:
    """
    True if `answer` fully matches `pattern` (via re.fullmatch).

    Full-match rather than search is intentional: a task expecting e.g. a
    date "YYYY-MM-DD" shouldn't pass just because a valid date is buried
    inside a longer sentence — that's a sign the model didn't follow the
    "answer only" instruction, which is itself worth flagging as invalid.
    """
    if not isinstance(answer, str):
        return False
    try:
        return re.fullmatch(pattern, answer.strip()) is not None
    except re.error:
        # A broken pattern is a task-definition bug, not a model failure —
        # fail closed (invalid) rather than raise, so one bad task can't
        # crash the whole batch run in eval_harness.py.
        return False


def validate_choice(answer: str, choices: list, case_sensitive: bool = False) -> bool:
    """
    True if `answer` (after stripping whitespace) exactly equals one of
    `choices`. Case-insensitive by default since models are inconsistent
    about capitalization ("Yes" vs "yes") and that's not a meaningful error.
    """
    if not isinstance(answer, str) or not answer.strip():
        return False

    text = answer.strip()
    if case_sensitive:
        return text in choices
    return text.lower() in [str(c).lower() for c in choices]


def validate_length(answer: str, min_words: int = None, max_words: int = None) -> bool:
    """
    True if the word count of `answer` falls within [min_words, max_words].

    Useful for summarization-style tasks ("summarize in under 50 words")
    where exact content can't be checked deterministically, but a length
    constraint is still a hard, checkable structural requirement.
    """
    if not isinstance(answer, str) or not answer.strip():
        return False

    word_count = len(answer.strip().split())
    if min_words is not None and word_count < min_words:
        return False
    if max_words is not None and word_count > max_words:
        return False
    return True


def validate_format(answer: str, format_spec: dict = None) -> bool:
    """
    Dispatches to the right validator based on format_spec["type"].

    format_spec examples:
        None                                            -> no check, True
        {"type": "number"}
        {"type": "number", "min": 0, "max": 100}
        {"type": "regex", "pattern": r"^\\d{4}-\\d{2}-\\d{2}$"}
        {"type": "choice", "choices": ["yes", "no"]}
        {"type": "choice", "choices": ["A", "B", "C", "D"], "case_sensitive": True}
        {"type": "length", "max_words": 50}

    Returns:
        bool: True if the task has no format_spec (nothing to check, or an
        unrecognized type — fails open so a task-definition typo doesn't
        wrongly force every answer to escalate), or if `answer` satisfies
        the spec. False otherwise.
    """
    if not format_spec:
        return True

    format_type = format_spec.get("type")

    if format_type == "number":
        return validate_number(
            answer,
            min_value=format_spec.get("min"),
            max_value=format_spec.get("max"),
        )

    if format_type == "regex":
        pattern = format_spec.get("pattern")
        if not pattern:
            return True
        return validate_regex(answer, pattern)

    if format_type == "choice":
        choices = format_spec.get("choices", [])
        if not choices:
            return True
        return validate_choice(
            answer,
            choices,
            case_sensitive=format_spec.get("case_sensitive", False),
        )

    if format_type == "length":
        return validate_length(
            answer,
            min_words=format_spec.get("min_words"),
            max_words=format_spec.get("max_words"),
        )

    # Unknown/unsupported type on kickoff day's real task format:
    # fail open rather than silently forcing every task to escalate.
    return True


# NOTE: an `extract_confidence()` and a second `validate_format()` were
# added here at one point and have been removed. Two problems with them:
#   1. `validate_format` was already defined above (line ~118) and fully
#      implemented/tested. Defining it a second time in the same file
#      doesn't raise an error in Python -- the second definition silently
#      REPLACES the first one. Every call to validators.validate_format()
#      was returning None (from the stub's bare `pass`) instead of doing
#      real validation, breaking the escalation pipeline invisibly.
#   2. `extract_confidence()` isn't needed as a separate step: confidence
#      is already parsed straight out of the model's JSON response inside
#      local_client.run_local() -> local_response["confidence"]. There's
#      no separate raw-string parsing step left to do here.
# If a teammate wants to add confidence-extraction logic for some other
# input shape, give it a distinct name (e.g. extract_confidence_from_text)
# so it can't collide with an existing function again.