# Review: STATIC-PACKAGED-SMOKE-V1

## Summary

Packaged build succeeded after `STATIC-SRC-REHOME-AUDIT-V1`. Static assets are correctly bundled at `_internal/src/frontend/static/` in the packaged exe. All runtime smoke tests pass for the packaged app.

## Baseline
- Branch: main
- Commit: d1e3ab3
- Remote: origin (https://github.com/yydshly/file_read_on_web.git)

## Static Path Sanity

- `python -m compileall .` — PASS
- `STATIC_PATH_SANITY_PASS` — PASS
  - `server.STATIC_DIR.name == "static"` — verified
  - `"src" in STATIC_DIR path` — verified
  - `"frontend" in STATIC_DIR path` — verified
  - `src/frontend/static/index.html` exists — verified
  - `src/frontend/static/app.js` exists — verified
  - `src/frontend/static/favicon.ico` exists — verified
  - root-level `static/` does not exist — verified

## Packaging Path Review

- `STATIC_PACKAGING_PATHS_PASS` — PASS
- All 5 spec files reference `src/frontend/static`
- `scripts/build_windows.ps1` references `src/frontend/static`

Files checked:
- `resource_browser_build.spec`
- `ziliao.spec`
- `ziliao_build.spec`
- `资料浏览器.spec`
- `资料浏览器_noconsole.spec`
- `scripts/build_windows.ps1`

## Build Result

- Build command: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1`
- Result: **SUCCESS**
- Output: `dist/资料浏览器/资料浏览器.exe`
- Static bundled at: `dist/资料浏览器/_internal/src/frontend/static/`
- All 4 static files present: `app.js`, `favicon.ico`, `index.html`, `style.css`

## Packaged Runtime Smoke

- `GET /api/health` → 200, `{"ok": true}` — PASS
- `GET /` → 200, HTML body — PASS
- `GET /static/app.js` → 200, >1000 bytes — PASS
- `GET /favicon.ico` → 200, >0 bytes — PASS

## Shutdown Smoke

- `POST /api/shutdown` → `{"ok": true, "message": "..."}` — PASS
- Packaged process exited cleanly — PASS

## Zip Safety

SKIPPED — no release zip was generated in this task. The build outputs to `dist/` which is in `.gitignore`.

## Changed Files Scope

- `git status -sb` shows working tree is clean (only untracked `dist/` and `build/` artifacts)
- No source files modified
- No packaging files modified (all correct from previous task)
- Only review report to be added

## Forbidden Changes Review

- Source files unchanged: PASS (`server.py`, `src/**` — not modified)
- Frontend files unchanged: PASS (no edits made)
- Routes unchanged: PASS (no route changes)
- Generated artifacts not committed: PASS (`dist/` and `build/` remain untracked)

## Known Issues

None.

## Decision

**PASS**
