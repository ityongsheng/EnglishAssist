import json

import httpx
import pytest

from english_assist.config import AppConfig
from english_assist.deepseek import DeepSeekClient
from english_assist.errors import AuthenticationError, InvalidResponseError, RateLimitError


def test_translate_returns_validated_replacement():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        assert request.url.path == "/chat/completions"
        assert request.headers["Authorization"] == "Bearer sk-test"
        assert body["model"] == "deepseek-v4-flash"
        assert body["thinking"] == {"type": "disabled"}
        assert body["response_format"] == {"type": "json_object"}
        assert "保持长期主义" in body["messages"][1]["content"]
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps({
                "replacement": "maintain a long-term mindset",
                "learning_phrase": "maintain a long-term mindset"
            })}}]
        })

    client = DeepSeekClient(
        AppConfig(),
        "sk-test",
        transport=httpx.MockTransport(handler),
    )
    result = client.translate("保持长期主义")
    assert result.replacement == "maintain a long-term mindset"
    assert result.source == "保持长期主义"
    assert result.learning_phrase == "maintain a long-term mindset"


def make_client(handler):
    return DeepSeekClient(AppConfig(), "sk-test", transport=httpx.MockTransport(handler))


def test_translate_rejects_empty_source():
    with pytest.raises(ValueError):
        make_client(lambda _: httpx.Response(500)).translate("   ")


def test_translate_maps_401_to_authentication_error():
    with pytest.raises(AuthenticationError):
        make_client(lambda _: httpx.Response(401, text="bad key")).translate("你好")


def test_translate_maps_429_to_rate_limit_error():
    with pytest.raises(RateLimitError):
        make_client(lambda _: httpx.Response(429, text="slow down")).translate("你好")


def test_translate_rejects_missing_replacement():
    payload = {"choices": [{"message": {"content": "{}"}}]}
    with pytest.raises(InvalidResponseError):
        make_client(lambda _: httpx.Response(200, json=payload)).translate("你好")
