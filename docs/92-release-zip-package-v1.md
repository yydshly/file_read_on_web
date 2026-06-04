# RELEASE-ZIP-PACKAGE-V1

## Task
RELEASE-ZIP-PACKAGE-V1

## Decision
**PASS**

---

## Changed Files
- `scripts/package_release_zip.ps1` — entry point script
- `scripts/_package_zip.py` — Python zip packaging helper
- `README.md` — added "生成发布 zip" section
- `.gitignore` — added `release_packages/`

---

## Implemented

### scripts/package_release_zip.ps1
- Entry point for release zip packaging
- Calls `scripts/build_windows.ps1` to build `dist/资料浏览器/`
- Reads `APP_VERSION` from `app_metadata.py` via Python
- Stamps zip name with `file_browser-v<VERSION>-windows-<YYYYMMDD>.zip`
- Calls `_package_zip.py` to create and verify the zip
- Output dir: `release_packages/`

### scripts/_package_zip.py
- Pure Python stdlib (`zipfile`) — no new dependencies
- Verifies required structure before zipping:
  - `资料浏览器.exe` exists
  - `_internal/` exists
  - `app_data/config.example.json` exists
- Excludes from zip:
  - `config.json`, `state.json`, `annotations.json`, `search_index.json`
  - `logs/`, `cache/`, `*.log`, `__pycache__/`, `*.pyc`
  - `resource_browser_build.exe`, `ziliao`, `ziliao_build`
- Creates zip with top-level `资料浏览器/` folder
- Verifies zip after creation (ZIP_VERIFY_PASS)
- Exits non-zero on any error

### Version reading
- `APP_VERSION` read from `app_metadata.py` — single source of truth
- Not hardcoded anywhere in scripts

### README update
- Added "生成发布 zip" section with:
  - Command: `powershell -ExecutionPolicy Bypass -File scripts/package_release_zip.ps1`
  - Output example: `release_packages/file_browser-v0.1.0-windows-YYYYMMDD.zip`
  - Note that zip excludes runtime data, config.json, logs, cache

### .gitignore
- Added `release_packages/`

---

## Validation

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| APP_VERSION read correctly | PASS (`0.1.0`) |
| build_windows.ps1 called | PASS |
| zip created | PASS |
| zip name includes version | PASS |
| zip name includes date | PASS |
| zip has top-level `资料浏览器/` | PASS |
| `资料浏览器.exe` in zip | PASS |
| `_internal/` in zip | PASS |
| `config.example.json` in zip | PASS |
| `config.json` excluded | PASS |
| `state.json` excluded | PASS |
| `annotations.json` excluded | PASS |
| `search_index.json` excluded | PASS |
| `logs/` excluded | PASS |
| `cache/` excluded | PASS |
| `resource_browser_build.exe` excluded | PASS |
| old `ziliao` name excluded | PASS |

---

## Known Issues
None.

---

## Recommendation
**Ready for next task.** The release zip workflow is now fully automated. Next logical step would be `RELEASE-CHECKLIST-V1` to formalize the pre-release verification checklist.
