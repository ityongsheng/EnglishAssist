from pathlib import Path


def test_install_script_preserves_existing_hammerspoon_config_and_sets_runtime_layout():
    script = Path("scripts/install.sh").read_text(encoding="utf-8")
    assert 'RUNTIME="$HOME/EnglishAssist"' in script
    assert 'ln -sfn "$ROOT" "$RUNTIME/app"' in script
    assert 'English Assist BEGIN' in script
    assert '>> "$HS_INIT"' in script
    assert 'python3.12' in script
    assert 'python3' in script
    assert 'config/config.json' in script


def test_doctor_wrapper_calls_installed_cli():
    script = Path("scripts/doctor.sh").read_text(encoding="utf-8")
    assert '$HOME/EnglishAssist/.venv/bin/english-assist' in script
    assert 'doctor' in script


def test_gitignore_excludes_local_runtime_artifacts():
    ignore = Path(".gitignore").read_text(encoding="utf-8")
    for item in [".venv/", "__pycache__/", ".pytest_cache/", "*.pyc", ".DS_Store"]:
        assert item in ignore
