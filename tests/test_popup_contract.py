from pathlib import Path


def test_popup_exposes_ime_safe_bridge_contract():
    html = Path("hammerspoon/popup.html").read_text(encoding="utf-8")
    assert "compositionstart" in html
    assert "compositionend" in html
    assert "event.isComposing" in html
    assert "action:'submit'" in html
    assert "action:'cancel'" in html
    assert "window.EnglishAssist" in html
    assert "setTranslating" in html
    assert "setError" in html
