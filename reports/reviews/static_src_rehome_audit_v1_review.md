# Review: STATIC-SRC-REHOME-AUDIT-V1

## Summary

Moved root-level `static/` directory to `src/frontend/static/`. Updated `STATIC_DIR` path in `server.py` and all packaging configuration files (5 spec files + build script) to reference the new location.

## Changed Files

| File | Change |
|------|--------|
| `server.py` | `STATIC_DIR = RESOURCE_DIR / "src" / "frontend" / "static"` |
| `src/frontend/__init__.py` | Created (package marker) |
| `src/frontend/static/*` | Moved from root `static/` |
| `resource_browser_build.spec` | `datas` updated to `('src/frontend/static', 'src/frontend/static')` |
| `ziliao.spec` | `datas` updated to `('src/frontend/static', 'src/frontend/static')` |
| `ziliao_build.spec` | `datas` updated to `('src/frontend/static', 'src/frontend/static')` |
| `资料浏览器.spec` | `datas` updated to `('src/frontend/static', 'src/frontend/static')` |
| `资料浏览器_noconsole.spec` | `datas` updated to `('src/frontend/static', 'src/frontend/static')` |
| `scripts/build_windows.ps1` | Required files, `--add-data` path, and static verification paths updated |

## Static Move

- All 4 files (`app.js`, `favicon.ico`, `index.html`, `style.css`) moved from `static/` to `src/frontend/static/`
- Old root-level `static/` directory deleted
- `src/frontend/__init__.py` created as package marker

## Server Static Path Update

`STATIC_DIR` changed from `RESOURCE_DIR / "static"` to `RESOURCE_DIR / "src" / "frontend" / "static"`.

All static serving routes (`GET /`, `GET /favicon.ico`, `GET /static/*`) remain unchanged — only the filesystem location changed.

## Packaging Review

5 spec files and `scripts/build_windows.ps1` updated to include static assets from `src/frontend/static` instead of root `static`. This is a required change for PyInstaller to bundle the assets from the correct source location.

## Dev Smoke

- `python -m compileall .` — PASS
- Import validation (`STATIC_SRC_IMPORT_PASS`) — PASS
- Content validation (`STATIC_SRC_CONTENT_PASS`) — PASS
- Static files sanity (`STATIC_FILES_PASS`) — PASS
- Old path grep check (`NO_OLD_STATIC_PATH_IN_SERVER_PASS`) — PASS
- Dev smoke test (`STATIC_DEV_SMOKE_PASS`) — PASS
  - `GET /` returned 200 with HTML
  - `GET /static/app.js` returned 200 with >1000 bytes
  - `GET /favicon.ico` returned 200
- Server shutdown via `/api/shutdown` — PASS

## Root Directory Audit

Root-level items classified:

**Should remain root (confirmed present):**
- `server.py` — entrypoint
- `README.md`, `config.example.json`, `requirements.txt` — project metadata
- `scripts/`, `docs/`, `reports/` — project directories
- `src/` — source package directory
- `*.spec` — packaging metadata
- `start.bat` — launcher script
- `assets/` — app icons and resources
- `cache/`, `logs/`, `app_data/` — runtime directories
- `release_packages/` — build output

**Runtime artifacts (not committed):**
- `config.json`, `state.json`, `annotations.json`, `search_index.json` — user data
- `__pycache__/` — Python cache
- `build/`, `dist/` — PyInstaller output

**Note:** Some Chinese-named spec files (e.g., `资料浏览器.spec`) exist alongside ASCII-named ones. Both sets were updated.

## Runtime Path Model Review

- `APP_DIR`, `DATA_DIR`, `RESOURCE_DIR`, `CACHE_DIR`, `TTS_CACHE_DIR` — unchanged
- `CONFIG_PATH`, `STATE_PATH`, `ANNO_PATH`, `SEARCH_INDEX_PATH` — unchanged
- `STATIC_DIR` — **intentionally changed** from `RESOURCE_DIR / "static"` to `RESOURCE_DIR / "src" / "frontend" / "static"`
- `_app_base_dir()`, `_resource_base_dir()`, `_data_base_dir()` — unchanged
- Dev mode static serving verified working
- Packaging path updated to match new STATIC_DIR

## Forbidden Changes Review

- No frontend behavior changed (no JS/CSS/HTML logic modifications)
- No backend services modified
- No `src/ai/**` changed
- No `src/backend/services/**` changed
- No routes split
- No AppContext introduced
- No new features implemented
- Runtime artifacts not committed

## Known Issues

None.

## Decision

**PASS**
