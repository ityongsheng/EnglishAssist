import io
import json
from pathlib import Path

from english_assist import cli
from english_assist.models import PhraseRecord, TranslationResult


def test_translate_stdout_is_machine_readable_and_does_not_record(monkeypatch, capsys, tmp_path: Path):
    monkeypatch.setattr(cli, "get_deepseek_api_key", lambda: "sk-test")
    monkeypatch.setattr(cli, "load_config", lambda: cli.AppConfig(runtime_root=tmp_path))

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def translate(self, source):
            return TranslationResult(source, "maintain a long-term mindset", "long-term mindset", "deepseek-v4-flash")

    recorded = []
    monkeypatch.setattr(cli, "DeepSeekClient", FakeClient)
    monkeypatch.setattr(cli, "append_phrase", lambda *_args, **_kwargs: recorded.append(True))
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO("保持长期主义"))

    rc = cli.main(["translate"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload["ok"] is True
    assert payload["replacement"] == "maintain a long-term mindset"
    assert recorded == []


def test_record_appends_exactly_one_phrase(monkeypatch, capsys, tmp_path: Path):
    monkeypatch.setattr(cli, "load_config", lambda: cli.AppConfig(runtime_root=tmp_path))
    calls: list[tuple[Path, PhraseRecord]] = []
    monkeypatch.setattr(cli, "append_phrase", lambda path, record: calls.append((path, record)))
    monkeypatch.setattr(cli.sys, "stdin", io.StringIO(json.dumps({
        "source": "保持长期主义",
        "translation": "maintain a long-term mindset",
        "model": "deepseek-v4-flash",
    }, ensure_ascii=False)))

    rc = cli.main(["record"])
    payload = json.loads(capsys.readouterr().out)

    assert rc == 0
    assert payload == {"ok": True}
    assert len(calls) == 1
    path, record = calls[0]
    assert path == tmp_path / "data" / "phrases.jsonl"
    assert record.source == "保持长期主义"
    assert record.translation == "maintain a long-term mindset"
