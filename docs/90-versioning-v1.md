# VERSIONING-V1

## Task
VERSIONING-V1

## Decision
**PASS**

---

## Version
```
APP_VERSION:     "0.1.0"
RELEASE_BASELINE: "Release Baseline V1"
Source of truth: app_metadata.py
```

---

## Implemented

### app_metadata.py
- New file: `app_metadata.py`
- Single source of truth for `APP_ID`, `APP_NAME`, `APP_VERSION`, `RELEASE_BASELINE`
- `APP_VERSION = "0.1.0"` — MVP phase, first publishable baseline after Release Baseline V1

### /api/health version
- Added `"version": APP_VERSION` to existing `/api/health` response
- No fields removed, no semantic changes
- Example response:
  ```json
  {
    "ok": true,
    "app_id": "file_read_on_web",
    "app_name": "资料浏览器",
    "version": "0.1.0",
    "soffice": "D:\\software\\LibreOffice\\program\\soffice.exe",
    "root": "...",
    "needs_root": false
  }
  ```

### /api/version
- New endpoint: `GET /api/version`
- Returns:
  ```json
  {
    "ok": true,
    "app_id": "file_read_on_web",
    "app_name": "资料浏览器",
    "version": "0.1.0",
    "release_baseline": "Release Baseline V1",
    "frozen": false
  }
  ```
- `frozen` reflects `sys.frozen` attribute (True in packaged exe, False in dev)

### Startup log version
- Log now records:
  ```
  version: 0.1.0
  release_baseline: Release Baseline V1
  ```
- Present in both dev and packaged modes

### README version
- Added `当前版本：0.1.0` in the "当前稳定基线" section

### Release baseline doc version
- Updated metadata block: `baseline_commit: 445d793`, added `app_version: 0.1.0`
- Added version note referencing `app_metadata.py` as source of truth

---

## Design

### Version is product metadata
`APP_VERSION` and `RELEASE_BASELINE` are product identity, not user configuration.

### config.json remains user/private config
No version information written to `config.json`, `config.example.json`, `state.json`, or `annotations.json`.

### Future release zip should read APP_VERSION from app_metadata.py
`app_metadata.py` is the single source of truth — future packaging scripts can import it directly.

---

## Validation

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| APP_METADATA_PASS | PASS |
| `/api/health` includes `version: "0.1.0"` | PASS |
| `/api/version` returns all fields | PASS |
| Startup log includes `version` and `release_baseline` | PASS |
| README shows version | PASS |
| Release baseline doc updated | PASS |
| No `config.example.json` change | PASS |
| No business logic change | PASS |

---

## Known Issues
None.
