# Review: HOTFIX-PACKAGE-RELEASE-ZIP-METADATA-V1

## Summary

Fixed `scripts/package_release_zip.ps1` to read `APP_VERSION` from `src/backend/domain/app_metadata.py` instead of the old root-level `app_metadata.py`. The script now uses AST parsing to extract the version directly from the source file, avoiding import path/PYTHONPATH issues.

## Baseline

```
1a3221d Run full smoke after route split
```

Working tree clean before editing.

## Problem Confirmed

The previous `package_release_zip.ps1` ran:
```powershell
$AppVersion = python -c "from app_metadata import APP_VERSION; print(APP_VERSION)"
```

This failed with:
```
ModuleNotFoundError: No module named 'app_metadata'
APP_VERSION was empty
```

Because `app_metadata.py` was moved to `src/backend/domain/app_metadata.py` during the route split.

## Root Cause

The packaging script was not updated when `app_metadata` was moved into `src/backend/domain/` during the route extraction work. The module import path became invalid in the PyInstaller/PowerShell environment.

## Script Change

Updated `scripts/package_release_zip.ps1`:

**Old (line 32):**
```powershell
$AppVersion = python -c "from app_metadata import APP_VERSION; print(APP_VERSION)"
```

**New (lines 31-38):**
```powershell
# Step 2: Read APP_VERSION from src/backend/domain/app_metadata.py
$MetadataPath = Join-Path $ProjectRoot "src/backend/domain/app_metadata.py"
if (-not (Test-Path $MetadataPath)) {
    Write-Host ("ERROR: metadata file not found: {0}" -f $MetadataPath) -ForegroundColor Red
    exit 1
}

$AppVersion = python -c "import ast, pathlib; p = pathlib.Path(r'$MetadataPath'); tree = ast.parse(p.read_text(encoding='utf-8')); values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0], ast.Name)}; print(values.get('APP_VERSION', ''))"
```

Also updated comment in header from `Reads APP_VERSION from app_metadata.py` to `Reads APP_VERSION from src/backend/domain/app_metadata.py`.

The AST-parsing approach reads the file directly without relying on Python import paths or PYTHONPATH, making it robust in any environment.

## Metadata Extraction Review

- PowerShell parse: PASS
- `PACKAGE_ZIP_METADATA_VERSION_PASS 0.1.0` — `APP_VERSION` correctly extracted from `src/backend/domain/app_metadata.py` via AST parsing
- Old `from app_metadata import APP_VERSION` no longer present: PASS
- New path `src/backend/domain/app_metadata.py` present in script: PASS
- `APP_VERSION was empty` guard retained: PASS

## Package Script Result

`scripts/package_release_zip.ps1`: EXIT:0

- Build step succeeded (PyInstaller `--noconsole` completed)
- `App version: 0.1.0` correctly read
- Zip `资料浏览器-v0.1.0-windows-20260605.zip` created (36,677,978 bytes)
- `ZIP_VERIFY_PASS` — `_package_zip.py` verification succeeded

## New Zip Verification

- `NEW_RELEASE_ZIP_FOUND_PASS`
- `v0.1.0` in zip name: PASS
- `windows` in zip name: PASS

## Zip Safety Validation

- No `config.json`, `state.json`, `annotations.json`, `search_index.json`, `.env` in zip: PASS
- No `/logs/`, `/cache/` path fragments: PASS
- No API keys/secrets/tokens: PASS
- `app_data/config.example.json` present (intentional template, not user data): PASS

## Packaged Runtime Smoke

- Packaged exe started successfully (`frozen: True`)
- `/api/health`: `ok: True` PASS
- `/api/version`: `ok: True`, `frozen: True` PASS
- Shutdown: `{"ok": true, ...}` PASS

**PACKAGE_ZIP_PACKAGED_RUNTIME_PASS**

## Source Cleanliness

- Only `scripts/package_release_zip.ps1` modified: PASS
- `reports/reviews/hotfix_package_release_zip_metadata_v1_review.md` is untracked (report file)
- No `src/**`, `server.py`, `build_windows.ps1`, or `_package_zip.py` changes: PASS
- Build/dist/release_packages artifacts are git-ignored locally

## Forbidden Changes Review

- `server.py` unchanged: PASS
- `src/**` unchanged: PASS
- Routes unchanged: PASS
- Frontend unchanged: PASS
- `scripts/build_windows.ps1` unchanged: PASS
- `scripts/_package_zip.py` unchanged: PASS
- Generated artifacts not committed: PASS

## Known Issues

- Packaged GUI/tray manual verification remains manual if not tested
- README architecture sync remains deferred

## Decision

PASS
