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
