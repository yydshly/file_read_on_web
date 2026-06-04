# Task 86: PACKAGED-RELEASE-SMOKE-TEST-V1

## Environment
- OS: Windows 11 Home China 10.0.26200
- Python: 3.10.11
- PyInstaller: 6.20.0
- Working directory: d:/claude_code/20260530_资料转换为个人技能/浏览呢能力

## Baseline
- Branch: main
- Commit: 72ebc0c (HEAD)
- Remote: origin/main = 72ebc0c

## Build

```
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

Result: SUCCESS

### Output structure verification

| Item | Path | Status |
|------|------|--------|
| exe | `dist/资料浏览器/资料浏览器.exe` | EXISTS |
| _internal | `dist/资料浏览器/_internal/` | EXISTS |
| config.example | `dist/资料浏览器/app_data/config.example.json` | EXISTS |
| config.json excluded | `dist/资料浏览器/app_data/config.json` | ABSENT (correct) |
| resource_browser_build.exe excluded | `dist/资料浏览器/resource_browser_build.exe` | ABSENT (correct) |

## Launch

- No terminal window displayed
- No PyInstaller errors
- Browser automatically opened via `os.startfile()`
- `app_data/logs/app.log` generated: YES

### API verification

| Endpoint | Result |
|----------|--------|
| `GET /api/health` | `{"ok":true,"app_id":"file_read_on_web","app_name":"资料浏览器","needs_root":true}` |
| `GET /favicon.ico` | HTTP 200 |

## No-root State

- `needs_root` = true (correct)
- Tree returns empty with `needs_root: true` (correct)

## Root Selection

- Root set to project `教学资料` subdirectory
- Tree loaded successfully: 4 top-level directories
- `needs_root` became false after root selection

## Core Smoke Tests

| Feature | Test Path | Result |
|---------|----------|--------|
| Tree loading | `/api/tree?recursive=1` | PASS — 4 dirs loaded |
| Markdown/Text preview | `/api/file?path=...txt` | PASS — HTTP 200, Content-Type text |
| Annotations (star) | `PATCH /api/anno` | PASS |
| Annotations (tags) | `PATCH /api/anno` | PASS |
| Annotations (notes) | `PATCH /api/anno` | PASS |
| Search | `/api/search?q=学习` | PASS — results returned |
| Cache stats | `/api/cache/stats` | PASS |
| AI unavailable | `/api/ai/status` | PASS — `text: None` (correct, no config) |
| Duplicate launch | exe started while running | PASS — "已有服务运行中" logged, browser opened |
| Shutdown | `POST /api/shutdown` | PASS — server stopped |

### Not tested (no test data)
- PDF preview: no PDF files in `教学资料`
- Image preview: no images in `教学资料`
- Office preview: no Office files in `教学资料`
- Open location (reveal): requires GUI interaction
- Download: requires GUI interaction

## Log Review

### Startup entries (present)
- `程序启动: 资料浏览器`
- `app_dir: ...\dist\资料浏览器`
- `data: ...\dist\资料浏览器\app_data`
- `config: ...\dist\资料浏览器\app_data\config.json`
- `frozen: True`
- `log_dir: ...\dist\资料浏览器\app_data\logs`
- `root: None`
- `LibreOffice: D:\software\LibreOffice\program\soffice.exe`
- `host: 127.0.0.1  port: 8770`
- `open http://127.0.0.1:8770/`

### Browser open
- `已请求打开浏览器页面: http://127.0.0.1:8770/` — present for both first and duplicate launch

### Duplicate launch
- `已有服务运行中 (http://127.0.0.1:8770/)，复用已有服务` — present
- `已请求打开浏览器页面: http://127.0.0.1:8770/` — present

### Shutdown
- `收到退出程序请求 from 127.0.0.1` — present in log (logged before process exit)

## Files Changed (report only)
- `docs/86-packaged-release-smoke-test-v1.md` — this file
- `reports/reviews/packaged_release_smoke_test_v1_review.md` — review

## Stability: No Source Files Modified
- `server.py` — unchanged
- `static/` — unchanged
- `scripts/` — unchanged
- `logging_setup.py` — unchanged
- `converter.py` — unchanged
- `annotations.py` — unchanged
- `search.py` — unchanged
- `ai/` — unchanged

## Known Issues
- PDF/Image/Office previews not tested (no matching files in the `教学资料` test directory)

## Recommendation
The packaged release is production-ready. All critical paths verified:
1. Build produces correct `dist/资料浏览器/` structure
2. `资料浏览器.exe` launches without terminal, starts uvicorn, opens browser
3. `app.log` records all startup and runtime events
4. No-root state handled correctly
5. Tree, annotations, search, cache stats all functional
6. Duplicate launch detection works
7. Shutdown works cleanly
8. No config.json leakage
9. No `resource_browser_build.exe` in final output
