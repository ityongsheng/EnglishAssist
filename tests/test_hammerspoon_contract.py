from pathlib import Path


def test_hammerspoon_script_contains_v1_safety_contract():
    lua = Path("hammerspoon/english_assist.lua").read_text(encoding="utf-8")
    required = [
        'hs.hotkey.bind({"shift"}, "space"',
        'hs.webview.usercontent.new("englishAssistBridge")',
        'hs.keycodes.currentSourceID',
        'hs.task.new',
        'task:setInput(text)',
        'readAllData',
        'writeAllData',
        'validTargetWindow',
        'finishTranslation',
        'recordPhrase',
        'state.mode == "translating"',
    ]
    for needle in required:
        assert needle in lua


def test_hammerspoon_loader_points_at_runtime_app():
    lua = Path("hammerspoon/init.lua.example").read_text(encoding="utf-8")
    assert 'EnglishAssist/app/hammerspoon/?.lua' in lua
    assert 'require("english_assist").start()' in lua


def test_phrase_history_records_clean_model_translation_not_spacing_wrapper():
    lua = Path("hammerspoon/english_assist.lua").read_text(encoding="utf-8")
    assert "recordPhrase(recorded)" not in lua
    assert "recordPhrase(translation)" in lua.split("pasteReplacement", 2)[-1]


def test_hammerspoon_tasks_use_arguments_overload_without_nil_stream_callback():
    lua = Path("hammerspoon/english_assist.lua").read_text(encoding="utf-8")
    assert "end, nil, {" not in lua


def test_hammerspoon_popup_errors_encode_javascript_strings_without_hs_json_string_mode():
    lua = Path("hammerspoon/english_assist.lua").read_text(encoding="utf-8")
    assert "local function jsString(value)" in lua
    assert "hs.json.encode(message)" not in lua


def test_hammerspoon_popup_stays_below_input_method_candidate_window():
    lua = Path("hammerspoon/english_assist.lua").read_text(encoding="utf-8")
    assert ":bringToFront(true)" not in lua
    assert ":bringToFront(false)" in lua
