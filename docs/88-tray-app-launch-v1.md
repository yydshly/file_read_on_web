# TRAY-APP-LAUNCH-V1

## Task
TRAY-APP-LAUNCH-V1

## Decision
**PASS**

---

## Baseline
- Branch: `main`
- Commit (before): `c8adc31` (origin/main)
- Remote: `origin/main`

---

## Changed Files
| File | Change |
|------|--------|
| `tray_controller.py` | New — pystray-based tray controller |
| `server.py` | Added `--tray`/`--no-tray` args, shared shutdown helper, tray startup integration |
| `requirements.txt` | Added `pystray>=0.19`, `Pillow>=10.0` |
| `scripts/build_windows.ps1` | Added `--hidden-import` for `pystray._win32`, `PIL.Image`, `PIL.ImageDraw` |
| `README.md` | Added "系统托盘" section |

---

## Implemented

### tray_controller.py
- Standalone module with `TrayController` class
- Menu items: `打开资料浏览器`, `查看日志`, `打开数据目录`, `退出程序`
- Graceful degradation if pystray/Pillow unavailable (returns `False` from `start()`)
- Icon loaded from `static/favicon.ico`
- All menu callbacks run in tray daemon thread
- `stop()` signals icon shutdown cleanly

### pystray / Pillow dependency
- Added to `requirements.txt`: `pystray>=0.19`, `Pillow>=10.0`
- Lazy import in `tray_controller.py` — no hard dependency
- If import fails, `start()` returns `False`, app continues normally

### Packaged default tray
- `tray_enabled = (sys.frozen or args.tray) and not args.no_tray`
- Packaged (`sys.frozen=True`): default `tray_enabled=True`
- Dev mode (`sys.frozen=False`): default `tray_enabled=False`

### Dev mode `--tray`
- `python server.py --tray` forces tray on in dev mode
- Log: `tray_enabled: True`, `tray_started: True`

### `--no-tray`
- `python server.py --no-tray` disables tray even in packaged mode
- Log: `tray_enabled: False`

### Tray menu "打开资料浏览器"
- Calls `_open_app_url(url)` — same browser-opening logic used at startup

### Tray menu "查看日志"
- Opens `app_data/logs/app.log` via `os.startfile()`
- Falls back to opening the logs directory if file doesn't exist

### Tray menu "打开数据目录"
- Opens `app_data/` via `os.startfile()`

### Tray menu "退出程序"
- Calls `tray.stop()` then `_shutdown_callback("tray")`
- Same shared shutdown path as `/api/shutdown`

### Shared shutdown helper
- `_request_app_shutdown(reason)` in `server.py`
- Kills orphaned soffice processes
- Stops tray icon if running
- Calls `_delayed_exit(0.6)`
- Used by both `/api/shutdown` and tray "退出程序"

### Duplicate launch no second tray
- Duplicate detection happens **before** tray startup
- Second instance exits early with `已有服务运行中` log
- Tray thread never started → no second icon

---

## Validation

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| pystray/Pillow import | PASS |
| Dev default `tray_enabled=False` | PASS |
| Dev `--tray` `tray_enabled=True`, `tray_started=True` | PASS |
| Dev `--no-tray` `tray_enabled=False` | PASS |
| Packaged exe starts | PASS |
| Packaged `tray_enabled=True`, `tray_started=True` | PASS |
| PDF preview (packaged) | PASS |
| Image preview (packaged) | PASS |
| Office preview DOCX→PDF (packaged) | PASS |
| reveal API | PASS |
| download API | PASS |
| search | PASS |
| Page shutdown removes tray | PASS |
| Duplicate launch: second exits, no second tray | PASS |
| No forbidden files tracked | PASS |

---

## Log excerpts

```
2026-06-04 19:24:55 [INFO] browse: tray_enabled: True
2026-06-04 19:24:55 [INFO] browse: tray_started: True
2026-06-04 19:25:44 [INFO] browse: 收到退出程序请求 (reason=api:127.0.0.1)
2026-06-04 19:26:08 [INFO] browse: tray_enabled: True
2026-06-04 19:26:08 [INFO] browse: tray_started: True
2026-06-04 19:26:28 [INFO] browse: 收到退出程序请求 (reason=api:127.0.0.1)
```

---

## Not Changed
- `converter.py` — Office conversion logic unchanged
- `annotations.py` — unchanged
- `search.py` — unchanged
- `safeio.py` — unchanged
- `config.example.json` — unchanged
- `static/app.js`, `static/index.html`, `static/style.css` — unchanged
- `ai/` — unchanged
- `root` state machine — unchanged
- Build output structure — still `dist/资料浏览器/`

---

## Known Issues
None.

---

## Recommendation
**Ready for merge.** All acceptance criteria met:
1. Packaged exe defaults to tray enabled ✓
2. Dev mode defaults to no tray ✓
3. `--tray` enables tray in dev ✓
4. `--no-tray` disables tray ✓
5. All 4 tray menu items implemented ✓
6. Page "退出" removes tray via shared shutdown ✓
7. Duplicate launch exits early — no second tray ✓
8. Browser-closed app reachable via tray ✓
9. All regression items unchanged ✓
10. No forbidden files in commit ✓
