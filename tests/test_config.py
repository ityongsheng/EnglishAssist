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
