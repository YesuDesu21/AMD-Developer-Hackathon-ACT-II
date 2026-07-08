# (Fireworks teammate) API connector & token tracker

# (Fireworks teammate) API connector & token tracker
"""
remote_client.py
-----------------
Thin wrapper around the Fireworks AI chat-completions endpoint. This is
called ONLY when router.policy.should_escalate() returns True — every
call here is scored (real, non-zero token cost), so it needs to be
reliable, track usage accurately, and refuse to silently call a model
that isn't allowed under the competition rules.

Returned shape (deliberately different from local_client's, since the
remote answer is authoritative — there's nowhere further to escalate to,
so there's no "confidence"/"is_valid_format" gate here):

    {
        "answer": str,
        "tokens_used": int,       # total tokens billed for this call
        "model": str,             # which Fireworks model actually answered
        "error": str or None,     # network/auth/API failure, if any
    }

Design notes:
- Uses the OpenAI-compatible /chat/completions route, which Fireworks
  supports (FIREWORKS_BASE_URL, e.g. https://api.fireworks.ai/inference/v1).
- Refuses to call any model outside config.settings.ALLOWED_MODELS when
  that list is non-empty (it's empty during pre-kickoff dev since the
  real model list isn't known yet). This exists so a stale/wrong model
  name can never accidentally burn scored tokens on a disallowed model.
- Retries on transient failures (timeouts, connection errors, 429 rate
  limits, 5xx server errors) with exponential backoff, since these don't
  mean "the model can't do this," just "try again." Auth/client errors
  (401/403/404/400) fail immediately — retrying those wastes time and
  can't succeed without a different key/model/payload anyway.
- Every failure path returns a well-formed dict rather than raising, so
  main.py can log/handle it uniformly, same philosophy as local_client.py.
"""

import time
import requests

from config.settings import (
    ALLOWED_MODELS,
    FIREWORKS_API_KEY,
    FIREWORKS_BASE_URL,
    REMOTE_MAX_RETRIES,
    REMOTE_MODEL_NAME,
    REMOTE_TIMEOUT_SECONDS,
)

FIREWORKS_CHAT_URL = f"{FIREWORKS_BASE_URL}/chat/completions"

# Status codes worth retrying: rate limiting and transient server errors.
# Anything else (400, 401, 403, 404) is a client-side/config problem that
# will not be fixed by retrying, so we fail fast on those instead.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_model_allowed(model_name: str) -> bool:
    """
    True if ALLOWED_MODELS is empty (pre-kickoff dev, unrestricted) or if
    model_name is explicitly on the list revealed at kickoff.
    """
    if not ALLOWED_MODELS:
        return True
    return model_name in ALLOWED_MODELS


def _post_with_retries(payload: dict, headers: dict):
    """
    POSTs to Fireworks with retry/backoff on transient failures.

    Returns:
        (response, error_message) — exactly one will be non-None.
        On success: (requests.Response, None)
        On exhausted retries / non-retryable failure: (None, str)
    """
    last_error = None

    for attempt in range(REMOTE_MAX_RETRIES + 1):
        try:
            response = requests.post(
                FIREWORKS_CHAT_URL,
                json=payload,
                headers=headers,
                timeout=REMOTE_TIMEOUT_SECONDS,
            )
        except requests.exceptions.Timeout:
            last_error = f"Fireworks request timed out after {REMOTE_TIMEOUT_SECONDS}s"
        except requests.exceptions.ConnectionError as exc:
            last_error = f"Could not reach Fireworks at {FIREWORKS_BASE_URL}: {exc}"
        except requests.exceptions.RequestException as exc:
            last_error = f"Fireworks request failed: {exc}"
        else:
            if response.status_code == 200:
                return response, None

            if response.status_code not in _RETRYABLE_STATUS_CODES:
                # Non-retryable: bad API key, bad model name, malformed
                # request, etc. Fail immediately with the response body
                # so the real cause is visible in logs.
                return None, f"Fireworks API error {response.status_code}: {response.text[:300]}"

            last_error = f"Fireworks API error {response.status_code} (attempt {attempt + 1})"

        # Exponential backoff before the next attempt (0.5s, 1s, 2s, ...).
        # Skipped after the final attempt since we're about to give up.
        if attempt < REMOTE_MAX_RETRIES:
            time.sleep(0.5 * (2 ** attempt))

    return None, last_error


def run_remote(task_prompt: str, model_name: str = REMOTE_MODEL_NAME) -> dict:
    """
    Sends a task to a Fireworks-hosted remote model. This is the ONLY
    function in the whole pipeline that spends scored tokens — call it
    only after should_escalate() has returned True.

    Args:
        task_prompt: the raw task text.
        model_name: which Fireworks model to call. Must be on
            config.settings.ALLOWED_MODELS once that list is populated
            at kickoff, or the call is refused before any network request
            is made (protects your scored-token budget from typos/staleness).

    Returns:
        dict: {"answer": str, "tokens_used": int, "model": str,
               "error": str or None}
    """
    if not FIREWORKS_API_KEY:
        return {
            "answer": "",
            "tokens_used": 0,
            "model": model_name,
            "error": "FIREWORKS_API_KEY is not set",
        }

    if not _is_model_allowed(model_name):
        return {
            "answer": "",
            "tokens_used": 0,
            "model": model_name,
            "error": (
                f"Refusing to call '{model_name}': not in ALLOWED_MODELS "
                f"{ALLOWED_MODELS}. Update ALLOWED_MODELS/REMOTE_MODEL_NAME "
                f"once the kickoff-day model list is revealed."
            ),
        }

    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": task_prompt}],
    }
    headers = {
        "Authorization": f"Bearer {FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }

    response, error = _post_with_retries(payload, headers)
    if error is not None:
        return {"answer": "", "tokens_used": 0, "model": model_name, "error": error}

    try:
        body = response.json()
        answer = body["choices"][0]["message"]["content"]
        usage = body.get("usage", {})
        tokens_used = usage.get(
            "total_tokens",
            usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        )
    except (KeyError, IndexError, ValueError) as exc:
        return {
            "answer": "",
            "tokens_used": 0,
            "model": model_name,
            "error": f"Unexpected Fireworks response shape: {exc}",
        }

    return {
        "answer": answer,
        "tokens_used": tokens_used,
        "model": model_name,
        "error": None,
    }


if __name__ == "__main__":
    # Quick manual smoke test:
    #   1. export FIREWORKS_API_KEY="your-key-here"
    #   2. Run:  python -m src.models.remote_client
    # This is NOT a substitute for automated tests — it's a fast way to
    # confirm real API connectivity/auth while developing.
    import json

    sample_task = "What is the capital of France?"
    result = run_remote(sample_task)
    print(json.dumps(result, indent=2))