# English Assist V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a macOS English-writing helper where `Option+Space` opens a Chinese popup, `Enter` sends only that fragment to DeepSeek, and the returned natural English is inserted at the original caret while the phrase is recorded locally.

**Architecture:** Hammerspoon owns global hotkeys, popup UI, input-source switching, focus restoration, clipboard preservation, and paste insertion. A Python package owns configuration, Keychain access, DeepSeek API calls, response validation, logging, and append-only phrase storage. Hammerspoon launches Python asynchronously with `hs.task`, sends user text through stdin, and records a phrase only after paste is considered successful.

**Tech Stack:** macOS 13+, Hammerspoon 1.1+, Lua, `hs.webview` + `hs.webview.usercontent`, Python 3.12, `httpx`, `keyring`, `pytest`, DeepSeek OpenAI-compatible Chat Completions API.

**Spec:** `docs/superpowers/specs/2026-09-05-english-assist-design.md`

## Global Constraints

- Global trigger is exactly `Option+Space`.
- The original document must remain unchanged while translation is pending.
- `Esc` cancels without changing the document or writing a phrase record.
- Only the popup fragment is sent to DeepSeek; never read or upload the whole document.
- API key is stored in macOS Keychain under service `EnglishAssist`, account `DeepSeekAPIKey`.
- Default model is `deepseek-v4-flash`; model remains configurable.
- DeepSeek thinking mode is disabled for V1 translation requests.
- DeepSeek JSON Output is used and validated before insertion.
- Phrase data is append-only UTF-8 JSONL at `~/EnglishAssist/data/phrases.jsonl`.
- Diagnostic log is `~/EnglishAssist/logs/app.log` and must not contain the API key or full user text by default.
- Clipboard contents are restored after successful paste as reliably as Hammerspoon supports.
- If the original target window disappears or cannot be focused, do not paste into another target.
- English is the normal writing input source; the popup temporarily switches to configured Chinese input and returns to configured English on success.
- Do not implement menu-bar analytics, iPhone/Watch, Anki, cloud sync, custom input method, continuous keystroke capture, or automatic Apple Writing Tools invocation in V1.

---

## Locked File Structure

```text
EnglishAssist/
├── pyproject.toml
├── README.md
├── src/
│   └── english_assist/
│       ├── __init__.py
│       ├── cli.py              # stdin/stdout JSON contract used by Hammerspoon
│       ├── config.py           # config loading + defaults
│       ├── deepseek.py         # HTTP request + response validation
│       ├── errors.py           # typed application errors
│       ├── keychain.py         # macOS Keychain via Python keyring
│       ├── logging_utils.py    # local sanitized diagnostics
│       ├── models.py           # TranslationResult / PhraseRecord dataclasses
│       └── storage.py          # append-only JSONL
├── tests/
│   ├── test_cli.py
│   ├── test_config.py
│   ├── test_deepseek.py
│   ├── test_keychain.py
│   ├── test_logging_utils.py
│   └── test_storage.py
├── hammerspoon/
│   ├── english_assist.lua     # state machine + OS integration
│   ├── popup.html             # popup UI + IME-safe Enter handling
│   └── init.lua.example       # one-line loader
└── scripts/
    ├── install.sh             # venv + Hammerspoon link/setup
    └── doctor.sh              # local diagnostic wrapper
```

Runtime user data is outside Git:

```text
~/EnglishAssist/
├── config/config.json
├── data/phrases.jsonl
└── logs/app.log
```

---

### Task 1: Bootstrap the Python package and configuration contract

**Files:**
- Create: `pyproject.toml`
- Create: `src/english_assist/__init__.py`
- Create: `src/english_assist/models.py`
- Create: `src/english_assist/errors.py`
- Create: `src/english_assist/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `AppConfig`, `TranslationResult`, `PhraseRecord`, and typed exceptions consumed by all later Python tasks.
- `load_config(path: Path | None = None) -> AppConfig`
- `AppConfig.runtime_root: Path` defaults to `~/EnglishAssist`.
- `AppConfig.model: str` defaults to `deepseek-v4-flash`.
- `AppConfig.base_url: str` defaults to `https://api.deepseek.com`.

- [ ] **Step 1: Write the failing configuration tests**

```python
# tests/test_config.py
import json
from pathlib import Path

from english_assist.config import load_config


def test_load_config_uses_v1_defaults(tmp_path: Path):
    cfg = load_config(tmp_path / "missing.json")
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.base_url == "https://api.deepseek.com"
    assert cfg.timeout_seconds == 15.0
    assert cfg.restore_to_english is True


def test_load_config_overrides_non_secret_values(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "model": "deepseek-v4-pro",
        "timeout_seconds": 9,
        "english_input_source": "com.apple.keylayout.ABC",
        "chinese_input_source": "com.apple.inputmethod.SCIM.ITABC",
    }), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.model == "deepseek-v4-pro"
    assert cfg.timeout_seconds == 9.0
    assert cfg.english_input_source == "com.apple.keylayout.ABC"
```

- [ ] **Step 2: Run the tests and confirm they fail because the package does not exist**

Run:

```bash
python3 -m pytest tests/test_config.py -v
```

