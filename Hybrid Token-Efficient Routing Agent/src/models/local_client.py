"""
Ollama connector & prompt template.

Exposes the single interface the rest of the team builds against:

    from src.models.local_client import query_local
    result = query_local(task_input)
    # {
    #     "answer": str,
    #     "confidence": float,
    #     "reasoning": str,
    #     "raw_response": str,
    #     "model": str,
    #     "latency_ms": float,
    #     "parse_ok": bool,
    # }

Design goals:
- Model name swappable via config.settings.LOCAL_MODEL (env var LOCAL_MODEL).
- Never raises on a malformed model response — returns parse_ok=False and
  confidence=0.0 instead, which src/router/policy.py should treat as an
  automatic escalation signal.
- Keeps latency + raw response for src/utils/logger.py (task_id, model
  used, tokens, confidence, latency).

Hybrid fix applied on top of the original version:
  1. Requests Ollama's native "format": "json" constraint as an extra
     guardrail, on top of the prompt instructions and manual parsing.
  2. Treats an out-of-range confidence value (e.g. 5.0, or a non-numeric
     string) as a sign the response itself is unreliable -- rather than
     silently clamping it into [0,1] and returning parse_ok=True, it now
     zeroes confidence AND flips parse_ok=False, so a badly miscalibrated
     model doesn't slip past the router's escalation check unnoticed.
"""

import json
import re
import time

import requests

from config.settings import LOCAL_MODEL_NAME as LOCAL_MODEL, OLLAMA_HOST, OLLAMA_TIMEOUT_SECONDS as LOCAL_REQUEST_TIMEOUT_S

# Prompt template (self-reported confidence)


CONFIDENCE_PROMPT_TEMPLATE = """You MUST respond with ONLY this exact JSON format. Do not include any other text, markdown, or explanation outside the JSON.

The "answer" field can be multiple lines long. Use \\n for line breaks in the answer if needed for paragraphs, lists, or multi-line content.

Example:
{{"answer": "This is a multi-line\\nanswer that can span\\nhowever many lines needed.", "confidence": 0.8, "reasoning": "your reasoning here"}}

Task: {task_input}

Rules:
- The "answer" field can be as long as needed - use multiple sentences, paragraphs, or lines separated by \\n
- The confidence MUST be a number between 0.0 and 1.0
- Use confidence >= 0.8 if you are confident the answer is correct. Simple factual questions, basic math, and well-known knowledge warrant high confidence.
- Use confidence 0.5-0.8 if you think the answer is likely correct but there's some uncertainty (e.g., multi-step reasoning, less common knowledge).
- Use confidence < 0.5 if you are genuinely unsure, guessing, or the task is ambiguous.
- Be calibrated: assign high confidence to answers you're sure about, and low confidence to answers you're unsure about.
"""


def build_prompt(task_input: str) -> str:
    """Fill the template with the actual task text."""
    return CONFIDENCE_PROMPT_TEMPLATE.format(task_input=task_input)


# JSON extraction helper

def _extract_json(text: str) -> dict | None:
    """
    Try hard to pull a JSON object out of a model response that may include
    stray text, markdown fences, or partial formatting. Small models often
    don't follow "respond with ONLY JSON" perfectly.
    """
    text = text.strip()

    # Strip markdown code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    # First attempt: parse the whole thing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Second attempt: find the first {...} block greedily
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# Main interface: run_local()

def _call_ollama(model: str, prompt: str, temperature: float) -> dict:
    """Single attempt to call Ollama and parse the response."""
    start = time.time()
    try:
        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": temperature},
            },
            timeout=LOCAL_REQUEST_TIMEOUT_S,
        )
        response.raise_for_status()
        raw_text = response.json().get("response", "")
    except requests.exceptions.RequestException as e:
        return {
            "answer": "",
            "confidence": 0.0,
            "is_valid_format": False,
            "error": f"local model request failed: {e}",
        }

    parsed = _extract_json(raw_text)

    if parsed is None:
        return {
            "answer": raw_text.strip()[:500],
            "confidence": 0.0,
            "is_valid_format": False,
            "error": "failed to parse JSON from model response",
        }

    raw_confidence = parsed.get("confidence", 0.0)
    try:
        confidence = float(raw_confidence)
        confidence_valid = 0.0 <= confidence <= 1.0
    except (TypeError, ValueError):
        confidence = 0.0
        confidence_valid = False

    if not confidence_valid:
        return {
            "answer": str(parsed.get("answer", "")),
            "confidence": 0.0,
            "is_valid_format": False,
            "error": f"model returned out-of-range or non-numeric confidence: {raw_confidence!r}",
        }

    return {
        "answer": str(parsed.get("answer", "")),
        "confidence": confidence,
        "is_valid_format": True,
        "error": None,
    }


def run_local(task_input: str, model: str = None, temperature: float = 0.2) -> dict:
    """
    Send a task to the local Ollama model and return a parsed,
    consistently-shaped result.

    On any failure (network, timeout, bad JSON, out-of-range confidence),
    retries once before giving up -- the model sometimes returns valid JSON
    in the wrong shape (e.g. {"text": "Paris"} instead of the requested
    {"answer": ..., "confidence": ..., "reasoning": ...} schema) on the
    first attempt but corrects itself on retry.

    `temperature` is exposed so policy.py can re-ask the same task at a
    different temperature as a self-consistency check.
    """
    model = model or LOCAL_MODEL
    prompt = build_prompt(task_input)

    result = _call_ollama(model, prompt, temperature)

    # Retry once on format/confidence failure (not on network errors --
    # if Ollama is unreachable, retrying won't help).
    if result.get("error") and not result.get("error", "").startswith("local model request failed"):
        retry = _call_ollama(model, prompt, temperature)
        if not retry.get("error"):
            return retry

    return result


class LocalClient:
    def __init__(self):
        self.model_name = LOCAL_MODEL

    def run_local(self, task_input: str, model: str = None, temperature: float = 0.2) -> dict:
        return run_local(task_input, model, temperature)


if __name__ == "__main__":
    import sys

    task = sys.argv[1] if len(sys.argv) > 1 else "What is 17 * 23?"
    result = run_local(task)
    print(json.dumps(result, indent=2))