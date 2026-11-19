# English Assist V1

English Assist is a small macOS writing helper for one workflow:

```text
write English -> Shift+Space -> type Chinese -> Enter -> DeepSeek -> English is pasted at the original caret -> keep writing
```

Successful Chinese→English pairs are appended to `~/EnglishAssist/data/phrases.jsonl` so the expressions you personally needed become your own English corpus.

## What V1 does

- Global `Shift+Space` shortcut.
- Floating Chinese input popup.
- Temporary switch to your configured Chinese input source.
- `Enter` translates; `Shift+Enter` inserts a newline; `Esc` cancels.
- Uses DeepSeek `deepseek-v4-flash` by default with thinking disabled and JSON Output.
- Returns focus only to the captured original window and pastes only there.
- Restores the configured English input source after success.
- Preserves the first clipboard item as reliably as Hammerspoon supports.
- Records a phrase only after paste is dispatched successfully.
- Leaves the document unchanged on API/network/target-window failure.

V1 does **not** continuously monitor keystrokes, upload your document, invoke Apple Writing Tools automatically, sync to iPhone, or implement a custom macOS input method.

## Requirements

- macOS 13 or newer.
- Hammerspoon 1.1+.
- Python 3.12+.
- A DeepSeek API key.
- Hammerspoon Accessibility permission.

If you use Homebrew:

```bash
brew install --cask hammerspoon
brew install python@3.12
```

## Install

From the project folder:

```bash
./scripts/install.sh
```

The installer creates/uses:

```text
~/EnglishAssist/
├── app -> this repository
├── .venv/
├── config/config.json
├── data/phrases.jsonl
└── logs/app.log
```

It does **not** replace your existing Hammerspoon configuration. It appends one marked loader block to `~/.hammerspoon/init.lua` only if that block is absent.

## 1. Save the DeepSeek API key in macOS Keychain

Run:

```bash
~/EnglishAssist/.venv/bin/english-assist setup-key
```

The prompt asks twice without echoing the key. The key is stored using:

```text
Service: EnglishAssist
Account: DeepSeekAPIKey
```

The key is not written to `config.json`, source code, `phrases.jsonl`, or logs.

## 2. Discover your real macOS input-source IDs

Do not guess these IDs. Open **Hammerspoon → Console** and run:

```lua
print("Current:", hs.keycodes.currentSourceID())
print("Layouts:", hs.inspect(hs.keycodes.layouts(true)))
print("Methods:", hs.inspect(hs.keycodes.methods(true)))
```

Switch macOS to your normal English input source and note its ID. Then switch to the Chinese input method you want to use and note that ID.

Edit:

```text
~/EnglishAssist/config/config.json
```

Example shape (replace the placeholders with the exact IDs printed on your Mac):

```json
{
  "model": "deepseek-v4-flash",
  "timeout_seconds": 15,
  "restore_to_english": true,
  "english_input_source": "<actual English source ID>",
  "chinese_input_source": "<actual Chinese source ID>"
}
```

## 3. Grant the one required macOS permission

Go to:

```text
System Settings -> Privacy & Security -> Accessibility -> Hammerspoon ON
```

V1 does not require Full Disk Access, Screen Recording, microphone access, or browser-history access.

Reload Hammerspoon config after changing permissions/configuration.

## Use

1. Put the caret where the English should go.
2. Press `Shift+Space`.
3. Type the Chinese idea in the popup.
4. Press `Enter`.
5. Keep writing when the natural English is inserted.

While Chinese IME composition/candidate selection is active, Enter is not treated as a translation submission. `Shift+Enter` can be used for a newline. `Esc` cancels and returns to the original window without changing it.

## Diagnostics

Run:

```bash
./scripts/doctor.sh
```

A ready setup looks conceptually like:

```json
{"ok":true,"keychain":true,"english_input_source":true,"chinese_input_source":true,"model":"deepseek-v4-flash"}
```

If `ok` is false, fill whichever input source is missing or run `setup-key` again.

## Local phrase history

After successful insertion, one line is appended to:

```text
~/EnglishAssist/data/phrases.jsonl
```

Example:

```json
{"timestamp":"2026-09-05T16:10:32+08:00","source":"保持长期主义","translation":"maintain a long-term mindset","model":"deepseek-v4-flash"}
```

Failed requests are not stored. Surrounding document paragraphs are not stored.

## Privacy model

**Sent to DeepSeek:** only the text you explicitly type into the English Assist popup.

**Stored locally:** successful popup source/translation pairs and sanitized diagnostic status.

**Not stored in files:** the DeepSeek API key. It lives in macOS Keychain.

**Not captured:** surrounding document text, browser history, microphone input, screen contents, or continuous keystrokes.

## Apple Writing Tools

English Assist solves **“I don't know how to say this in English.”** Finish your draft first, then use macOS Writing Tools → **Proofread** or **Rewrite** to learn how your own English can be improved.

## DeepSeek API

The implementation uses the OpenAI-compatible endpoint `https://api.deepseek.com/chat/completions`, model `deepseek-v4-flash` by default, `response_format={"type":"json_object"}`, and `thinking={"type":"disabled"}`.
