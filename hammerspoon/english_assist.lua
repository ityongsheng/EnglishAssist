local M = {}

local HOME = os.getenv("HOME")
local runtimeRoot = HOME .. "/EnglishAssist"
local pythonBin = runtimeRoot .. "/.venv/bin/python"
local popupHtmlPath = runtimeRoot .. "/app/hammerspoon/popup.html"
local configPath = runtimeRoot .. "/config/config.json"

local state = {
  mode = "idle",
  popup = nil,
  bridge = nil,
  popupReady = false,
  pendingOpen = false,
  targetWindow = nil,
  targetWindowID = nil,
  previousInputSource = nil,
  activeTask = nil,
  translation = nil,
  requestSerial = 0,
}

local function readFile(path)
  local f, err = io.open(path, "r")
  if not f then return nil, err end
  local value = f:read("*a")
  f:close()
  return value
end

local function loadConfig()
  local f = io.open(configPath, "r")
  if not f then return {} end
  local raw = f:read("*a")
  f:close()
  return hs.json.decode(raw) or {}
end

local function jsCall(script)
  if state.popup and state.popupReady then
    state.popup:evaluateJavaScript(script)
  end
end

local function jsString(value)
  local text = tostring(value or "")
  text = text:gsub("\\", "\\\\")
  text = text:gsub('"', '\\"')
  text = text:gsub("\r", "\\r")
  text = text:gsub("\n", "\\n")
  text = text:gsub("\b", "\\b")
  text = text:gsub("\f", "\\f")
  return '"' .. text .. '"'
end

local function setPopupError(message)
  state.mode = "error"
  jsCall("window.EnglishAssist.setError(" .. jsString(message) .. ")")
end

local function captureTarget()
  local win = hs.window.focusedWindow()
  if not win or not win:id() then
    return false, "No focused target window."
  end
  state.targetWindow = win
  state.targetWindowID = win:id()
  state.previousInputSource = hs.keycodes.currentSourceID()
  return true
end

local function restorePreviousSource()
  if state.previousInputSource and state.previousInputSource ~= "" then
    return hs.keycodes.currentSourceID(state.previousInputSource)
  end
  return true
end

local function switchToChinese()
  local cfg = loadConfig()
  if not cfg.chinese_input_source or cfg.chinese_input_source == "" then
    return false, "Chinese input source is not configured."
  end
  if not hs.keycodes.currentSourceID(cfg.chinese_input_source) then
    return false, "Configured Chinese input source is unavailable."
  end
  return true
end

local function switchToEnglish()
  local cfg = loadConfig()
  if cfg.restore_to_english == false then
    return restorePreviousSource()
  end
  if not cfg.english_input_source or cfg.english_input_source == "" then
    return false
  end
  return hs.keycodes.currentSourceID(cfg.english_input_source)
end

local function popupFrame()
  local screen = hs.mouse.getCurrentScreen() or hs.screen.mainScreen()
  local frame = screen:frame()
  return hs.geometry.rect(
    frame.x + (frame.w - 520) / 2,
    frame.y + frame.h * 0.22,
    520,
    172
  )
end

local function focusPopup()
  if not state.popup then return end
  state.popup:show():bringToFront(false)
  local win = state.popup:hswindow()
  if win then win:focus() end
end

local function activatePopup()
  state.pendingOpen = false
  focusPopup()
  jsCall("window.EnglishAssist.reset()")
  hs.timer.doAfter(0.03, function()
    local switched, err = switchToChinese()
    if not switched then
      setPopupError(err)
      return
    end
    jsCall("window.EnglishAssist.focusInput()")
  end)
end

local function clearSession()
  state.mode = "idle"
  state.targetWindow = nil
  state.targetWindowID = nil
  state.previousInputSource = nil
  state.activeTask = nil
  state.translation = nil
  state.pendingOpen = false
end

