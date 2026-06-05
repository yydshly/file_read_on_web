# Review: SERVER-FINAL-SCOPE-AUDIT-V1

## Summary

Audited the final remaining scope of `server.py` after all nine functional route groups have been extracted into dedicated modules. `server.py` now contains only entrypoint wiring, path setup, context initialization, router registration coordination, and lifecycle/launch helpers. No functional API routes remain in `server.py`. A modest amount of dead import code was identified.

## Baseline

```
4d2be17 Split preconvert route and worker
```

Working tree is clean; no uncommitted changes.

## Current server.py Role

`server.py` serves as the application entrypoint, wiring layer, and lifecycle coordinator. It:
- Computes all path constants (`APP_DIR`, `DATA_DIR`, `CACHE_DIR`, etc.)
- Creates `AppContext` and all route state objects
- Registers all API routers via `app.include_router`
- Defines lifecycle hooks (`_on_startup`, `_on_shutdown`)
- Coordinates background task cancellation across all route states
- Implements CLI parsing, duplicate-instance detection, browser/tray launch, and graceful shutdown

## Remaining Inventory

### Functions (top-level, line-sorted)

| Line | Name | Classification |
|------|------|---------------|
| 52 | `_ensure_stdio_for_noconsole` | ENTRYPOINT_BOOTSTRAP |
| 65 | `_app_base_dir` | PATH_MODEL |
| 71 | `_resource_base_dir` | PATH_MODEL |
| 77 | `_is_writable_dir` | PATH_MODEL |
| 88 | `_data_base_dir` | PATH_MODEL |
| 150 | `_load_config` | CONFIG_LOADING |
| 161 | `_has_root` | APP_CONTEXT_WIRING |
| 189 | `_require_root` | APP_CONTEXT_WIRING |
| 195 | `_safe_resolve` | APP_CONTEXT_WIRING |
| 280 | `_stop_background_tasks` | BACKGROUND_TASK_COORDINATION |
| 294 | `_on_startup` | LIFECYCLE_HOOKS |
| 301 | `_on_shutdown` | LIFECYCLE_HOOKS |
| 319 | `_open_app_url` | BROWSER_LAUNCH |
| 345 | `_open_browser_when_ready` | BROWSER_LAUNCH |
| 364 | `_resolve_initial_root` | APP_CONTEXT_WIRING |
| 392 | `_is_our_service_running` | ENTRYPOINT_BOOTSTRAP |
| 414 | `_delayed_exit` | LIFECYCLE_HOOKS |
| 426 | `_request_app_shutdown` | LIFECYCLE_HOOKS |
| 474 | `main` | ENTRYPOINT_BOOTSTRAP |

No classes remain in `server.py`.

### Import Classification

| Import | Status | Notes |
|--------|--------|-------|
| `from pydantic import BaseModel` | CONFIRMED_UNUSED | Used only in `ai_routes.py` |
| `from typing import Any` | CONFIRMED_UNUSED | Not referenced in server.py |
| `import asyncio` | CONFIRMED_UNUSED | Route modules use it; server.py does not |
| `import json` | CONFIRMED_UNUSED | Not referenced in server.py |
| `import logging` | CONFIRMED_UNUSED | Not referenced in server.py |
| `import subprocess` | CONFIRMED_UNUSED | Not referenced in server.py |
| `from src.ai import tasks as ai_tasks` | CONFIRMED_UNUSED | Used only in `ai_routes.py` |
| `from src.ai.base import Message as AIMessage, CapabilityNotSupported` | CONFIRMED_UNUSED | Used only in `ai_routes.py` |
| `from src.backend.services.ai_document import build_ai_status` | CONFIRMED_UNUSED | Used only in `ai_routes.py` |
| `from src.backend.services import annotations as annotations_mod` | USED | `anno_store = annotations_mod.AnnotationStore(...)` at line 115 |
| `from src.backend.services import converter` | USED | Passed to route factories |
| `from src.backend.services import search as search_mod` | USED | Passed to `SearchRouteState` |
| `from src.backend.domain.app_metadata import APP_ID, APP_NAME, APP_VERSION, RELEASE_BASELINE` | USED | Used in `main()` and router factories |
| `from src.backend.routes.*` | USED | All router factories |
| `from src.backend.infra.*` | USED | Logging, safe I/O |
| `from src.backend.services.runtime_state import RuntimeStateStore` | USED | `state_store = RuntimeStateStore(...)` |
| `from src.backend.services.tts_cache import TtsCache` | USED | `tts_cache = TtsCache(...)` |
| `from src.backend.app_context import AppContext, AppPaths` | USED | `ctx = AppContext(...)` |
| `from src.ai import factory as ai_factory` | USED | `ctx.ai_text_provider = ai_factory.make_active(...)` |
| `from src.backend.services.ai_document import AiDocumentService` | USED | `ai_doc_service = AiDocumentService(...)` |
| `from typing import Optional` | USED | `_resolve_initial_root(cli_root: Optional[str])` |
| `import socket` | USED | `_is_our_service_running` |
| `import threading` | USED | `_open_browser_when_ready`, `_delayed_exit` |
| `import time` | USED | `time.time()` calls in logging |
| `import webbrowser` | USED | `_open_app_url` |
| `import argparse` | USED | `main()` CLI parsing |
| `import os` | USED | `os.startfile`, `os.walk`, path ops |
| `from pathlib import Path` | USED | All path constants |
| `from fastapi import FastAPI, HTTPException` | USED | `app = FastAPI()`, `HTTPException` in `_require_root` |

## Route Decorator Scan

