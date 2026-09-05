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
