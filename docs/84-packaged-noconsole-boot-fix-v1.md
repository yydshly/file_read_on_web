# Task 84: PACKAGED-NOCONSOLE-BOOT-FIX-V1

## Background

`PACKAGED-BUILD-SCRIPT-V1` produced a working but imperfect package:

1. `--noconsole` exe crashed at startup with `AttributeError: 'NoneType' object has no attribute 'isatty'`
2. Output directory was `dist/ziliao/` instead of the product name `dist/资料浏览器/`
3. Internal build name `ziliao_build` leaked into final output
4. Button layout in the UI had suboptimal labels

## Changes

### 1. server.py — stdio guard and uvicorn log_config=None

**`_ensure_stdio_for_noconsole()`** — new function at top of file:

```python
def _ensure_stdio_for_noconsole() -> None:
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8", errors="replace")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8", errors="replace")
```

Called as the first line of `main()`, before any logging or uvicorn setup.

**`uvicorn.run(..., log_config=None)`** — disables uvicorn's default logging config (which calls `.isatty()` on None):

```python
uvicorn.run(app, host=args.host, port=args.port, log_level="info", log_config=None)
```

This forces uvicorn to use our own `logging_setup.py` handler, which we also made noconsole-safe.

### 2. logging_setup.py — conditional console handler

The console `StreamHandler` is now guarded:

```python
stream = getattr(sys, "stdout", None)
if stream is not None and hasattr(stream, "write"):
    console = logging.StreamHandler(stream)
    console.setFormatter(fmt)
    console.setLevel(level)
    root.addHandler(console)
```

File handler is always added. In `--noconsole` mode, only file logging occurs. In dev mode, console output still works.

### 3. scripts/build_windows.ps1 — renamed internal build, correct output path

| Before | After |
|--------|-------|
| Internal name: `ziliao_build` | Internal name: `resource_browser_build` |
| Output: `dist/ziliao/` | Output: `dist/资料浏览器/` |
| Final exe: `ziliao.exe` (manually renamed) | Final exe: `资料浏览器.exe` (auto-renamed) |

Internal flow:
1. PyInstaller builds to `dist/resource_browser_build/`
2. `_build_copy.py` helper copies to `dist/资料浏览器/` and renames `resource_browser_build.exe` → `资料浏览器.exe`
3. Internal build directory deleted after copy
4. `app_data/config.example.json` copied from project root
5. Verification checks for absence of `resource_browser_build.exe` in final dir

**PowerShell CJK encoding workaround**: Chinese product name is hardcoded inside `_build_copy.py` (Python, UTF-8 safe) rather than in PowerShell scripts, avoiding PowerShell's broken CJK string parsing.

### 4. scripts/_build_copy.py — new helper script

Handles:
- `shutil.copytree(..., dirs_exist_ok=True)` — overwrites existing dest dir (works even when Windows Defender has a handle)
- Renames `resource_browser_build.exe` → `资料浏览器.exe`
- Prints Chinese product name as last line for PowerShell to capture

### 5. static/index.html — improved button layout

| Before | After |
|--------|-------|
| `资料浏览器` + `切换` + `退出程序` on same row | `资料浏览器` + `退出` on title row; `切换资料目录` on its own row below |

Button IDs (`shutdown-btn`, `pick-root`) unchanged — no JS changes needed.

### 6. static/style.css — minimal additions

```css
.sidebar-root-actions { margin-top: 4px; }
.sidebar-root-actions #pick-root { width: 100%; }
```

## Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall .` | PASS (exit 0) |
| TEXT_HEALTH_CHECK | PASS |
| No `ziliao` in build script or README | PASS |
| `dist/资料浏览器/` exists | PASS |
| `dist/资料浏览器/资料浏览器.exe` exists | PASS |
| `dist/资料浏览器/app_data/config.example.json` exists | PASS |
| `dist/资料浏览器/app_data/config.json` absent | PASS |
| `resource_browser_build.exe` not in final dir | PASS |
| noconsole exe starts without `isatty` crash | PASS |
| `app_data/logs/app.log` generated | PASS |
| `/api/health` returns `app_id: file_read_on_web` | PASS |
| `/favicon.ico` returns HTTP 200 | PASS |
| Duplicate launch reuses existing service | PASS |
| `/api/shutdown` terminates service | PASS |

## Files Changed

- `server.py` — stdio guard + uvicorn log_config=None
- `logging_setup.py` — conditional console handler
- `scripts/build_windows.ps1` — renamed internal name + correct output
- `scripts/_build_copy.py` — new helper script
- `static/index.html` — button layout
- `static/style.css` — title-row styles
- `README.md` — packaging section updated (already correct)

## Files NOT Changed (stability)

- `converter.py` — Office logic unchanged
- `annotations.py` — data structures unchanged
- `search.py` — search algorithm unchanged
- `ai/` — AI provider logic unchanged
- `safeio.py` — unchanged
- `requirements.txt` — no new dependencies