Expected: collection/import failure for `english_assist`.

- [ ] **Step 3: Create packaging metadata and dependencies**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=75", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "english-assist"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "httpx>=0.28,<1",
  "keyring>=25,<26",
]

[project.optional-dependencies]
dev = ["pytest>=8,<9"]

[project.scripts]
english-assist = "english_assist.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Add typed shared models and errors**

```python
# src/english_assist/models.py
from dataclasses import dataclass


@dataclass(frozen=True)
class TranslationResult:
    source: str
    replacement: str
    learning_phrase: str
    model: str


@dataclass(frozen=True)
class PhraseRecord:
    timestamp: str
    source: str
    translation: str
    model: str
```

```python
# src/english_assist/errors.py
class EnglishAssistError(Exception):
    code = "english_assist_error"


class ConfigurationError(EnglishAssistError):
    code = "configuration_error"


class AuthenticationError(EnglishAssistError):
    code = "authentication_error"


class NetworkError(EnglishAssistError):
    code = "network_error"


class RateLimitError(EnglishAssistError):
    code = "rate_limit_error"


class APIError(EnglishAssistError):
    code = "api_error"


class InvalidResponseError(EnglishAssistError):
    code = "invalid_response"
```

- [ ] **Step 5: Implement configuration loading without secrets**

```python
# src/english_assist/config.py
from dataclasses import dataclass, replace
import json
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    runtime_root: Path = Path.home() / "EnglishAssist"
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: float = 15.0
    restore_to_english: bool = True
    english_input_source: str = ""
    chinese_input_source: str = ""

    @property
    def phrase_path(self) -> Path:
        return self.runtime_root / "data" / "phrases.jsonl"

    @property
    def log_path(self) -> Path:
        return self.runtime_root / "logs" / "app.log"


def default_config_path() -> Path:
    return Path.home() / "EnglishAssist" / "config" / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    path = path or default_config_path()
    cfg = AppConfig()
    if not path.exists():
        return cfg
    raw = json.loads(path.read_text(encoding="utf-8"))
    allowed = {
        "model", "base_url", "timeout_seconds", "restore_to_english",
        "english_input_source", "chinese_input_source",
    }
    updates = {k: v for k, v in raw.items() if k in allowed}
    if "timeout_seconds" in updates:
        updates["timeout_seconds"] = float(updates["timeout_seconds"])
    return replace(cfg, **updates)
```

- [ ] **Step 6: Install editable package and run the tests**

Run:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest tests/test_config.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Commit the package/config foundation**

```bash
git add pyproject.toml src/english_assist tests/test_config.py
git commit -m "feat: add english assist configuration core"
```

---

### Task 2: Add Keychain access and secret-safe logging

**Files:**
- Create: `src/english_assist/keychain.py`
- Create: `src/english_assist/logging_utils.py`
- Test: `tests/test_keychain.py`
- Test: `tests/test_logging_utils.py`

**Interfaces:**
- Produces: `get_deepseek_api_key() -> str`, `set_deepseek_api_key(value: str) -> None`.
- Produces: `build_logger(path: Path) -> logging.Logger` and `redact(text: str, secrets: tuple[str, ...] = ()) -> str`.
- Uses macOS Keychain through the `keyring` backend; no key appears in config files or example command lines.

- [ ] **Step 1: Write failing Keychain tests with monkeypatched keyring**

```python
# tests/test_keychain.py
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
```

- [ ] **Step 2: Write failing redaction tests**

```python
# tests/test_logging_utils.py
from english_assist.logging_utils import redact


def test_redact_removes_known_secret():
    assert "sk-secret" not in redact("request failed sk-secret", ("sk-secret",))


def test_redact_masks_bearer_token():
    text = redact("Authorization: Bearer abc123")
    assert "abc123" not in text
    assert "[REDACTED]" in text
```

- [ ] **Step 3: Run the tests and verify they fail**

```bash
.venv/bin/pytest tests/test_keychain.py tests/test_logging_utils.py -v
```

Expected: imports fail because the modules do not exist.

- [ ] **Step 4: Implement Keychain wrapper**

```python
# src/english_assist/keychain.py
import keyring

from .errors import ConfigurationError

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
```

- [ ] **Step 5: Implement sanitized local logging**

```python
# src/english_assist/logging_utils.py
import logging
from pathlib import Path
import re

BEARER_RE = re.compile(r"(?i)(authorization:\s*bearer\s+)[^\s]+")


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    result = BEARER_RE.sub(r"\1[REDACTED]", str(text))
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


def build_logger(path: Path) -> logging.Logger:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("english_assist")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger
```

- [ ] **Step 6: Run the focused tests**

