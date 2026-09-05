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
