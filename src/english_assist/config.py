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
        "model",
        "base_url",
        "timeout_seconds",
        "restore_to_english",
        "english_input_source",
        "chinese_input_source",
    }
    updates = {k: v for k, v in raw.items() if k in allowed}
    if "timeout_seconds" in updates:
        updates["timeout_seconds"] = float(updates["timeout_seconds"])
    return replace(cfg, **updates)