```bash
.venv/bin/pytest tests/test_keychain.py tests/test_logging_utils.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit secure secret handling**

```bash
git add src/english_assist/keychain.py src/english_assist/logging_utils.py tests/test_keychain.py tests/test_logging_utils.py
git commit -m "feat: store deepseek key in macOS keychain"
```

---

### Task 3: Implement and validate the DeepSeek translation client

**Files:**
- Create: `src/english_assist/deepseek.py`
- Test: `tests/test_deepseek.py`

**Interfaces:**
- Consumes: `AppConfig`, `TranslationResult`, typed errors.
- Produces: `DeepSeekClient(config: AppConfig, api_key: str, transport: httpx.BaseTransport | None = None)`.
- Produces: `DeepSeekClient.translate(source: str) -> TranslationResult`.
- Request contract: `POST /chat/completions`, `response_format={"type":"json_object"}`, `thinking={"type":"disabled"}`, `max_tokens=256`.

- [ ] **Step 1: Write a happy-path mocked HTTP test**

```python
# tests/test_deepseek.py
import json
import httpx

from english_assist.config import AppConfig
from english_assist.deepseek import DeepSeekClient


def test_translate_returns_validated_replacement():
    def handler(request: httpx.Request):
        body = json.loads(request.content)
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
```

- [ ] **Step 2: Add malformed/empty/auth/rate-limit tests**

```python
# append to tests/test_deepseek.py
import pytest
from english_assist.errors import AuthenticationError, InvalidResponseError, RateLimitError


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
```

- [ ] **Step 3: Run tests and verify failure**

```bash
.venv/bin/pytest tests/test_deepseek.py -v
```

Expected: import failure for `english_assist.deepseek`.

- [ ] **Step 4: Implement the system prompt and HTTP client**

```python
# src/english_assist/deepseek.py
import json
import time
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
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidResponseError("DeepSeek returned malformed JSON") from exc
        if not replacement:
            raise InvalidResponseError("DeepSeek returned an empty replacement")
        if replacement.startswith("```") or replacement.endswith("```"):
            raise InvalidResponseError("DeepSeek returned markdown instead of insertable text")
        return TranslationResult(source, replacement, learning_phrase, self.config.model)
```

- [ ] **Step 5: Run client tests**

```bash
.venv/bin/pytest tests/test_deepseek.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit DeepSeek integration**

```bash
git add src/english_assist/deepseek.py tests/test_deepseek.py
git commit -m "feat: add validated deepseek translation client"
```

---

### Task 4: Add phrase storage and the stdin/stdout CLI transaction contract

**Files:**
- Create: `src/english_assist/storage.py`
- Create: `src/english_assist/cli.py`
- Test: `tests/test_storage.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `append_phrase(path: Path, record: PhraseRecord) -> None`.
- CLI `translate` reads plain UTF-8 source from stdin and prints one JSON object to stdout; it does **not** save a phrase.
- CLI `record` reads a JSON object from stdin and appends it; Hammerspoon calls it only after paste succeeds.
- CLI `setup-key` prompts with `getpass` and writes to Keychain.
- CLI `doctor` outputs JSON readiness without revealing the secret.

- [ ] **Step 1: Write storage tests**

```python
# tests/test_storage.py
import json
from pathlib import Path
from english_assist.models import PhraseRecord
from english_assist.storage import append_phrase


def test_append_phrase_writes_one_utf8_json_line(tmp_path: Path):
    path = tmp_path / "data" / "phrases.jsonl"
    append_phrase(path, PhraseRecord(
        timestamp="2026-09-05T16:10:32+08:00",
        source="保持长期主义",
        translation="maintain a long-term mindset",
        model="deepseek-v4-flash",
    ))
    row = json.loads(path.read_text(encoding="utf-8").strip())
    assert row["source"] == "保持长期主义"
    assert row["translation"] == "maintain a long-term mindset"
```

- [ ] **Step 2: Write CLI tests proving translation does not record prematurely**

```python
# tests/test_cli.py
import io
import json

from english_assist import cli
from english_assist.models import TranslationResult


def test_translate_stdout_is_machine_readable_and_does_not_record(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_deepseek_api_key", lambda: "sk-test")
    monkeypatch.setattr(cli, "load_config", lambda: cli.AppConfig())

    class FakeClient:
        def __init__(self, *_args, **_kwargs): pass
        def translate(self, source):
            return TranslationResult(source, "maintain a long-term mindset", "long-term mindset", "deepseek-v4-flash")

    monkeypatch.setattr(cli, "DeepSeekClient", FakeClient)
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("保持长期主义"))
    rc = cli.main(["translate"])
    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["ok"] is True
    assert payload["replacement"] == "maintain a long-term mindset"
```

- [ ] **Step 3: Run storage/CLI tests and verify failure**

```bash
.venv/bin/pytest tests/test_storage.py tests/test_cli.py -v
```

Expected: missing modules/functions.

- [ ] **Step 4: Implement append-only storage**

```python
# src/english_assist/storage.py
from dataclasses import asdict
import json
from pathlib import Path

from .models import PhraseRecord


