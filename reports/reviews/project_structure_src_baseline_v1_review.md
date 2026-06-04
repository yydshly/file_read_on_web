# Review: PROJECT-STRUCTURE-SRC-BASELINE-V1

## Summary

Established a clean `src/` project structure while keeping `server.py` as the runtime entrypoint. All previously-extracted backend modules (`runtime_state.py`, `tts_cache.py`, `ai/service.py`) were relocated into the new structure without changing runtime behavior.

## Changed Files

- `server.py` — updated imports to use `src.*` paths
- `src/__init__.py` — new package marker
- `src/ai/__init__.py` — new
- `src/ai/base.py` — moved from `ai/base.py`
- `src/ai/factory.py` — moved from `ai/factory.py`
- `src/ai/tasks.py` — moved from `ai/tasks.py`
- `src/ai/minimax.py` — moved from `ai/minimax.py`
- `src/ai/minimax_anthropic.py` — moved from `ai/minimax_anthropic.py`
- `src/ai/mimo.py` — moved from `ai/mimo.py`
- `src/backend/__init__.py` — new
- `src/backend/services/__init__.py` — new
- `src/backend/services/runtime_state.py` — moved from `runtime_state.py`
- `src/backend/services/tts_cache.py` — moved from `tts_cache.py`
- `src/backend/services/ai_document.py` — moved and renamed from `ai/service.py`
- `ai/` directory — deleted (all modules moved)
- `runtime_state.py` — deleted (moved)
- `tts_cache.py` — deleted (moved)

## New Directory Structure

```
src/
  __init__.py
  ai/
    __init__.py       (was ai/__init__.py)
    base.py           (was ai/base.py)
    factory.py        (was ai/factory.py)
    tasks.py          (was ai/tasks.py)
    minimax.py        (was ai/minimax.py)
    minimax_anthropic.py
    mimo.py
  backend/
    __init__.py
    services/
      __init__.py
      runtime_state.py  (was runtime_state.py)
      tts_cache.py      (was tts_cache.py)
      ai_document.py    (was ai/service.py)
```

Architecture: `src/ai/` = provider/task/model-call layer; `src/backend/services/` = application service layer. `ai/service.py` (now `ai_document.py`) correctly lives under `backend/services`, not under `ai/`.

## Import Migration

- `server.py` now imports from `src.ai.*` and `src.backend.services.*`
- `ai_document.py` imports `from src.ai import factory as ai_factory`
- `src/ai/factory.py` uses relative imports `from .base import ...`
- `src/ai/tasks.py` uses relative imports `from .base import ...`
- `src/ai/minimax.py`, `minimax_anthropic.py`, `mimo.py` use relative imports `from .base import ...`
- `RuntimeStateStore` and `TtsCache` in `src/backend/services/` keep their original `safeio` and `logging_setup` imports (root-level modules, not moved)
- `ai_document.py` keeps its original `converter` and `search` imports (root-level modules, not moved)

## Runtime Path Model Review

All path constants (`APP_DIR`, `DATA_DIR`, `RESOURCE_DIR`, `STATIC_DIR`, `CACHE_DIR`, `TTS_CACHE_DIR`, `CONFIG_PATH`, `STATE_PATH`, `ANNO_PATH`, `SEARCH_INDEX_PATH`) remain in `server.py` unchanged. No path functions were modified.

## Service Behavior Review

- `RuntimeStateStore` — byte-for-byte identical except updated docstring path reference
- `TtsCache` — byte-for-byte identical
- `AiDocumentService` — same behavior, imports updated to `src.ai.factory`
- `build_ai_status` — same behavior
- `mask_key` — same behavior

## Dev Smoke

Server starts cleanly:
```
python server.py --no-browser --no-tray
```
No errors. All routes remain in `server.py`.

## Packaging Review

```
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```
Build completed successfully. No `hiddenimports` or `pathex` changes were required — PyInstaller auto-discovers `src.*` imports when analyzing `server.py`.

## Forbidden Changes Review

- Routes not split: ✓ `server.py` still holds all routes
- Frontend unchanged: ✓ no frontend files modified
- `converter.py`, `search.py`, `annotations.py` unchanged: ✓ remain at root
- `safeio.py`, `logging_setup.py`, `tray_controller.py` unchanged: ✓ not moved
- `static/`, `scripts/`, `docs/`, `README.md` unchanged: ✓ not touched
- No generated artifacts committed: ✓ `dist/` cleaned before staging

## Known Issues

None.

## Decision
**PASS**
