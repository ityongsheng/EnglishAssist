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
