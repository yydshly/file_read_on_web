# Review: SERVER-CLEANUP-UNUSED-IMPORTS-V1

## Summary

Removed nine confirmed unused imports from `server.py` following the `SERVER-FINAL-SCOPE-AUDIT-V1` finding that these imports were re-exported through route modules but never used in `server.py` itself.

## Baseline

```
930128a Audit final server scope
```

Working tree was clean before this task.

## Removed Imports

| Removed Import | Reason |
|----------------|--------|
| `import asyncio` | No `asyncio.` references in server.py |
| `import json` | No `json.` references in server.py |
| `import logging` | No `logging.` references in server.py |
| `import subprocess` | No `subprocess.` references in server.py |
| `from typing import Any` | `Any` not referenced in server.py |
| `from pydantic import BaseModel` | `BaseModel` not referenced; used only in `ai_routes.py` |
| `from src.ai import tasks as ai_tasks` | `ai_tasks` not referenced; used only in `ai_routes.py` |
| `from src.ai.base import Message as AIMessage, CapabilityNotSupported` | Neither symbol referenced; used only in `ai_routes.py` |
| `from src.backend.services.ai_document import build_ai_status` | `build_ai_status` not referenced; used only in `ai_routes.py` |

## Preserved Imports

All imports that are actually used by `server.py` were preserved:

- Standard library: `argparse`, `os`, `socket`, `sys`, `threading`, `time`, `webbrowser`, `Path` from `pathlib`, `Optional` from `typing`
- FastAPI: `FastAPI`, `HTTPException`
- Route modules: all nine `create_*_router` factories and three `*RouteState` classes
- App infrastructure: `AppContext`, `AppPaths`, `init_logging`, `get_logger`, `read_json`, `RuntimeStateStore`, `TtsCache`
- Services: `annotations_mod`, `converter`, `search_mod`, `AiDocumentService`
- AI: `ai_factory`
- Metadata: `APP_ID`, `APP_NAME`, `APP_VERSION`, `RELEASE_BASELINE`
- Tray: `TrayController` (conditional import)

## Route Registration Review

All 34 routes remain registered and functional. No route registrations were touched.

## Decorator Review

Only `@app.on_event("startup")` and `@app.on_event("shutdown")` remain in `server.py` — the FastAPI lifecycle hooks. No functional API route decorators (`@app.get`, `@app.post`, etc.) are present.

## Validation

- `python -m compileall .`: EXIT:0 ✓
- `SERVER_CLEANUP_IMPORT_PASS` ✓
- `SERVER_CLEANUP_CONTENT_PASS` ✓
- `SERVER_CLEANUP_ROUTES_PASS` ✓
- `SERVER_CLEANUP_DECORATOR_PASS` ✓
- `SERVER_CLEANUP_DEV_SMOKE_PASS` — `/api/health`, `/api/version`, `/api/root`, `/api/cache/stats`, `/api/ai/status`, `/api/preconvert/status` all responded 200 ✓
- `SERVER_CLEANUP_SHUTDOWN_REQUESTED` ✓

## Dev Smoke

Server started cleanly with `python server.py --no-browser --no-tray`. All six smoke endpoints returned 200 with valid JSON. Shutdown endpoint confirmed functional.

## Forbidden Changes Review

- No `src/**` files modified ✓
- No route registration changes ✓
- No lifecycle behavior changes ✓
- No frontend changes ✓
- No packaging changes ✓
- No new features or behavioral changes ✓

## Known Issues

None.

## Decision

PASS
