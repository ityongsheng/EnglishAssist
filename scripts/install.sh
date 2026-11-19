#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUNTIME="$HOME/EnglishAssist"
HS_DIR="$HOME/.hammerspoon"
HS_INIT="$HS_DIR/init.lua"

choose_python() {
  if command -v python3.12 >/dev/null 2>&1; then
    command -v python3.12
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    local candidate
    candidate="$(command -v python3)"
    if "$candidate" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY
    then
      printf '%s\n' "$candidate"
      return
    fi
  fi
  echo "English Assist requires Python 3.12 or newer." >&2
  echo "Install it first, for example: brew install python@3.12" >&2
  exit 1
}

PYTHON_BIN="$(choose_python)"

echo "Using Python: $PYTHON_BIN ($("$PYTHON_BIN" --version 2>&1))"
mkdir -p "$RUNTIME"/{config,data,logs}

if [[ -e "$RUNTIME/app" && ! -L "$RUNTIME/app" ]]; then
  echo "$RUNTIME/app already exists and is not a symlink; refusing to replace it." >&2
  exit 1
fi
ln -sfn "$ROOT" "$RUNTIME/app"

"$PYTHON_BIN" -m venv "$RUNTIME/.venv"
"$RUNTIME/.venv/bin/python" -m pip install -U pip
"$RUNTIME/.venv/bin/pip" install -e "$ROOT"

CONFIG="$RUNTIME/config/config.json"
if [[ ! -f "$CONFIG" ]]; then
  cat > "$CONFIG" <<'JSON'
{
  "model": "deepseek-v4-flash",
  "timeout_seconds": 15,
  "restore_to_english": true,
  "english_input_source": "",
  "chinese_input_source": ""
}
JSON
  echo "Created $CONFIG"
else
  echo "Keeping existing $CONFIG"
fi

mkdir -p "$HS_DIR"
touch "$HS_INIT"
if ! grep -Fq -- "-- English Assist BEGIN" "$HS_INIT"; then
  cat >> "$HS_INIT" <<'LUA'

-- English Assist BEGIN
package.path = os.getenv("HOME") .. "/EnglishAssist/app/hammerspoon/?.lua;" .. package.path
require("english_assist").start()
-- English Assist END
LUA
  echo "Added English Assist loader to $HS_INIT"
else
  echo "English Assist loader already exists in $HS_INIT"
fi

cat <<EOF

English Assist files are installed under:
  $RUNTIME

Next steps:
  1. Store your DeepSeek key:
     $RUNTIME/.venv/bin/english-assist setup-key

  2. Open Hammerspoon Console and run:
     print("Current:", hs.keycodes.currentSourceID())
     print("Layouts:", hs.inspect(hs.keycodes.layouts(true)))
     print("Methods:", hs.inspect(hs.keycodes.methods(true)))

  3. Put the exact English/Chinese source IDs into:
     $RUNTIME/config/config.json

  4. Enable Hammerspoon in:
     System Settings -> Privacy & Security -> Accessibility

  5. Reload Hammerspoon config, then type in any editor and press Shift+Space.

Run diagnostics anytime with:
  $ROOT/scripts/doctor.sh
EOF

if [[ ! -d "/Applications/Hammerspoon.app" ]]; then
  echo
  echo "Hammerspoon was not detected in /Applications. Install it first (Homebrew: brew install --cask hammerspoon)."
fi
