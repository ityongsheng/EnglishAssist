import pytest

from english_assist.errors import ConfigurationError
from english_assist import keychain


def test_get_key_rejects_missing_secret(monkeypatch):
    monkeypatch.setattr(keychain.keyring, "get_password", lambda *_: None)
    with pytest.raises(ConfigurationError):
        keychain.get_deepseek_api_key()


def test_set_and_get_use_fixed_service_and_account(monkeypatch):
    calls = []
    monkeypatch.setattr(keychain.keyring, "set_password", lambda *args: calls.append(args))
    keychain.set_deepseek_api_key("sk-test")
    assert calls == [("EnglishAssist", "DeepSeekAPIKey", "sk-test")]
