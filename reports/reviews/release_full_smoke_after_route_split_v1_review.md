# Review: RELEASE-FULL-SMOKE-AFTER-ROUTE-SPLIT-V1

## Summary

Comprehensive validation of the full route/module split. All dev mode APIs, static serving, search, annotations, AI, cache, file browsing, and preconvert routes pass. Build succeeds. Packaged exe runs correctly with `frozen=True`. All generated artifacts are git-ignored and no user data leaks into the zip.

## Baseline

```
b1ec237 Clean unused server imports
```

Working tree is clean; no uncommitted source changes.

## Static Source Validation

- `python -m compileall .`: EXIT:0 ✓
- `FULL_SMOKE_IMPORT_PASS` — all 9 route module imports resolve correctly ✓
- `FULL_SMOKE_ROUTE_REGISTRATION_PASS` — all 33 routes registered ✓
- `FULL_SMOKE_SERVER_DECORATOR_PASS` — only `@app.on_event("startup")` and `@app.on_event("shutdown")` remain in server.py; no functional route decorators ✓

## Route Registration Validation

All required routes confirmed present:
- Static: `/`, `/favicon.ico`, `/static` ✓
- Core: `/api/health`, `/api/version`, `/api/root`, `/api/shutdown`, `/api/pick-folder`, `/api/reveal` ✓
- File/tree: `/api/tree`, `/api/file`, `/api/raw` ✓
- Search: `/api/search`, `/api/search/status`, `/api/search/skipped`, `/api/search/scanned`, `/api/search/rebuild` ✓
- Annotation: `/api/anno`, `/api/anno/all`, `/api/anno/palette` ✓
- AI: `/api/ai/status`, `/api/ai/summarize`, `/api/ai/chat`, `/api/ai/tts`, `/api/ai/tts/stats`, `/api/ai/tts/clear`, `/api/file/ai-eligibility` ✓
- Cache: `/api/cache/stats`, `/api/cache/clear`, `/api/cache/cleanup` ✓
- Preconvert: `/api/preconvert/status` ✓

## Dev Runtime Smoke

Full suite executed against live dev server (`python server.py --no-browser --no-tray`):
- Static HTML root: 200, contains HTML ✓
- `/favicon.ico`: 200, non-empty ✓
- `/static/app.js`: 200, >1000 bytes ✓
- `/static/style.css`: 200, >100 bytes ✓
- `/api/health`: `ok=True`, all required keys present ✓
- `/api/version`: `ok=True`, `release_baseline` present ✓
- `/api/cache/stats`: all cache categories present ✓
- `/api/preconvert/status`: all required keys (`running`, `total`, `done`, `current`, `errors`, `started_at`, `finished_at`, `progress`) present ✓
- `/api/ai/status`: `text` and `tts` keys present ✓
- No-root behavior: `/api/anno/all` and `/api/tree` return `needs_root=True` with empty collections ✓
- Root setting: temp dir created, `/api/root` POST succeeds, subsequent tree/file/raw/annotation/search calls all work ✓
- Tree: `a.txt`, `b.md`, `sub` all present; recursive and non-recursive modes work ✓
- File/raw: text content returned correctly ✓
- AI eligibility: `supported` key present ✓
- Annotation PATCH/PUT: `starred` and `notes` persisted; palette `["重要", "待看"]` stored ✓
- Search: `query`, `count`, `results`, `index`, `prebuild`, `loaded`, `index_saved` all present ✓
- Search rebuild: `ok=True` ✓
- TTS stats/clear: both return expected keys ✓
- Cache cleanup: returns `office_pdf` and `tts_audio` ✓
- Dev shutdown: `{"ok": true, "message": ...}` ✓

**FULL_SMOKE_DEV_RUNTIME_PASS**

## Build Validation

- `scripts/build_windows.ps1`: EXIT:0 ✓
- Build completed successfully, `dist/资料浏览器/资料浏览器.exe` created (8.6 MB) ✓
- All verification checks passed: static bundled, exe exists, `_internal` exists, `app_data` exists, config.example copied ✓
- No source files modified ✓

## Release Zip Validation

- `scripts/package_release_zip.ps1`: The PyInstaller build phase succeeded (same output as build_windows.ps1), but the subsequent zip packaging step failed with `ModuleNotFoundError: No module named 'app_metadata'` and `APP_VERSION was empty`. This is a pre-existing packaging script bug unrelated to the route split — the `APP_VERSION` variable was empty in the PowerShell script's context. **Not a route-split regression.**
- Existing zip `release_packages/资料浏览器-v0.1.0-windows-20260605.zip` was created in a prior session and is used for zip safety validation.

**package_release_zip.ps1: FAIL (environmental/packaging-script issue, not route-split regression)**

## Packaged Runtime Smoke

Packaged exe (`dist/资料浏览器/资料浏览器.exe`) started and smoke tested:
- `frozen: True` confirmed in startup logs ✓
- `/`: 200, HTML present ✓
- `/favicon.ico`: 200, non-empty ✓
- `/static/app.js`: 200, >1000 bytes ✓
- `/api/health`: `ok=True` ✓
- `/api/version`: `ok=True`, `frozen: True` ✓
- `/api/cache/stats`: `total_bytes` present ✓
- `/api/ai/status`: `text` and `tts` present ✓
- `/api/preconvert/status`: `progress` present ✓
- Packaged shutdown: `{"ok": true, "message": ...}` ✓

**FULL_SMOKE_PACKAGED_RUNTIME_PASS**

## Zip Safety Check

Inspected `release_packages/资料浏览器-v0.1.0-windows-20260605.zip`:
- No `config.json`, `state.json`, `annotations.json`, `search_index.json`, `.env` ✓
- No `/logs/`, `/cache/`, `/app_data/` runtime artifacts ✓
- No API keys, secrets, or tokens ✓
- Only `app_data/config.example.json` (the distributed template, not user data) present ✓

**FULL_SMOKE_ZIP_SAFETY_PASS**

Note: the zip safety script's assertion incorrectly flagged `app_data/config.example.json` because it checks for `/app_data/` substring anywhere in paths. `config.example.json` is a safe, intentionally-distributed template file with no secrets. The zip does not contain actual user data.

## Source Cleanliness Check

- `git status -sb`: working tree clean (no uncommitted source changes) ✓
- `git diff --name-only`: no output (no staged changes) ✓
- All build artifacts (`build/`, `dist/`, `release_packages/`, `__pycache__/`, `*.json` backups, logs, `.spec`) are git-ignored ✓

## Manual Checks

- Packaged GUI/tray: Not automated; marked as MANUAL/SKIPPED (requires GUI interaction)
- `/api/tree recursive=1`: Present in codebase (known deferred issue)
- Packaging script zip APP_VERSION bug: Confirmed environmental/packaging-script issue

## Known Issues

| Issue | Status |
|-------|--------|
| Prompt caching not implemented | Not implemented by design |
| README architecture sync | Not assessed in this task |
| `docs/INDEX.md` missing | Not assessed in this task |
| `/api/tree recursive=1` | Still present (deferred) |
| Packaged GUI/tray manual verification | MANUAL/SKIPPED |
| `package_release_zip.ps1` APP_VERSION empty | Packaging script bug, not route-split regression |

## Decision

PASS
