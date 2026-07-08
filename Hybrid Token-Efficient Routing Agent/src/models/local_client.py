import json
import requests

from config.settings import LOCAL_MODEL_NAME, OLLAMA_HOST, OLLAMA_TIMEOUT_SECONDS


class LocalClient:

    def __init__(self):
        self.model_name = LOCAL_MODEL_NAME
        self.ollama_host = OLLAMA_HOST
        self.timeout = OLLAMA_TIMEOUT_SECONDS

        self.OLLAMA_GENERATE_URL = f"{OLLAMA_HOST}/api/generate"

        self.PROMPT_TEMPLATE = """You are a careful assistant completing a task. \
Respond with ONLY a single JSON object and nothing else — no markdown \
fences, no explanation before or after it.

The JSON object must have exactly these two fields:
- "answer": your complete answer to the task, as a string.
- "confidence": a number between 0.0 and 1.0 representing how confident \
you are that your answer is fully correct. Be honest and calibrated: \
use a LOW score (below 0.5) if the task is ambiguous, outside your \
knowledge, requires precise facts/computation you are unsure about, or \
if you are guessing. Use a HIGH score (above 0.8) only when you are sure.

Task:
{task_prompt}

JSON response:"""

    def _build_prompt(self, task_prompt: str) -> str:
        return self.PROMPT_TEMPLATE.format(task_prompt=task_prompt)

    def _extract_json_object(self, raw_text: str) -> str:
        text = raw_text.strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        return text

    def _parse_model_output(self, raw_text: str) -> dict:
        candidate = self._extract_json_object(raw_text)

        try:
            parsed = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            return {"answer": "", "confidence": 0.0, "is_valid_format": False}

        if not isinstance(parsed, dict):
            return {"answer": "", "confidence": 0.0, "is_valid_format": False}

        answer = parsed.get("answer")
        confidence = parsed.get("confidence")

        valid = (
            isinstance(answer, str)
            and answer.strip() != ""
            and isinstance(confidence, (int, float))
            and 0.0 <= float(confidence) <= 1.0
        )

        return {
            "answer": answer if isinstance(answer, str) else "",
            "confidence": float(confidence) if isinstance(confidence, (int, float)) else 0.0,
            "is_valid_format": valid,
        }

    def run_local(self, task_prompt: str, model_name: str = LOCAL_MODEL_NAME) -> dict:
        payload = {
            "model": model_name,
            "prompt": self._build_prompt(task_prompt),
            "stream": False,
            "format": "json",
        }

        try:
            response = requests.post(
                self.OLLAMA_GENERATE_URL,
                json=payload,
                timeout=OLLAMA_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout:
            return {
                "answer": "",
                "confidence": 0.0,
                "is_valid_format": False,
                "error": f"Ollama request timed out after {OLLAMA_TIMEOUT_SECONDS}s",
            }
        except requests.exceptions.ConnectionError as exc:
            return {
                "answer": "",
                "confidence": 0.0,
                "is_valid_format": False,
                "error": f"Could not reach Ollama at {OLLAMA_HOST}: {exc}",
            }
        except requests.exceptions.RequestException as exc:
            return {
                "answer": "",
                "confidence": 0.0,
                "is_valid_format": False,
                "error": f"Ollama request failed: {exc}",
            }

        try:
            body = response.json()
            raw_model_output = body.get("response", "")
        except (json.JSONDecodeError, AttributeError) as exc:
            return {
                "answer": "",
                "confidence": 0.0,
                "is_valid_format": False,
                "error": f"Ollama returned an unparseable HTTP body: {exc}",
            }

        parsed = self._parse_model_output(raw_model_output)
        parsed["error"] = None
        return parsed