local function ensurePopup()
  if state.popup then return true end

  local html, err = readFile(popupHtmlPath)
  if not html then
    hs.alert.show("English Assist popup missing: " .. tostring(err))
    return false
  end

  state.bridge = hs.webview.usercontent.new("englishAssistBridge")
  state.bridge:setCallback(function(message)
    local body = message.body or {}
    if body.action == "ready" then
      state.popupReady = true
      if state.pendingOpen then activatePopup() end
    elseif body.action == "submit" then
      M.submit(body.text or "")
    elseif body.action == "cancel" then
      M.cancel()
    end
  end)

  state.popup = hs.webview.new(
      popupFrame(),
      {
        javaScriptEnabled = true,
        javaScriptCanOpenWindowsAutomatically = false,
        privateBrowsing = true,
      },
      state.bridge
    )
    :allowTextEntry(true)
    :allowNewWindows(false)
    :windowStyle({})
    :shadow(true)
    :transparent(true)
    :bringToFront(false)
    :html(html)

  return true
end

local function validTargetWindow()
  if not state.targetWindowID then return nil end
  local win = hs.window.get(state.targetWindowID)
  if not win or not win:isVisible() then return nil end
  return win
end

local function snapshotClipboard()
  local all = hs.pasteboard.readAllData()
  return {
    all = all,
    text = hs.pasteboard.getContents(),
    empty = (not all or next(all) == nil) and hs.pasteboard.getContents() == nil,
  }
end

local function restoreClipboard(snapshot)
  if snapshot and snapshot.all and next(snapshot.all) ~= nil then
    if hs.pasteboard.writeAllData(snapshot.all) then return true end
  end
  if snapshot and snapshot.text ~= nil then
    return hs.pasteboard.setContents(snapshot.text)
  end
  if snapshot and snapshot.empty then
    hs.pasteboard.clearContents()
    return true
  end
  return false
end

local function smartReplacement(replacement, leftChar, rightChar)
  local value = replacement
  if leftChar and leftChar:match("[%w%)]") and not value:match("^%s") then
    value = " " .. value
  end
  if rightChar and rightChar:match("[%w%(]") and not value:match("%s$") then
    value = value .. " "
  end
  if rightChar and rightChar:match("[%.%,%!%?%:%;]") then
    value = value:gsub("%s+$", "")
  end
  return value
end

local function replacementWithSafeSpacing(replacement)
  -- AX string offsets are reliable enough for byte indexing only when the
  -- surrounding value is ASCII. Otherwise V1 inserts the validated text as-is.
  local system = hs.axuielement.systemWideElement()
  if not system then return replacement end
  local element = system:attributeValue("AXFocusedUIElement")
  if not element then return replacement end
  local value = element:attributeValue("AXValue")
  local range = element:attributeValue("AXSelectedTextRange")
  if type(value) ~= "string" or type(range) ~= "table" then return replacement end
  if not value:match("^[%z\1-\127]*$") then return replacement end

  local location = tonumber(range.location)
  local length = tonumber(range.length)
  if not location or not length or location < 0 or length < 0 then return replacement end

  local leftChar = nil
  if location > 0 then leftChar = value:sub(location, location) end
  local rightIndex = location + length + 1
  local rightChar = nil
  if rightIndex <= #value then rightChar = value:sub(rightIndex, rightIndex) end
  return smartReplacement(replacement, leftChar, rightChar)
end

local function pasteReplacement(target, replacement, callback)
  local snapshot = snapshotClipboard()
  if not hs.pasteboard.setContents(replacement) then
    callback(false, "Could not write translation to clipboard.")
    return
  end

  target:focus()
  hs.timer.doAfter(0.06, function()
    local focused = hs.window.focusedWindow()
    if not focused or focused:id() ~= target:id() then
      restoreClipboard(snapshot)
      callback(false, "Original target window could not be focused.")
      return
    end

    hs.eventtap.keyStroke({"cmd"}, "v", 0, target:application())
    hs.timer.doAfter(0.12, function()
      local restored = restoreClipboard(snapshot)
      callback(true, restored and nil or "Translation inserted, but clipboard restoration failed.")
    end)
  end)
end

