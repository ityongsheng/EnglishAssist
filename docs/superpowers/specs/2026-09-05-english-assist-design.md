# English Assist V1 Design

Date: 2026-09-05
Status: Proposed design, approved in chat for specification

## 1. Goal

Build a lightweight macOS English-writing assistant for a user who normally writes in English but occasionally needs to express an idea in Chinese.

The primary interaction is:

1. The user is typing in any normal macOS text field with English as the default input language.
2. The user presses `Shift+Space`.
3. English Assist opens a small floating input window near the active app and automatically switches that input box to Chinese input.
4. The user types Chinese and presses `Enter`.
5. English Assist sends the Chinese text to the DeepSeek API.
6. On success, the floating window closes, focus returns to the original app, and the translated natural English is inserted at the original caret position.
7. English Assist restores the English input source.
8. The successful Chinese→English pair is appended to `phrases.jsonl`.
9. The user immediately continues typing in English.

The tool is not a replacement for Apple Writing Tools. DeepSeek handles “I do not know how to say this in English”; Apple Writing Tools handles proofreading and rewriting after the user has finished drafting.

## 2. V1 Scope

V1 includes only:

- Global hotkey: `Shift+Space`.
- Floating Chinese input box.
- Automatic temporary switch to a configured Chinese input source.
- `Enter` to translate.
- `Esc` to cancel without changing the document.
- DeepSeek API translation.
- Safe insertion at the original caret position.
- Restoration of the English input source.
- Append-only learning log in JSONL.
- Error/retry UI.
- Clipboard preservation.
- Basic automatic spacing around inserted English.
- Support for common editable text fields in apps such as Safari, Chrome, Notes, ChatGPT, Notion, editors, and standard macOS controls where synthetic paste is allowed.

V1 explicitly does not include:

- A custom macOS input method.
- Automatic monitoring of all keystrokes.
- Double-space triggers.
- A menu-bar analytics application.
- iPhone or Apple Watch apps.
- Cloud synchronization.
- Anki export.
- A database server.
- User accounts.
- Automatic invocation of Apple Writing Tools.
- Continuous background capture of document content.

## 3. Architecture

Use a small two-layer architecture.

### 3.1 Hammerspoon interaction layer

Responsibilities:

- Register global `Shift+Space`.
- Capture the currently focused application/window before opening the assistant.
- Remember the current macOS input source.
- Open and focus the floating input UI.
- Switch the assistant input field to the configured Chinese input source.
- Handle `Enter`, `Esc`, and retry.
- Keep the original document untouched while translation is pending.
- On successful translation, restore focus to the original application.
- Insert the returned English text using safe paste/insertion logic.
- Restore the prior input source, normally English.
- Preserve and restore the user's clipboard contents.
- Display concise status/error notifications.

Hammerspoon should contain no DeepSeek-specific business logic beyond invoking the Python core and receiving its structured result.

### 3.2 Python core

Responsibilities:

- Read the DeepSeek API key securely from macOS Keychain.
- Build the translation request.
- Call the DeepSeek API.
- Validate the response.
- Return a minimal structured response to Hammerspoon.
- Append successful translations to `phrases.jsonl`.
- Write diagnostic logs without recording secrets.

Suggested modules:

- `app/translate.py` — command-line entry point used by Hammerspoon.
- `app/deepseek.py` — DeepSeek client and response validation.
- `app/storage.py` — append-only phrase logging.
- `app/config.py` — non-secret settings, model name, timeouts, input-source identifiers.

## 4. User Interaction

### 4.1 Opening

When `Shift+Space` is pressed:

- Store the currently focused app/window reference.
- Store the current input source.
- Store a marker that identifies the current insertion point context as well as practical APIs allow.
- Open a compact floating window.
- Focus its text field.
- Switch to the configured Chinese input source.

Suggested appearance:

```
┌────────────────────────────────────┐
│ ✦ Translate to English             │
│                                    │
│ 我越来越觉得长期积累非常重要_       │
│                                    │
│ Enter Translate    Esc Cancel      │
└────────────────────────────────────┘
```

### 4.2 Translation state

After `Enter`:

- Disable duplicate submission.
- Keep the floating window visible.
- Show `Translating…`.
- Do not return focus to the original app yet.
- Do not modify the original document.

This avoids a race where the user continues typing before the translation is ready and the translation is later inserted at an unintended location.

### 4.3 Success

On success:

