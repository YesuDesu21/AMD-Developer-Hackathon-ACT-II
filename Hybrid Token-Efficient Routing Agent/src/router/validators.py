import re
import json

YES_NO_CHOICES = ["yes", "no"]


def validate_number(answer: str, min_value: float = None, max_value: float = None) -> bool:
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
    if not isinstance(answer, str):
        return False
    try:
        return re.fullmatch(pattern, answer.strip()) is not None
    except re.error:
        return False


def validate_choice(answer: str, choices: list, case_sensitive: bool = False) -> bool:
    if not isinstance(answer, str) or not answer.strip():
        return False

    text = answer.strip()
    if case_sensitive:
        return text in choices
    return text.lower() in [str(c).lower() for c in choices]


def validate_length(answer: str, min_words: int = None, max_words: int = None) -> bool:
    if not isinstance(answer, str) or not answer.strip():
        return False

    word_count = len(answer.strip().split())
    if min_words is not None and word_count < min_words:
        return False
    if max_words is not None and word_count > max_words:
        return False
    return True


def validate_format(answer: str, format_spec: dict = None) -> bool:
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

    return True


class Validators:

    @staticmethod
    def extract_confidence(response) -> float:
        if isinstance(response, dict):
            return response.get("confidence", 0.0)

        try:
            data = json.loads(response)
            return data.get("confidence", 0.0)
        except (json.JSONDecodeError, TypeError):
            return 0.0

    @staticmethod
    def validate_format(answer: str, format_spec: dict = None) -> bool:
        return validate_format(answer, format_spec)
