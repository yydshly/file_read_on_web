# Review: APP-CONTEXT-BASELINE-V1

## Summary

Introduced `AppContext` as a central dataclass-based context for shared runtime dependencies and mutable application state. `server.py` now creates a single `ctx` object at module level that serves as the single source of truth for `root`, `preconvert_enabled`, AI providers, tray controller, and all service objects.

## Changed Files
- `server.py` — integrated `ctx` as single source of truth
- `src/backend/app_context.py` — new file defining `AppContext` and `AppPaths`

## AppContext Design

```python
@dataclass
class AppPaths:
    app_dir, data_dir, resource_dir, static_dir, cache_dir, tts_cache_dir,
    config_path, state_path, anno_path, search_index_path, default_root_rel

@dataclass
class AppContext:
    paths: AppPaths
    anno_store, state_store, tts_cache, ai_doc_service  # services
    root, preconvert_enabled                             # mutable runtime state
    ai_text_provider, ai_tts_provider                   # AI providers
    tray_controller                                      # tray controller
```

## Server Integration

At module level after path constants:
```python
ctx = AppContext(
    paths=AppPaths(...),
    anno_store=anno_store,
    state_store=state_store,
    tts_cache=tts_cache,
    ai_doc_service=ai_doc_service,
)
```

## Runtime State Migration

| Before | After |
|--------|-------|
| `ROOT` (module global) | `ctx.root` |
| `PRECONVERT_ENABLED` (module global) | `ctx.preconvert_enabled` |
| `ai_text_provider` (module global) | `ctx.ai_text_provider` |
| `ai_tts_provider` (module global) | `ctx.ai_tts_provider` |
| `_tray_controller` (module global) | `ctx.tray_controller` |
| `anno_store` (standalone) | `ctx.anno_store` |
| `state_store` (standalone) | `ctx.state_store` |
| `tts_cache` (standalone) | `ctx.tts_cache` |
| `ai_doc_service` (standalone) | `ctx.ai_doc_service` |

All references updated in routes and main(). Helper functions `_has_root()` and `_require_root()` now use `ctx.root`.

## Services Through Context

- `ctx.anno_store` — used in annotations routes, summarize routes
- `ctx.state_store` — used in startup, root routes, search routes
- `ctx.tts_cache` — used in TTS routes, cache stats routes
- `ctx.ai_doc_service` — used in eligibility, summarize, chat routes

## AI Providers Through Context

- `ctx.ai_text_provider` — set in `main()` via `ai_factory.make_active()`
- `ctx.ai_tts_provider` — set in `main()` via `ai_factory.make_tts()`
- Accessed via `_ai_require_text()` and `_ai_require_tts()` helpers

## Tray Through Context

- `ctx.tray_controller` — set in `main()` after tray starts
- `_request_app_shutdown()` stops tray and sets `ctx.tray_controller = None`

## Deferred Globals

The following remain as module-private (background task) variables, intentionally deferred to a future `LIFECYCLE-EXTRACT-V1`:

- `_preconvert_task`
- `_preconvert_status`
- `_prebuild_task`
- `_prebuild_root`
- `_background_root`
- `_warm_task`
- `_search_index_loaded_root`
- `_last_search_index_save_at`
- `_search_index_save_lock`

These don't need to be in `AppContext` for this baseline — they are pure internal async task handles.

## API Compatibility Review

All routes remain in `server.py` with unchanged behavior:
- `GET /api/tree`, `POST /api/root`, `GET /api/file` — unchanged
- `GET /api/cache/stats`, `POST /api/cache/cleanup` — unchanged
- `GET /api/ai/status`, `POST /api/ai/summarize`, `POST /api/ai/chat`, `POST /api/ai/tts` — unchanged
- `GET /api/anno/all`, `GET /api/anno`, `PATCH /api/anno`, `PUT /api/anno/palette` — unchanged
- `GET /api/health`, `GET /api/version`, `GET /api/root` — unchanged
- `POST /api/shutdown`, `POST /api/reveal`, `POST /api/pick-folder` — unchanged

## Dev Smoke

| Test | Result |
|------|--------|
| `python -m compileall .` | PASS |
| `APP_CONTEXT_IMPORT_PASS` | PASS |
| `APP_CONTEXT_CONTENT_PASS` | PASS |
| `APP_CONTEXT_CONSTRUCTION_PASS` | PASS |
| `NO_DUPLICATE_RUNTIME_GLOBALS_PASS` | PASS |
| `APP_CONTEXT_DEV_SMOKE_PASS` | PASS |
| Shutdown | PASS |

Smoke verified: `/api/health`, `/api/version`, `/api/root` POST, `/api/tree`, `/api/cache/stats`, `/api/ai/status`

## Packaging Review

Build succeeded — all 8 verification checks passed. Static assets bundled correctly at `_internal/src/frontend/static/`.

## Forbidden Changes Review

- Routes not split: PASS (all routes remain in server.py)
- Frontend unchanged: PASS (src/frontend/static not modified)
- Backend services unchanged: PASS (src/backend/services/** not modified)
- src.ai unchanged: PASS
- Packaging/spec files unchanged: PASS
- Generated artifacts not committed: PASS

## Known Issues

None.

## Decision

**PASS**
