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
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_model_allowed(model_name: str) -> bool:
    if not ALLOWED_MODELS:
        return True
    return model_name in ALLOWED_MODELS


def _normalize_model_id(model_name: str) -> str:
    """
    Fireworks' API rejects bare model names (e.g. "minimax-m3") with a 404 --
    it requires the full "accounts/fireworks/models/<name>" path. The
    published ALLOWED_MODELS list uses the short announcement names, so we
    normalize here rather than trust every caller to pass the full path.
    Anything already looking like a full path (starts with "accounts/") is
    left untouched, so this is a no-op if the harness ever injects full
    paths directly.
    """
    if model_name.startswith("accounts/"):
        return model_name
    return f"accounts/fireworks/models/{model_name}"


def _post_with_retries(payload: dict, headers: dict):
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
                return None, f"Fireworks API error {response.status_code}: {response.text[:300]}"

            last_error = f"Fireworks API error {response.status_code} (attempt {attempt + 1})"

        if attempt < REMOTE_MAX_RETRIES:
            time.sleep(0.5 * (2 ** attempt))

    return None, last_error


def run_remote(task_prompt: str, model_name: str = REMOTE_MODEL_NAME) -> dict:
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
        "model": _normalize_model_id(model_name),
        "messages": [{"role": "user", "content": task_prompt}],
        "max_tokens": 2048,
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


class RemoteClient:
    def generate(self, task_prompt: str, model_name: str = REMOTE_MODEL_NAME) -> dict:
        return run_remote(task_prompt, model_name)
