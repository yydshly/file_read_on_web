# Review: PROJECT-ARTIFACTS-ROOT-AUDIT-V1

## Summary

Organized root-level project artifacts by moving PyInstaller spec files into a new `packaging/` directory. Verified that `.gitignore` already covers all runtime/generated artifacts. The build script (`scripts/build_windows.ps1`) uses PyInstaller CLI directly and was unaffected by the spec file relocation.

## Baseline
- Branch: main
- Commit: 65079e5
- Remote: origin (https://github.com/yydshly/file_read_on_web.git)

## Root Directory Audit

| Root Item | Classification | Action |
|---|---|---|
| `.claude/` | KEEP_ROOT | unchanged (already ignored) |
| `__pycache__/` | BUILD_OUTPUT_IGNORE | unchanged (already ignored) |
| `annotations.json` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `annotations.json.bak` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `assets/` | KEEP_ROOT | allowed per task |
| `build/` | BUILD_OUTPUT_IGNORE | already in .gitignore |
| `cache/` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `config.example.json` | KEEP_ROOT | tracked example config |
| `config.json` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `config.json.bak` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `dist/` | BUILD_OUTPUT_IGNORE | already in .gitignore |
| `docs/` | KEEP_ROOT | per task |
| `logs/` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `packaging/` | NEW_DIRECTORY | created |
| `README.md` | KEEP_ROOT | project metadata |
| `release_packages/` | BUILD_OUTPUT_IGNORE | already in .gitignore |
| `reports/` | KEEP_ROOT | per task |
| `requirements.txt` | KEEP_ROOT | project dependency |
| `resource_browser_build.spec` | MOVE_TO_PACKAGING | moved to packaging/ |
| `scripts/` | KEEP_ROOT | per task |
| `search_index.json` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `search_index.json.bak` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `server.py` | KEEP_ROOT | entrypoint |
| `src/` | KEEP_ROOT | per task |
| `start.bat` | KEEP_ROOT | launcher script |
| `state.json` | RUNTIME_GENERATED_IGNORE | already in .gitignore |
| `ziliao.spec` | MOVE_TO_PACKAGING | moved to packaging/ |
| `ziliao_build.spec` | MOVE_TO_PACKAGING | moved to packaging/ |
| `资料浏览器.spec` | MOVE_TO_PACKAGING | moved to packaging/ |
| `资料浏览器_noconsole.spec` | MOVE_TO_PACKAGING | moved to packaging/ |
| `教学资料/` | RUNTIME_GENERATED_IGNORE | already in .gitignore |

## Spec File Rehome

All 5 root-level spec files moved to `packaging/`:
- `resource_browser_build.spec`
- `ziliao.spec`
- `ziliao_build.spec`
- `资料浏览器.spec`
- `资料浏览器_noconsole.spec`

## JSON / Runtime Artifact Policy

No runtime JSON files are tracked by git. All are either in `.gitignore` or not yet added. Files confirmed ignored:
- `config.json` — in .gitignore
- `state.json` — in .gitignore
- `annotations.json` — in .gitignore
- `search_index.json` — in .gitignore

Backup files (`*.bak`) are also ignored via `*.bak` pattern.

## .gitignore Review

Existing `.gitignore` already contains all required entries. No changes were necessary.

Coverage verified:
- `config.json` ✓
- `state.json` ✓
- `annotations.json` ✓
- `search_index.json` ✓
- `app_data/` ✓
- `cache/` ✓
- `logs/` ✓
- `build/` ✓
- `dist/` ✓
- `release_packages/` ✓
- `__pycache__/` ✓

Note: `*.spec` in gitignore only matches root-level spec files, allowing `packaging/*.spec` to be tracked.

## Packaging Path Review

`scripts/build_windows.ps1` uses PyInstaller CLI directly (not spec files), so no spec path updates were needed. The `--add-data` flag already references `src/frontend/static` correctly. Build verification paths also already reference `src/frontend/static`.

Build result: **SUCCESS** — all 8 verification checks passed.

## Validation

| Check | Result |
|---|---|
| `python -m compileall .` | PASS |
| `ROOT_PY_ONLY_SERVER_PASS` | PASS |
| `SPEC_REHOME_PASS` | PASS |
| `PACKAGING_STATIC_PATH_PASS` | PASS |
| `RUNTIME_ARTIFACT_IGNORE_PASS` | PASS |
| `NO_TRACKED_RUNTIME_JSON_PASS` | PASS |
| Packaging check | PASS (build succeeded) |

## Forbidden Changes Review

- Source files unchanged: PASS (server.py, src/** not modified)
- Frontend files unchanged: PASS (src/frontend/static files not modified)
- Routes unchanged: PASS (no route changes)
- Generated artifacts not committed: PASS (dist/, build/, release_packages/ not tracked)

## Known Issues

None.

## Decision

**PASS**