Only two decorators remain in `server.py`, both lifecycle hooks:

```
293:@app.on_event("startup")
300:@app.on_event("shutdown")
```

No functional API route decorators (`@app.get`, `@app.post`, etc.) remain. ✓

## Route Registration Review

All 34 routes (including FastAPI auto-routes) are registered via the included routers. All required API routes are present:

- `GET /api/preconvert/status` ✓
- `GET /api/search`, `GET /api/search/status`, `GET /api/search/skipped`, `GET /api/search/scanned`, `POST /api/search/rebuild` ✓
- `GET /api/tree`, `GET /api/file`, `GET /api/raw` ✓
- `GET /api/anno/all`, `GET /api/anno`, `PATCH /api/anno`, `PUT /api/anno/palette` ✓
- `GET /api/ai/status`, `POST /api/ai/summarize`, `POST /api/ai/chat`, `POST /api/ai/tts`, `GET /api/ai/tts/stats`, `POST /api/ai/tts/clear` ✓
- `POST /api/cache/clear`, `GET /api/cache/stats`, `POST /api/cache/cleanup` ✓
- `GET /`, `/favicon.ico`, `/static` ✓
- `GET /api/health`, `GET /api/version` ✓
- `GET /api/root`, `POST /api/root`, `POST /api/reveal`, `POST /api/shutdown`, `POST /api/pick-folder` ✓

## Import / Dead Code Review

Nine unused imports were identified (see table above). These imports exist in `server.py` because the symbols they reference are re-exported for use by the route modules, but the route modules import them directly from their own sources. The imports are harmless but incorrect — they suggest a coupling that does not actually exist.

Recommended cleanup: `SERVER-CLEANUP-UNUSED-IMPORTS-V1`.

## Lifecycle Extraction Assessment

| Function | Recommendation |
|----------|---------------|
| `_stop_background_tasks` | KEEP_IN_SERVER — coordinates cancellation across all route states |
| `_request_app_shutdown` | KEEP_IN_SERVER — orchestrates flush, soffice kill, tray stop, and exit |
| `_on_startup` | KEEP_IN_SERVER — FastAPI lifecycle hook; must live near `app` |
| `_on_shutdown` | KEEP_IN_SERVER — FastAPI lifecycle hook; must live near `app` |
| `_open_app_url` | KEEP_IN_SERVER — platform-specific browser open logic |
| `_open_browser_when_ready` | KEEP_IN_SERVER — launch helper tied to server startup timing |
| `_resolve_initial_root` | KEEP_IN_SERVER — CLI/state/default resolution tied to `main()` |
| `main` | KEEP_IN_SERVER — CLI entry point; must remain |

**Conclusion:** None of the remaining functions are good extraction candidates. Each is either tightly coupled to the `main()` CLI startup sequence, requires access to all route state objects simultaneously, or is a FastAPI lifecycle hook that must live near the `app` definition. Extracting any of them would increase coupling, not reduce it.

## App Factory Assessment

Introducing `src/backend/app_factory.py` would centralize app construction. Potential responsibilities:
- Create `AppContext`
- Instantiate all route state objects
- Register all routers
- Register lifecycle hooks
- Return `(app, ctx, route_states)` bundle

**Risk: MEDIUM.** The benefit is moderate — `main()` would become slightly thinner. However, `main()` is already clean enough (no functional routes, no inline request handlers). The route state instantiation already happens inline and would need to move. Circular import risk is non-trivial given the `app_context` ↔ route state dependency.

**Conclusion:** An app factory would reduce some wiring noise but adds a new import dependency layer. Given that `server.py` is already the clear entrypoint and wiring layer, the extraction would trade one form of coupling for another without significant gain. **Not recommended at this time.**

## Recommended Server Role

**Option A** — `server.py` remains full entrypoint + wiring file. No further structural extraction needed. Only remove unused imports.

This is the correct role for `server.py` at this stage of the codebase. All functional logic is correctly partitioned into route modules. The remaining code in `server.py` is exactly what an entrypoint/wiring file should contain.

## Known Issues Review

| Issue | Status |
|-------|--------|
| search cache concurrency bug fixed | Not assessed in this task |
| `/api/tree recursive=1` still present | Not assessed in this task |
| prompt caching not implemented | Not implemented by design |
| README out of sync with current src/routes architecture | Not assessed in this task |
| `docs/INDEX.md` missing | Not assessed in this task |
| `reports/reviews/` volume growing | Confirmed; this task adds another review |
| possible unused imports after route split | **Confirmed** — 9 unused imports identified |
| lifecycle extraction deferred | **Deferred** — assessed as low-value, KEEP_IN_SERVER |
| packaging check after full route split | Not assessed in this task |

## Recommended Next Task

**SERVER-CLEANUP-UNUSED-IMPORTS-V1**

Nine imports in `server.py` are confirmed unused (`BaseModel`, `Any`, `asyncio`, `json`, `logging`, `subprocess`, `ai_tasks`, `AIMessage`, `CapabilityNotSupported`, `build_ai_status`). Removing them reduces misleading import coupling and makes the actual dependencies clearer. This is a safe, low-risk cleanup with no behavioral change.

## Validation

- `python -m compileall .`: EXIT:0 ✓
- `SERVER_FINAL_SCOPE_IMPORT_PASS` ✓
- `SERVER_FINAL_SCOPE_ROUTES_PASS` ✓
- `SERVER_FINAL_SCOPE_NO_ROUTE_DECORATORS_PASS` ✓

## Forbidden Changes Review

No source files were modified during this audit. All work was read-only inspection followed by report creation.

## Decision

PASS
