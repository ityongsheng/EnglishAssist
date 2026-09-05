import json

import httpx

from .config import AppConfig
from .errors import AuthenticationError, APIError, InvalidResponseError, NetworkError, RateLimitError
from .models import TranslationResult

SYSTEM_PROMPT = """You are the translation engine inside an English writing input assistant.
Return one JSON object only. The JSON schema is:
{"replacement":"natural insertable English","learning_phrase":"short useful English phrase"}
Translate Chinese or mixed Chinese-English into natural, modern English that can be inserted directly at the user's caret. Preserve meaning and tone. Prefer idiomatic English over literal translation. Preserve useful existing English. Do not add explanations, labels, quotes, markdown, or commentary outside the JSON object.
"""


class DeepSeekClient:
    def __init__(self, config: AppConfig, api_key: str, transport=None):
        self.config = config
        self.api_key = api_key
        self.client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            transport=transport,
        )

    def translate(self, source: str) -> TranslationResult:
        source = source.strip()
        if not source:
            raise ValueError("source must not be empty")

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": source},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 256,
        }
        try:
            response = self.client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise NetworkError("DeepSeek request timed out") from exc
        except httpx.HTTPError as exc:
            raise NetworkError("DeepSeek network request failed") from exc

        if response.status_code == 401:
            raise AuthenticationError("DeepSeek rejected the API key")
        if response.status_code == 429:
            raise RateLimitError("DeepSeek rate limit reached")
        if response.status_code >= 400:
            raise APIError(f"DeepSeek returned HTTP {response.status_code}")

        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            replacement = parsed["replacement"].strip()
            learning_phrase = str(parsed.get("learning_phrase") or replacement).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise InvalidResponseError("DeepSeek returned malformed JSON") from exc

        if not replacement:
            raise InvalidResponseError("DeepSeek returned an empty replacement")
        if replacement.startswith("```") or replacement.endswith("```"):
            raise InvalidResponseError("DeepSeek returned markdown instead of insertable text")

        return TranslationResult(source, replacement, learning_phrase, self.config.model)