1. Receive a validated English replacement from Python.
2. Close the floating window.
3. Restore the original application/window focus.
4. Restore the original or configured English input source.
5. Insert the translated English at the intended caret position.
6. Place the caret immediately after the inserted English.
7. Restore the original clipboard contents.
8. Append the phrase record to `phrases.jsonl`.

### 4.4 Cancel

Pressing `Esc`:

- Closes the floating window.
- Restores the original input source.
- Restores focus to the original app.
- Makes no document changes.
- Saves no phrase record.

### 4.5 Failure

If network, authentication, timeout, API, or parsing errors occur:

- The original document remains unchanged.
- Keep the entered Chinese text in the assistant window.
- Display a concise error.
- Provide `Enter` to retry and `Esc` to cancel.

Example:

```
┌────────────────────────────────────┐
│ ⚠ Translation failed               │
│                                    │
│ 保持长期主义                        │
│                                    │
│ Enter Retry        Esc Cancel      │
└────────────────────────────────────┘
```

## 5. DeepSeek Integration

### 5.1 API behavior

The Python core should use DeepSeek through its official API endpoint and use a low-latency, low-cost model appropriate for short translation tasks. The exact model name must remain configurable rather than hard-coded into UI logic.

Thinking/reasoning should be disabled for V1 translation requests when the chosen API/model supports doing so.

### 5.2 Translation prompt

The model instruction should prioritize insertable natural English, not explanations.

Required behavior:

- Translate the user's Chinese into natural, modern English.
- Prefer how an English speaker would naturally express the idea rather than literal word-for-word translation.
- Preserve meaning and tone.
- Return only text that can be directly inserted into an English draft.
- No quotation marks.
- No labels such as “Translation”.
- No Markdown.
- No explanation.
- If the user includes mixed Chinese and English, preserve useful English and rewrite only as needed to make the whole fragment natural.

### 5.3 Structured result

Prefer a structured result that can be validated before insertion, conceptually:

```json
{
  "replacement": "maintain a long-term mindset",
  "source": "保持长期主义",
  "learning_phrase": "maintain a long-term mindset"
}
```

Only `replacement` is inserted into the document. The storage layer can record the source and translation after successful insertion.

If structured mode is unavailable or unreliable for a chosen model/API version, Python must still strictly sanitize and validate plain text before returning it.

## 6. Secure API Key Storage

The DeepSeek API key must not be stored in source code, JSON config, shell history examples, or Git.

Use macOS Keychain with a dedicated service name such as:

- Service: `EnglishAssist`
- Account: `DeepSeekAPIKey`

The Python core reads the key at request time.

The application must never log the API key or Authorization header.

## 7. Phrase Storage

Store phrases in:

`~/EnglishAssist/data/phrases.jsonl`

One successful translation per line.

Recommended V1 schema:

```json
{"timestamp":"2026-09-05T16:10:32+08:00","source":"保持长期主义","translation":"maintain a long-term mindset","model":"<configured-model>"}
```

Rules:

- Append only.
- UTF-8.
- Save only after a successful translation result is inserted.
- Do not store failed requests.
- Do not store API secrets.
- Avoid storing surrounding document text in V1 for privacy.

## 8. Input Source Handling

Configuration should contain identifiers for:

- Preferred English input source.
- Preferred Chinese input source.

Behavior:

- On launch of the assistant, remember the current input source.
- Switch the floating input box to Chinese.
- On success/cancel/failure exit, restore the previous source, except when user configuration explicitly requests always returning to a specific English input source.

Default UX recommendation: always return to the configured English input source after a successful insertion, because the tool's purpose is English-first writing.

## 9. Insertion and Clipboard Safety

### 9.1 Clipboard preservation

If clipboard-based paste is used:

1. Save the complete clipboard state if supported.
2. Put the translated text on the clipboard.
3. Paste into the original app.
4. Wait briefly for the paste operation to be consumed.
5. Restore the previous clipboard state.

If complete clipboard state cannot be restored reliably for some rich clipboard formats, document the limitation and at minimum preserve the common text clipboard flavor.

### 9.2 Caret safety

The assistant must keep the source application unfocused while translation is pending. This strongly reduces caret drift.

On return, it should focus the same application/window captured at invocation. V1 does not promise reliable insertion if the target window was closed, replaced, or made non-editable while the popup was open; in that case it must fail safely and preserve the translated text for manual copy/retry rather than inserting into an unknown target.

## 10. Automatic Spacing

V1 should prevent obvious spacing errors around inserted English.

Examples:

- `I think|this matters` + `in the long run` should result in `I think in the long run this matters` when surrounding context can be safely determined.
- Before punctuation, avoid `word .` and prefer `word.`.

