# RELEASE-ZIP-PACKAGE-FIX-V1

## Task
RELEASE-ZIP-PACKAGE-FIX-V1

## Decision
**PASS**

---

## Fixed

### 1. `_package_zip.py` arcname string/Path bug
**Before (broken):**
```python
top_level = source_dir.name  # str
arcname = str(top_level / rel)  # TypeError: unsupported operand type(s) for /: 'str' and 'WindowsPath'
```
**After (fixed):**
```python
arcname = f"{top_level}/{rel.as_posix()}"
```
- Uses `rel.as_posix()` for cross-platform path → forward-slash string
- Properly constructs `资料浏览器/app_data/config.json` etc.

### 2. `package_release_zip.ps1` zip name from `file_browser` to Chinese product name
**Before:**
```powershell
$ZipName = ("file_browser-v{0}-windows-{1}.zip" -f $AppVersion, $DateStamp)
```
**After:**
```powershell
$ZipName = ("资料浏览器-v{0}-windows-{1}.zip" -f $AppVersion, $DateStamp)
```
- Also updated comment from `dist/file_browser/` → `dist/资料浏览器/`

### 3. README/docs/report naming consistency
- `docs/92-release-zip-package-v1.md`: Updated all references from `file_browser-v*` to `资料浏览器-v*`
- Review files: already clean

---

## Validation

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| OLD_NAMING_CLEAN_PASS | PASS |
| APP_VERSION_PASS | PASS |
| `package_release_zip.ps1` execution | PASS |
| ZIP_VERIFY_PASS | PASS |
| Chinese-named zip created (`资料浏览器-v0.1.0-windows-20260604.zip`) | PASS |
| zip has top-level `资料浏览器/` | PASS |
| `exe` included | PASS |
| `_internal/` included | PASS |
| `config.example.json` included | PASS |
| `config.json`/`state.json`/`annotations.json`/`search_index.json` excluded | PASS |
| `logs/`/`cache/` excluded | PASS |
| `resource_browser_build.exe`/`ziliao` excluded | PASS |
| no `dist/` prefix in zip | PASS |

---

## Known Issues
None.
