# Review: CORE-MODULES-SRC-REHOME-V1

## Summary

All remaining root-level backend Python modules were moved into the `src/` package structure. The final layout is:

```
server.py              ← entrypoint (unchanged)
src/
  ai/                 ← provider/task layer (established in prior task)
  backend/
    domain/           ← app_metadata
    infra/            ← safeio, logging_setup, tray_controller
    services/         ← converter, search, annotations,
                         runtime_state, tts_cache, ai_document
```

## Changed Files

**New files:**
- `src/backend/domain/__init__.py`
- `src/backend/domain/app_metadata.py`
- `src/backend/infra/__init__.py`
- `src/backend/infra/safeio.py`
- `src/backend/infra/logging_setup.py`
- `src/backend/infra/tray_controller.py`
- `src/backend/services/converter.py`
- `src/backend/services/search.py`
- `src/backend/services/annotations.py`

**Modified:**
- `server.py` — updated imports to `src.backend.*`
- `src/backend/services/runtime_state.py` — updated infra imports
- `src/backend/services/tts_cache.py` — updated infra imports
- `src/backend/services/ai_document.py` — updated service imports

**Deleted (old root-level modules):**
- `converter.py`, `search.py`, `annotations.py`, `safeio.py`, `logging_setup.py`, `tray_controller.py`, `app_metadata.py`

## Import Migration

All imports were updated to absolute `src.backend.*` paths:
- `server.py` → `src.backend.services.*`, `src.backend.infra.*`, `src.backend.domain.*`
- `runtime_state.py` → `src.backend.infra.*`
- `tts_cache.py` → `src.backend.infra.*`
- `ai_document.py` → `src.backend.services.converter`, `src.backend.services.search`
- `search.py` → `from . import converter`, `from src.backend.infra.safeio import ...`
- `annotations.py` → `from src.backend.infra.safeio import ...`

Move order ensured correct dependencies: infra → domain → services.

## Runtime Path Model Review

All path constants (`APP_DIR`, `DATA_DIR`, `RESOURCE_DIR`, `STATIC_DIR`, `CACHE_DIR`, `TTS_CACHE_DIR`, `CONFIG_PATH`, `STATE_PATH`, `ANNO_PATH`, `SEARCH_INDEX_PATH`) and path functions (`_app_base_dir`, `_resource_base_dir`, `_data_base_dir`) remain in `server.py` unchanged.

## Service Behavior Review

- All modules are byte-for-byte identical to originals except for import path changes
- `converter.py` — no import changes needed (did not import any moved modules)
- `search.py` — updated to `from . import converter` (relative) and `from src.backend.infra.safeio import ...`
- `annotations.py` — updated to `from src.backend.infra.safeio import ...`
- `safeio.py`, `logging_setup.py`, `tray_controller.py`, `app_metadata.py` — no internal import changes needed

## Dev Smoke

Server starts cleanly with `python server.py --no-browser --no-tray`. No errors.

## Packaging Review

```
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```
Build completed successfully. No `hiddenimports` or `pathex` changes were required — PyInstaller auto-discovers `src.*` imports.

## Forbidden Changes Review

- Routes not split: ✓ server.py still holds all routes
- Frontend unchanged: ✓ no frontend files modified
- `src/ai/` unchanged: ✓ only import paths updated
- Generated artifacts not committed: ✓ dist/ cleaned before staging
- No AppContext, no route split, no feature changes: ✓

## Known Issues

**Validation spec substring false positive:** The spec's `NO_OLD_ROOT_IMPORTS_PASS` check uses raw substring matching (e.g. `r"import converter"`) which incorrectly flags `from src.backend.services import converter` — the correct new import literally contains the forbidden substring as a substring. This is a spec design issue; precise line-based checking confirms all old root-level imports are genuinely eliminated. The actual runtime behavior is correct.

## Decision
**PASS**
