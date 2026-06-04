# REVEAL-FOREGROUND-UX-V1

## Task
REVEAL-FOREGROUND-UX-V1

## Decision
**PASS**

---

## Changed Files
- `server.py` — `_bring_explorer_to_front_later()` helper + enhanced `/api/reveal`
- `static/app.js` — button loading/success/error feedback

---

## Implemented

### Windows Explorer foreground best-effort (`server.py`)
- Added `_bring_explorer_to_front_later(target: Path)` helper
- Runs on a daemon thread, non-blocking
- Waits 0.8s for Explorer window to open
- Uses `ctypes.windll.user32` — no new dependencies
- Tries `CabinetWClass` then `ExploreWClass`
- Calls `ShowWindow(hwnd, SW_RESTORE)` + `SetForegroundWindow(hwnd)`
- Logs success/failure; never raises

### `/api/reveal` response enhanced
Returns:
```json
{
  "ok": true,
  "path": "D:\\path\\to\\file.pdf",
  "parent": "D:\\path\\to",
  "foreground_attempted": true
}
```
- `ok` preserved for backward compatibility
- `foreground_attempted` is `true` on Windows, `false` on other platforms

### Reveal logs
- `"打开本地位置: <path>"` on success
- Windows: `"已请求前置资源管理器窗口: <path>"`
- Failure: `"reveal failed: <reason>"`

### Frontend button feedback (`static/app.js`)
Clicking "打开位置":
1. Button disabled, text → `"打开中…"`
2. On success: text → `"已打开"`, title → `"已打开资源管理器，如未看到请查看任务栏。"`
3. If `setStatus()` exists, also calls it with the same message
4. After 1600ms, button restores original text
5. On failure: alert with error message, button restores immediately

---

## Validation

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| `/api/reveal` returns `ok=true` with valid path | PASS |
| `/api/reveal` enhanced fields (`path`, `parent`, `foreground_attempted`) | PASS |
| `/api/health` | PASS |
| `/api/version` | PASS |
| `/api/tree` | PASS |
| `/api/search` | PASS |
| No new dependencies introduced | PASS |

---

## Known Limitations
- Windows may block forced foreground in some focus-stealing states (UWP apps, full-screen apps, secure desktop). This is a Windows OS limitation, not a bug.
- When foreground is blocked, the user sees the `"如未看到请查看任务栏"` hint in the button title and status message.

---

## Recommendation
**Ready for next task.** The reveal UX is now significantly improved for Windows users.
