from types import SimpleNamespace

from .errors import ConfigurationError

try:
    import keyring as _keyring
except ModuleNotFoundError:
    def _missing(*_args, **_kwargs):
        raise ConfigurationError("Python keyring dependency is not installed")
    keyring = SimpleNamespace(get_password=_missing, set_password=_missing)
else:
    keyring = _keyring

SERVICE = "EnglishAssist"
ACCOUNT = "DeepSeekAPIKey"


def get_deepseek_api_key() -> str:
    value = keyring.get_password(SERVICE, ACCOUNT)
    if not value or not value.strip():
        raise ConfigurationError("DeepSeek API key is not configured")
    return value.strip()


def set_deepseek_api_key(value: str) -> None:
    value = value.strip()
    if not value:
        raise ConfigurationError("DeepSeek API key cannot be empty")
    keyring.set_password(SERVICE, ACCOUNT, value)