def append_phrase(path: Path, record: PhraseRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(asdict(record), ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
        fh.flush()
```

- [ ] **Step 5: Implement CLI subcommands and exit behavior**

```python
# src/english_assist/cli.py
from datetime import datetime
import argparse
import getpass
import json
import sys

from .config import AppConfig, load_config
from .deepseek import DeepSeekClient
from .errors import EnglishAssistError
from .keychain import get_deepseek_api_key, set_deepseek_api_key
from .logging_utils import build_logger, redact
from .models import PhraseRecord
from .storage import append_phrase


def emit(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def cmd_translate() -> int:
    cfg = load_config()
    logger = build_logger(cfg.log_path)
    source = sys.stdin.read().strip()
    if not source:
        emit({"ok": False, "error": "empty_input", "message": "Enter Chinese text first."})
        return 5
    try:
        key = get_deepseek_api_key()
        result = DeepSeekClient(cfg, key).translate(source)
        logger.info("translation_success model=%s", result.model)
        emit({
            "ok": True,
            "source": result.source,
            "replacement": result.replacement,
            "learning_phrase": result.learning_phrase,
            "model": result.model,
        })
        return 0
    except EnglishAssistError as exc:
        logger.warning("translation_failure code=%s message=%s", exc.code, redact(str(exc)))
        emit({"ok": False, "error": exc.code, "message": str(exc)})
        return 2


def cmd_record() -> int:
    cfg = load_config()
    raw = json.loads(sys.stdin.read())
    append_phrase(cfg.phrase_path, PhraseRecord(
        timestamp=datetime.now().astimezone().isoformat(timespec="seconds"),
        source=str(raw["source"]),
        translation=str(raw["translation"]),
        model=str(raw["model"]),
    ))
    emit({"ok": True})
    return 0


def cmd_setup_key() -> int:
    first = getpass.getpass("DeepSeek API key: ")
    second = getpass.getpass("Repeat API key: ")
    if first != second:
        emit({"ok": False, "error": "key_mismatch"})
        return 2
    set_deepseek_api_key(first)
    emit({"ok": True})
    return 0


def cmd_doctor() -> int:
    cfg = load_config()
    try:
        get_deepseek_api_key()
        key_ready = True
    except EnglishAssistError:
        key_ready = False
    emit({
        "ok": key_ready and bool(cfg.chinese_input_source) and bool(cfg.english_input_source),
        "keychain": key_ready,
        "english_input_source": bool(cfg.english_input_source),
        "chinese_input_source": bool(cfg.chinese_input_source),
        "model": cfg.model,
    })
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["translate", "record", "setup-key", "doctor"])
    args = parser.parse_args(argv)
    return {
        "translate": cmd_translate,
        "record": cmd_record,
        "setup-key": cmd_setup_key,
        "doctor": cmd_doctor,
    }[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Add a record test and run all Python tests**

Add to `tests/test_cli.py` a test that monkeypatches `append_phrase`, sends one JSON record through stdin, and asserts exactly one call occurs.

```bash
.venv/bin/pytest -v
```

Expected: all Python tests PASS.

- [ ] **Step 7: Commit CLI/storage transaction semantics**

```bash
git add src/english_assist/storage.py src/english_assist/cli.py tests/test_storage.py tests/test_cli.py
git commit -m "feat: add translation CLI and phrase recording"
```

---

### Task 5: Build the IME-safe floating popup UI

**Files:**
- Create: `hammerspoon/popup.html`

**Interfaces:**
- JavaScript → Lua message port: `englishAssistBridge`.
- Messages:
  - `{action:"ready"}`
  - `{action:"submit", text:"..."}`
  - `{action:"cancel"}`
- Lua → JavaScript functions:
  - `window.EnglishAssist.reset()`
  - `window.EnglishAssist.setTranslating()`
  - `window.EnglishAssist.setError(message)`
  - `window.EnglishAssist.focusInput()`
- Enter must not submit while a Chinese IME composition/candidate selection is active.

- [ ] **Step 1: Create the popup with explicit composition handling**

```html
<!-- hammerspoon/popup.html -->
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html,body{margin:0;background:transparent;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
.card{box-sizing:border-box;margin:8px;padding:16px;border-radius:14px;background:rgba(28,28,30,.96);color:white;box-shadow:0 14px 40px rgba(0,0,0,.28)}
.title{font-size:13px;font-weight:600;opacity:.8;margin-bottom:10px}
textarea{box-sizing:border-box;width:100%;height:72px;resize:none;border:0;outline:0;border-radius:9px;padding:10px;font-size:17px;background:rgba(255,255,255,.10);color:white}
.status{min-height:18px;margin-top:8px;font-size:12px;opacity:.72}
.error{color:#ff9f9f}
.hint{font-size:11px;opacity:.52;margin-top:5px}
</style>
</head>
<body>
<div class="card">
  <div class="title">✦ Translate to English</div>
  <textarea id="source" autocomplete="off" spellcheck="false"></textarea>
  <div id="status" class="status"></div>
  <div class="hint">Enter Translate · Shift+Enter newline · Esc Cancel</div>
</div>
<script>
(() => {
  const input = document.getElementById('source');
  const status = document.getElementById('status');
  let composing = false;
  let busy = false;

  function post(body) {
    try { window.webkit.messageHandlers.englishAssistBridge.postMessage(body); }
    catch (_) { /* standalone visual test outside Hammerspoon */ }
  }

  input.addEventListener('compositionstart', () => composing = true);
  input.addEventListener('compositionend', () => composing = false);
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      post({action:'cancel'});
      return;
    }
    if (event.key === 'Enter' && !event.shiftKey && !composing && !event.isComposing) {
      event.preventDefault();
      if (busy) return;
      const text = input.value.trim();
      if (!text) {
        status.className = 'status error';
        status.textContent = 'Enter Chinese text first.';
        return;
      }
      busy = true;
      post({action:'submit', text});
    }
  });

  window.EnglishAssist = {
    reset() {
      busy = false;
      input.disabled = false;
      input.value = '';
      status.className = 'status';
      status.textContent = '';
      setTimeout(() => input.focus(), 0);
    },
    setTranslating() {
      busy = true;
      input.disabled = true;
      status.className = 'status';
      status.textContent = 'Translating…';
    },
    setError(message) {
      busy = false;
      input.disabled = false;
      status.className = 'status error';
      status.textContent = message || 'Translation failed. Enter to retry.';
      setTimeout(() => input.focus(), 0);
    },
    focusInput() { setTimeout(() => input.focus(), 0); }
  };
  post({action:'ready'});
})();
</script>
</body>
</html>
```

- [ ] **Step 2: Manually verify the HTML outside Hammerspoon for keyboard logic**

Open it in Safari only as a visual check. Confirm:

```text
- textarea accepts Chinese
- Shift+Enter inserts a newline
- Enter is prevented from inserting a newline
- Esc is captured
```

The JavaScript bridge will fail harmlessly in Safari because Hammerspoon's message handler is absent; visual and IME behavior are the only target of this step.

- [ ] **Step 3: Commit the popup UI**

```bash
git add hammerspoon/popup.html
git commit -m "feat: add IME-safe translation popup"
```

---

### Task 6: Implement Hammerspoon popup state, input-source switching, and async Python bridge

**Files:**
- Create: `hammerspoon/english_assist.lua`
- Create: `hammerspoon/init.lua.example`

**Interfaces:**
- Public Lua entry point: `require("english_assist").start()`.
- State values: `idle`, `editing`, `translating`, `error`.
- `Option+Space` ignored while state is `translating`; while popup is visible in `editing/error`, bring it forward rather than opening a duplicate.
- Python executable: `~/EnglishAssist/.venv/bin/python` in installed layout.
- Translation task: `python -m english_assist.cli translate`; source passed with `task:setInput(text)`.

- [ ] **Step 1: Create state/config loading and the global hotkey**

```lua
-- hammerspoon/english_assist.lua
local M = {}
local HOME = os.getenv("HOME")
local runtimeRoot = HOME .. "/EnglishAssist"
local pythonBin = runtimeRoot .. "/.venv/bin/python"
local popupHtmlPath = runtimeRoot .. "/app/hammerspoon/popup.html"
local configPath = runtimeRoot .. "/config/config.json"

local state = {
  mode = "idle",
  popup = nil,
  bridge = nil,
  targetWindow = nil,
  targetWindowID = nil,
  previousInputSource = nil,
  activeTask = nil,
  translation = nil,
}

local function readFile(path)
  local f = assert(io.open(path, "r"))
  local value = f:read("*a")
  f:close()
  return value
end

local function loadConfig()
  local f = io.open(configPath, "r")
  if not f then return {} end
  local raw = f:read("*a")
  f:close()
  return hs.json.decode(raw) or {}
end
```

Register:

```lua
local hotkey = hs.hotkey.bind({"alt"}, "space", function()
  if state.mode == "translating" then return end
  if state.popup and state.popup:isVisible() then
    state.popup:bringToFront(true)
    state.popup:hswindow():focus()
    state.popup:evaluateJavaScript("window.EnglishAssist.focusInput()")
    return
  end
  M.open()
end)
```

- [ ] **Step 2: Implement target capture and Chinese input-source activation**

```lua
local function captureTarget()
  local win = hs.window.focusedWindow()
  if not win then return false, "No focused target window." end
  state.targetWindow = win
  state.targetWindowID = win:id()
  state.previousInputSource = hs.keycodes.currentSourceID()
  return true
end

local function switchToChinese()
  local cfg = loadConfig()
  if not cfg.chinese_input_source or cfg.chinese_input_source == "" then
    return false, "Chinese input source is not configured."
  end
  if not hs.keycodes.currentSourceID(cfg.chinese_input_source) then
    return false, "Configured Chinese input source is unavailable."
  end
  return true
end
```

- [ ] **Step 3: Build the webview and bridge callback**

```lua
local function popupFrame()
  local screen = hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
  local frame = screen:frame()
  return hs.geometry.rect(frame.x + (frame.w - 520) / 2, frame.y + frame.h * 0.22, 520, 150)
end

local function ensurePopup()
  if state.popup then return end
  state.bridge = hs.webview.usercontent.new("englishAssistBridge")
  state.bridge:setCallback(function(message)
    local body = message.body or {}
    if body.action == "submit" then
      M.submit(body.text or "")
    elseif body.action == "cancel" then
      M.cancel()
    end
  end)
  state.popup = hs.webview.new(
      popupFrame(),
      {javaScriptEnabled=true, javaScriptCanOpenWindowsAutomatically=false, privateBrowsing=true},
      state.bridge
    )
    :allowTextEntry(true)
    :allowNewWindows(false)
    :windowStyle({})
    :shadow(true)
    :bringToFront(true)
    :html(readFile(popupHtmlPath))
end
```

- [ ] **Step 4: Implement `open()` and `cancel()`**

```lua
function M.open()
  local ok, err = captureTarget()
  if not ok then hs.alert.show(err); return end
  ensurePopup()
  state.mode = "editing"
  state.translation = nil
  state.popup:evaluateJavaScript("window.EnglishAssist.reset()")
  state.popup:show():bringToFront(true)
  state.popup:hswindow():focus()
  local switched, switchErr = switchToChinese()
  if not switched then
    state.mode = "error"
    state.popup:evaluateJavaScript("window.EnglishAssist.setError(" .. hs.json.encode(switchErr) .. ")")
  end
end

local function restorePreviousSource()
  if state.previousInputSource then
    hs.keycodes.currentSourceID(state.previousInputSource)
  end
end

function M.cancel()
  if state.mode == "translating" and state.activeTask and state.activeTask:isRunning() then
    state.activeTask:terminate()
  end
  if state.popup then state.popup:hide() end
  restorePreviousSource()
  if state.targetWindow then state.targetWindow:focus() end
  state.mode = "idle"
  state.activeTask = nil
  state.translation = nil
end
```

- [ ] **Step 5: Implement async `submit()` using stdin rather than command arguments**

```lua
function M.submit(text)
  text = (text or ""):match("^%s*(.-)%s*$")
  if text == "" then
    state.popup:evaluateJavaScript("window.EnglishAssist.setError('Enter Chinese text first.')")
    return
  end
  if state.mode == "translating" then return end

  state.mode = "translating"
  state.popup:evaluateJavaScript("window.EnglishAssist.setTranslating()")

  local task = hs.task.new(pythonBin, function(exitCode, stdOut, stdErr)
    state.activeTask = nil
    local decoded = hs.json.decode(stdOut or "")
    if exitCode ~= 0 or not decoded or decoded.ok ~= true then
      state.mode = "error"
      local message = decoded and decoded.message or "Translation failed. Enter to retry."
      state.popup:evaluateJavaScript("window.EnglishAssist.setError(" .. hs.json.encode(message) .. ")")
      return
    end
    state.translation = decoded
    M.finishTranslation()
  end, nil, {"-m", "english_assist.cli", "translate"})

  if not task then
    state.mode = "error"
    state.popup:evaluateJavaScript("window.EnglishAssist.setError('Could not start Python translator.')")
    return
  end
  state.activeTask = task
  task:setInput(text)
  task:start()
end
```

- [ ] **Step 6: Create the loader**

```lua
-- hammerspoon/init.lua.example
package.path = os.getenv("HOME") .. "/EnglishAssist/app/hammerspoon/?.lua;" .. package.path
require("english_assist").start()
```

And export `start()`:

```lua
function M.start()
  hs.alert.show("English Assist loaded")
  return M
end

return M
```

- [ ] **Step 7: Manual Hammerspoon checkpoint before insertion exists**

With a temporary config containing valid input-source IDs, reload Hammerspoon and verify:

```text
Option+Space -> popup appears
popup -> Chinese input source active
Esc -> popup disappears, prior app refocuses, previous input source restored
Enter -> popup shows Translating… and duplicate Enter does nothing
network/API error -> entered Chinese remains in popup and Enter can retry
```

Do not implement document paste in this checkpoint.

- [ ] **Step 8: Commit popup state and Python bridge**

```bash
git add hammerspoon/english_assist.lua hammerspoon/init.lua.example
git commit -m "feat: connect translation popup to python core"
```

---

### Task 7: Add safe target validation, clipboard-preserving insertion, English restore, and post-insert recording

**Files:**
- Modify: `hammerspoon/english_assist.lua`

**Interfaces:**
- `M.finishTranslation()` must never paste unless the original target window still exists and can be focused.
- Phrase `record` call happens only after paste has been sent to the original target.
- Clipboard snapshot uses `hs.pasteboard.readAllData()`/`writeAllData()` with text fallback.
- English source restore uses configured `english_input_source` after success; cancel uses previous source.

- [ ] **Step 1: Add target validation helpers**

```lua
local function validTargetWindow()
  if not state.targetWindowID then return nil end
  local win = hs.window.get(state.targetWindowID)
  if not win or not win:isVisible() then return nil end
  return win
end

local function switchToEnglish()
  local cfg = loadConfig()
  if cfg.restore_to_english and cfg.english_input_source and cfg.english_input_source ~= "" then
    return hs.keycodes.currentSourceID(cfg.english_input_source)
  end
  restorePreviousSource()
  return true
end
```

- [ ] **Step 2: Add complete-first-item clipboard snapshot with text fallback**

```lua
local function snapshotClipboard()
  return {
    all = hs.pasteboard.readAllData(),
    text = hs.pasteboard.getContents(),
  }
end

local function restoreClipboard(snapshot)
  if snapshot and snapshot.all and next(snapshot.all) ~= nil then
    if hs.pasteboard.writeAllData(snapshot.all) then return true end
  end
  if snapshot and snapshot.text ~= nil then
    return hs.pasteboard.setContents(snapshot.text)
  end
  return false
end
```

- [ ] **Step 3: Implement exact paste into the original target**

```lua
local function pasteReplacement(target, replacement, callback)
  local snapshot = snapshotClipboard()
  if not hs.pasteboard.setContents(replacement) then
    callback(false, "Could not write translation to clipboard.")
    return
  end

  target:focus()
  hs.timer.doAfter(0.06, function()
    if hs.window.focusedWindow() == nil or hs.window.focusedWindow():id() ~= target:id() then
      restoreClipboard(snapshot)
      callback(false, "Original target window could not be focused.")
      return
    end
    hs.eventtap.keyStroke({"cmd"}, "v", 0, target:application())
    hs.timer.doAfter(0.12, function()
      local restored = restoreClipboard(snapshot)
      callback(true, restored and nil or "Translation inserted, but clipboard restoration failed.")
    end)
  end)
end
```

V1 considers the synthetic paste dispatched successfully after the target remains focused through the paste delay. It does not attempt invasive document-content verification across every app.

- [ ] **Step 4: Implement post-insert phrase recording as a second Python task**

```lua
local function recordPhrase(translation)
  local payload = hs.json.encode({
    source = translation.source,
    translation = translation.replacement,
    model = translation.model,
  })
  local task = hs.task.new(pythonBin, function(exitCode, stdOut, stdErr)
    if exitCode ~= 0 then
      hs.notify.new({title="English Assist", informativeText="English inserted, but phrase history was not saved."}):send()
    end
  end, nil, {"-m", "english_assist.cli", "record"})
  if task then task:setInput(payload):start() end
end
```

- [ ] **Step 5: Implement the success state transition**

```lua
function M.finishTranslation()
  local translation = state.translation
  local target = validTargetWindow()
  if not target then
    state.mode = "error"
    state.popup:evaluateJavaScript("window.EnglishAssist.setError('Original target is no longer available. Translation was not inserted.')")
    return
  end

  state.popup:hide()
  switchToEnglish()
  pasteReplacement(target, translation.replacement, function(ok, warning)
    if not ok then
      state.mode = "error"
      state.popup:show():bringToFront(true)
      state.popup:evaluateJavaScript("window.EnglishAssist.setError(" .. hs.json.encode(warning) .. ")")
      return
    end
    recordPhrase(translation)
    if warning then
      hs.notify.new({title="English Assist", informativeText=warning}):send()
    end
    state.mode = "idle"
    state.translation = nil
    state.targetWindow = nil
    state.targetWindowID = nil
    state.previousInputSource = nil
  end)
end
```

- [ ] **Step 6: Add conservative spacing helper only where AX context is safely available**

Do not rewrite unrelated document text. Implement a pure helper first:

```lua
local function smartReplacement(replacement, leftChar, rightChar)
  local value = replacement
  if leftChar and leftChar:match("[%w%)]") and not value:match("^%s") then
    value = " " .. value
  end
  if rightChar and rightChar:match("[%w%(]") and not value:match("%s$") then
    value = value .. " "
  end
  if rightChar and rightChar:match("[%.%,%!%?%:%;]") then
    value = value:gsub("%s+$", "")
  end
  return value
end
```

Attempt surrounding-character inspection with Accessibility only in apps/controls where a focused element exposes a plain string value and selected text range. If either attribute is unavailable, call `pasteReplacement` with the unmodified `translation.replacement`. Do not add keyboard-based probing or deletion tricks.

- [ ] **Step 7: Manual compatibility tests**

For each target below, copy a distinctive value such as `CLIPBOARD-SENTINEL` before invoking the assistant. Verify translated text is inserted and the sentinel returns to the clipboard afterward.

```text
Apple Notes
Safari textarea/contenteditable
Chrome textarea/contenteditable
ChatGPT web composer
Notion editor
TextEdit or another native macOS text editor
```

Also verify:

```text
- Close target window while popup is open -> no paste into another app.
- Switch to another app while translating -> finish focuses only the captured original target.
- Kill network -> no document change; popup shows retry.
- Press Option+Space during translation -> no second request.
```

- [ ] **Step 8: Commit safe insertion flow**

```bash
git add hammerspoon/english_assist.lua
git commit -m "feat: insert translations safely and preserve clipboard"
```

---

### Task 8: Installer, input-source discovery, README, and end-to-end release verification

**Files:**
- Create: `scripts/install.sh`
- Create: `scripts/doctor.sh`
- Create: `README.md`
- Modify: `.gitignore` if absent

**Interfaces:**
- Installed code root: `~/EnglishAssist/app` as a symlink or copy of the repository.
- Python environment: `~/EnglishAssist/.venv`.
- Hammerspoon loader: `~/.hammerspoon/init.lua` requires installed `english_assist.lua` without replacing unrelated user config.
- Setup must help discover `hs.keycodes.layouts(true)` and `hs.keycodes.methods(true)` so actual input-source IDs are copied, never guessed.

- [ ] **Step 1: Add `.gitignore` before generating local environments**

```gitignore
.venv/
__pycache__/
.pytest_cache/
*.pyc
.DS_Store
```

- [ ] **Step 2: Create an installer that does not request unnecessary permissions**

```bash
#!/usr/bin/env bash
# scripts/install.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$HOME/EnglishAssist"
mkdir -p "$RUNTIME"/{config,data,logs}
ln -sfn "$ROOT" "$RUNTIME/app"

python3.12 -m venv "$RUNTIME/.venv"
"$RUNTIME/.venv/bin/pip" install -U pip
"$RUNTIME/.venv/bin/pip" install -e "$ROOT"

mkdir -p "$HOME/.hammerspoon"
cat <<'LUA'
Add this line to ~/.hammerspoon/init.lua if it is not already present:
package.path = os.getenv("HOME") .. "/EnglishAssist/app/hammerspoon/?.lua;" .. package.path
require("english_assist").start()
LUA

echo "Next: $RUNTIME/.venv/bin/english-assist setup-key"
echo "Then configure input source IDs and grant Hammerspoon Accessibility permission."
```

- [ ] **Step 3: Add an input-source discovery procedure to README**

The README must tell the user to open Hammerspoon Console and run:

```lua
print("Current:", hs.keycodes.currentSourceID())
print("Layouts:", hs.inspect(hs.keycodes.layouts(true)))
print("Methods:", hs.inspect(hs.keycodes.methods(true)))
```

Then create `~/EnglishAssist/config/config.json` using exact returned IDs:

```json
{
  "model": "deepseek-v4-flash",
  "timeout_seconds": 15,
  "restore_to_english": true,
  "english_input_source": "<copy actual English source ID>",
  "chinese_input_source": "<copy actual Chinese source ID>"
}
```

Do not ship guessed IDs as functional defaults.

- [ ] **Step 4: Document permissions and privacy**

README must state:

```text
Required: System Settings -> Privacy & Security -> Accessibility -> Hammerspoon ON.
Not required for V1: Full Disk Access, Screen Recording, microphone, browser history access.
Sent to DeepSeek: only text typed in the English Assist popup.
Stored locally: successful source/translation pairs and sanitized diagnostics.
Not stored: API key in files, failed phrase requests, surrounding document paragraphs.
```

- [ ] **Step 5: Create doctor wrapper**

```bash
#!/usr/bin/env bash
# scripts/doctor.sh
set -euo pipefail
exec "$HOME/EnglishAssist/.venv/bin/english-assist" doctor
```

- [ ] **Step 6: Run automated verification from a clean venv**

```bash
rm -rf .venv
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest -v
```

Expected: every Python unit test PASS.

- [ ] **Step 7: Run the full manual acceptance checklist**

```text
[ ] English is the normal input source before invocation.
[ ] Option+Space opens one popup and does not alter the document.
[ ] Popup automatically switches to configured Chinese input source.
[ ] Chinese IME candidate selection with Enter does not accidentally submit mid-composition.
[ ] Enter after composition sends one DeepSeek request.
[ ] Popup remains in Translating… until a result/error arrives.
[ ] Success closes popup, restores target, switches to English, and pastes natural English.
[ ] Caret remains immediately after the pasted English in tested apps.
[ ] phrases.jsonl gains exactly one line only after successful paste dispatch.
[ ] Esc makes no document/storage change.
[ ] Invalid key/network timeout/rate limit leave original document unchanged and allow retry.
[ ] Original clipboard content survives normal successful translation.
[ ] Closed/missing original target causes safe failure, never paste into the wrong app.
[ ] Safari, Chrome, Notes, ChatGPT web, Notion, and native editor smoke tests are documented PASS/unsupported.
[ ] app.log contains no API key and no full source phrase by default.
```

- [ ] **Step 8: Commit installer/docs and tag the V1-ready checkpoint**

```bash
git add .gitignore README.md scripts/install.sh scripts/doctor.sh
git commit -m "docs: add english assist installation and verification"
git tag english-assist-v1-rc1
```

---

## Final Verification Commands

Run these before claiming V1 complete:

```bash
git status --short
.venv/bin/pytest -v
python -m compileall -q src
```

On the actual Mac runtime also run:

```bash
$HOME/EnglishAssist/.venv/bin/english-assist doctor
```

Then reload Hammerspoon and execute the manual acceptance checklist in Task 8.

## Implementation Notes Locked by This Plan

1. **Use `hs.webview`, not `hs.chooser`, for V1.** The UI must remain open during `Translating…` and must handle Chinese IME composition correctly.
2. **Pass translation source over stdin.** Do not put the Chinese phrase in command-line args, environment variables, or shell commands.
3. **Translate and record are separate transactions.** A valid DeepSeek result is not enough to create a phrase record; Hammerspoon records only after it has successfully dispatched paste to the captured target.
4. **Do not use the system clipboard to transport Chinese into Python.** The Python bridge is stdin/stdout; clipboard is reserved only for final cross-app paste.
5. **Use official DeepSeek JSON Output.** Validate the `replacement` field before Hammerspoon ever sees text eligible for insertion.
6. **Fail closed on target ambiguity.** If window identity/focus validation fails, keep the translated text in the popup and do not paste anywhere.
7. **Spacing is conservative.** Only adjust boundary spaces when Accessibility yields safe left/right context; otherwise insert exactly the validated replacement.