local function recordPhrase(translation)
  local payload = hs.json.encode({
    source = translation.source,
    translation = translation.replacement,
    model = translation.model,
  })
  local task = hs.task.new(pythonBin, function(exitCode, _stdOut, _stdErr)
    if exitCode ~= 0 then
      hs.notify.new({
        title = "English Assist",
        informativeText = "English inserted, but phrase history was not saved.",
      }):send()
    end
  end, {"-m", "english_assist.cli", "record"})

  if not task then
    hs.notify.new({
      title = "English Assist",
      informativeText = "English inserted, but phrase history could not be started.",
    }):send()
    return
  end
  task:setInput(payload)
  task:start()
end

function M.open()
  if state.mode == "translating" then return end
  if state.popup and state.popup:isVisible() and (state.mode == "editing" or state.mode == "error") then
    focusPopup()
    jsCall("window.EnglishAssist.focusInput()")
    return
  end

  local ok, err = captureTarget()
  if not ok then
    hs.alert.show(err)
    return
  end
  if not ensurePopup() then
    clearSession()
    return
  end

  state.mode = "editing"
  state.translation = nil
  state.pendingOpen = true
  focusPopup()
  if state.popupReady then activatePopup() end
end

function M.cancel()
  state.requestSerial = state.requestSerial + 1
  if state.activeTask and state.activeTask:isRunning() then
    state.activeTask:terminate()
  end
  if state.popup then state.popup:hide() end
  restorePreviousSource()
  local target = validTargetWindow()
  if target then target:focus() end
  clearSession()
end

function M.submit(text)
  text = (text or ""):match("^%s*(.-)%s*$")
  if text == "" then
    setPopupError("Enter Chinese text first.")
    return
  end
  if state.mode == "translating" then return end

  state.mode = "translating"
  jsCall("window.EnglishAssist.setTranslating()")
  state.requestSerial = state.requestSerial + 1
  local serial = state.requestSerial

  local task = hs.task.new(pythonBin, function(exitCode, stdOut, _stdErr)
    if serial ~= state.requestSerial or state.mode == "idle" then return end
    state.activeTask = nil
    local decoded = hs.json.decode(stdOut or "")
    if exitCode ~= 0 or not decoded or decoded.ok ~= true then
      local message = decoded and decoded.message or "Translation failed. Enter to retry."
      setPopupError(message)
      return
    end
    state.translation = decoded
    M.finishTranslation()
  end, {"-m", "english_assist.cli", "translate"})

  if not task then
    setPopupError("Could not start Python translator.")
    return
  end

  state.activeTask = task
  task:setInput(text)
  local started = task:start()
  if not started then
    state.activeTask = nil
    setPopupError("Could not start Python translator.")
  end
end

function M.finishTranslation()
  local translation = state.translation
  if not translation or not translation.replacement then
    setPopupError("Translation result was invalid.")
    return
  end

  local target = validTargetWindow()
  if not target then
    setPopupError("Original target is no longer available. Translation was not inserted.")
    return
  end

  state.popup:hide()
  target:focus()
  if not switchToEnglish() then
    focusPopup()
    switchToChinese()
    setPopupError("Configured English input source is unavailable. Translation was not inserted.")
    return
  end

  hs.timer.doAfter(0.03, function()
    local stillTarget = validTargetWindow()
    if not stillTarget then
      focusPopup()
      switchToChinese()
      setPopupError("Original target is no longer available. Translation was not inserted.")
      return
    end

    local replacement = replacementWithSafeSpacing(translation.replacement)
    pasteReplacement(stillTarget, replacement, function(ok, warning)
      if not ok then
        focusPopup()
        switchToChinese()
        setPopupError(warning)
        return
      end

      recordPhrase(translation)
      if warning then
        hs.notify.new({title = "English Assist", informativeText = warning}):send()
      end
      clearSession()
    end)
  end)
end

function M.start()
  if M._hotkey then M._hotkey:delete() end
  M._hotkey = hs.hotkey.bind({"alt"}, "space", function()
    if state.mode == "translating" then return end
    if state.popup and state.popup:isVisible() then
      focusPopup()
      jsCall("window.EnglishAssist.focusInput()")
      return
    end
    M.open()
  end)
  hs.alert.show("English Assist loaded")
  return M
end

return M