Because reliable surrounding-text inspection is not available in every app, spacing logic must be conservative. It must never delete or rewrite unrelated text merely to improve spacing.

If context cannot be safely inspected, insert the translation exactly as returned and let the user add/remove a space manually.

## 11. Privacy

V1 sends only the Chinese/mixed fragment entered into the assistant popup to DeepSeek.

It does not:

- Read the whole document.
- Read browser history.
- Continuously monitor keystrokes.
- Upload `phrases.jsonl`.
- Capture surrounding paragraphs.

This should be stated clearly in the README.

## 12. Logging

Diagnostic log location:

`~/EnglishAssist/logs/app.log`

Logs may contain:

- Timestamp.
- Event type.
- Success/failure.
- HTTP status category.
- Latency.
- Sanitized exception message.

Logs must not contain:

- API key.
- Authorization headers.
- Full user text by default.

A debug mode may optionally include text locally, but it must be off by default.

## 13. Permissions

Hammerspoon will likely require macOS Accessibility permissions to synthesize keyboard input and interact with other applications.

The README must explain the exact macOS permission steps and provide a simple permission test.

The design should avoid requesting unnecessary permissions such as Full Disk Access unless later implementation proves it is required.

## 14. Configuration

Suggested non-secret config file:

`~/EnglishAssist/config/config.json`

Conceptual fields:

```json
{
  "model": "<deepseek-low-latency-model>",
  "timeout_seconds": 15,
  "hotkey": "shift+space",
  "restore_to_english": true,
  "english_input_source": "<macOS-input-source-id>",
  "chinese_input_source": "<macOS-input-source-id>"
}
```

The installer/setup workflow should help the user discover the actual input-source identifiers instead of requiring them to guess.

## 15. Error Cases

The implementation must handle at least:

- No API key configured.
- Invalid API key.
- Network offline.
- Request timeout.
- API rate limit.
- API returns empty output.
- API returns malformed structured output.
- Popup submitted with empty text.
- User presses `Shift+Space` while popup is already open.
- Original target app/window disappears.
- Paste is not accepted by the target app.
- Chinese input source is unavailable.
- Clipboard restoration failure.

All failures must be safe: no deletion or replacement of existing document text.

## 16. Testing Strategy

### 16.1 Python unit tests

Test:

- Prompt construction.
- Response parsing.
- Empty/malformed responses.
- Storage append behavior.
- No-write-on-failure behavior.
- Secret redaction in logs.

DeepSeek requests should be mocked in unit tests.

### 16.2 Hammerspoon behavior tests

Manual/automated where practical:

- Hotkey opens popup.
- Popup switches to Chinese input.
- `Esc` restores focus and input source.
- `Enter` blocks duplicate submit.
- Success restores target app and inserts text.
- Failure changes no document text.
- Clipboard is restored.

### 16.3 Compatibility smoke tests

V1 target apps:

- Apple Notes.
- Safari textarea/contenteditable.
- Chrome textarea/contenteditable.
- ChatGPT web composer.
- Notion editor.
- A native macOS text editor.

Any app that blocks synthetic paste can be documented as unsupported rather than worked around with invasive automation.

## 17. Acceptance Criteria

V1 is complete when all of the following are true:

1. The user can type English normally with English as the default input source.
2. `Shift+Space` opens a small assistant input box without changing the original document.
3. The assistant input box accepts Chinese input and supports `Enter` / `Esc`.
4. The assistant can automatically switch to the configured Chinese input source.
5. On successful DeepSeek translation, natural English is inserted at the original caret position.
6. Focus and English input mode are restored so the user can immediately continue typing.
7. Every successful inserted translation is appended to `phrases.jsonl`.
8. Failed requests do not alter the original document.
9. The user's clipboard is preserved as reliably as the target environment allows.
10. API secrets are stored in macOS Keychain and never committed to Git.
11. The implementation works in the defined smoke-test applications, subject to documented app-specific limitations.
12. No continuous keystroke logging or surrounding-document upload occurs.

## 18. Future Extensions (Not V1)

Possible later additions only after V1 proves useful in daily use:

- `Option+Shift+Space` learning/explanation mode.
- Phrase search and favorites.
- Review scheduling.
- iCloud synchronization.
- iPhone Shortcuts or app-based review.
- Anki export.
- Menu-bar statistics.
- Native Swift UI replacing Hammerspoon.
- Multiple translation providers.
- Per-app style presets.

These are deliberately excluded from V1.
