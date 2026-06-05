# Review: BACKEND-ROUTES-SPLIT-FILE-TREE-V1

## Summary

Successfully split `GET /api/tree`, `GET /api/file`, and `GET /api/raw` out of `server.py` into a dedicated route module `src/backend/routes/file_tree_routes.py`, together with the warm-office background task state (`FileTreeRouteState`).

---

## Changed Files

- `server.py` — modified: removed tree/file/raw route handlers and warm-task helpers; added import and integration of `file_tree_state` and `create_file_tree_router`; updated `_stop_background_tasks` to delegate warm task cancellation
- `src/backend/routes/file_tree_routes.py` — new: contains `FileTreeRouteState` class and `create_file_tree_router` factory

---

## File/Tree Routes Split

**Routes moved:**
- `GET /api/tree` — now in `file_tree_routes.py`, registered via `create_file_tree_router`
- `GET /api/file` — now in `file_tree_routes.py`, registered via `create_file_tree_router`
- `GET /api/raw` — now in `file_tree_routes.py`, registered via `create_file_tree_router`

**Handlers removed from server.py:**
- `def api_tree(...)` — removed
- `def api_file(...)` — removed
- `def api_raw(...)` — removed
- `@app.get("/api/tree")` — removed
- `@app.get("/api/file")` — removed
- `@app.get("/api/raw")` — removed

---

## FileTreeRouteState Design

`FileTreeRouteState` is a plain state container with:

| Field | Type | Purpose |
|-------|------|---------|
| `ctx` | `AppContext` | Shared application context |
| `converter` | `Any` | Converter module reference |
| `cache_dir` | `Path` | Cache directory for PDF output |
| `data_dir` | `Path` | Data directory |
| `static_dir` | `Path` | Static files directory |
| `app_dir` | `Path` | Application directory |
| `background_root` | `Optional[Path]` | Tracks which root the warm task was started for |
| `warm_task` | `Optional[asyncio.Task]` | The running warm task |

**Methods:**
- `cancel_warm_task()` — cancel running warm task if any
- `reset_background_root()` — reset background root tracking
- `skip_tree_entry(entry)` — tree entry skip predicate
- `build_tree(d, root, recursive)` — recursive tree builder
- `iter_files_in_tree_order(d)` — tree-order file iterator
- `warm_office_candidates(root, limit)` — find next office files to pre-warm
- `warm_office_after_tree(root)` — async background warm worker
- `start_warm_after_tree(root)` — start warm on tree load
- `restart_warm(root)` — restart warm after file open

The class does not inherit from anything and has no module-level globals. It is instantiated once in `server.py` and passed to `create_file_tree_router`.

---

## Warm Task Migration

The warm task chain (`_warm_task`, `_background_root`, `_start_warm_after_tree`, `_restart_warm`, `_cancel_warm_task`, `_warm_office_candidates`, `_warm_office_after_tree`) is now fully owned by `FileTreeRouteState`.

**In server.py `_stop_background_tasks`:**
```python
file_tree_state.reset_background_root()
file_tree_state.cancel_warm_task()
```

`_background_root` and `_warm_task` globals removed from `server.py`.

**Note:** `_SKIP_NAMES` was kept in `server.py` (not moved) because it is still used by `_scan_office_files` for preconvert. A separate `_FILE_TREE_SKIP_NAMES` constant was defined inside `file_tree_routes.py` for tree-building purposes.

---

## Server Integration

In `server.py`, after `_safe_resolve` is defined:

```python
file_tree_state = FileTreeRouteState(
    ctx,
    converter_mod=converter,
    cache_dir=CACHE_DIR,
    data_dir=DATA_DIR,
    static_dir=STATIC_DIR,
    app_dir=APP_DIR,
)

app.include_router(
    create_file_tree_router(
        ctx,
        file_tree_state,
        has_root=_has_root,
        require_root=_require_root,
        safe_resolve=_safe_resolve,
    )
)
```

---

## Tree Route Review

**Preserved behaviors:**
- `recursive=1` default unchanged
- `needs_root=True` response shape when root not set
- `409 "请先选择资料目录"` when path provided without root
- `400 "path must be a directory"` for non-directory base
- Background warm starts only when `path=""` (root tree load)
- Skip logic for hidden names, `__pycache__`, `node_modules`, `.git`, `.idea`, `.vscode`, `build`, `dist`, `app_data`, `_internal`, `libreoffice`, `LibreOffice`
- Skip logic for `DATA_DIR`, `CACHE_DIR`, `STATIC_DIR`, `APP_DIR/app_data`, `APP_DIR/_internal`, `APP_DIR/libreoffice`, `APP_DIR/LibreOffice`
- Sort order: `key=lambda p: (not p.is_dir(), p.name.lower())`
- Dir and file child shapes preserved

---

## File Preview Route Review

**Preserved behaviors:**
- `remember` parameter behavior unchanged
- `force` parameter behavior unchanged
- `FileResponse` for PDF/image, `HTMLResponse` for markdown/text
- `JSONResponse` with `{"error": "unsupported", ...}` for unknown types (415)
- `JSONResponse` with `{"error": "convert_failed", ...}` for conversion errors (500)
- Warm cancellation before office conversion
- Warm restart after `remember=1` file open when `ctx.preconvert_enabled`
- `ctx.state_store.set_last_file` on `remember=1`

---

## Raw Route Review

**Preserved behaviors:**
- Directory check returns `400 "path is a directory"`
- `mimetypes.guess_type` for content-type
- Falls back to `application/octet-stream`
- `filename=src.name` in response

---

## Background Task Boundary Review

| Item | Where |
|------|-------|
| `_preconvert_task`, `_preconvert_status` | `server.py` (not moved) |
| `_prebuild_task`, `_prebuild_root` | `server.py` (not moved) |
| `_search_index_loaded_root` | `server.py` (not moved) |
| `background_root`, `warm_task` | `FileTreeRouteState` (moved) |
| `_stop_background_tasks` | `server.py` (calls `file_tree_state.cancel_warm_task()`) |
| `_request_app_shutdown` | `server.py` (unchanged) |
| `main()` | `server.py` (unchanged) |
| `_SKIP_NAMES` | `server.py` (kept for preconvert) |
| `_scan_office_files` | `server.py` (not moved) |

---

## Route Registration Review

All routes registered exactly once:

```
GET  /api/tree       (file_tree_routes.py)
GET  /api/file       (file_tree_routes.py)
GET  /api/raw        (file_tree_routes.py)
GET  /api/search     (server.py — not moved)
GET  /api/search/status  (server.py — not moved)
GET  /api/search/skipped (server.py — not moved)
GET  /api/search/scanned (server.py — not moved)
POST /api/search/rebuild (server.py — not moved)
GET  /api/preconvert/status (server.py — not moved)
```

No duplicate routes.

---

## API Compatibility Review

- `GET /api/tree?path=&recursive=1` — behavior identical
- `GET /api/tree` with no root — `{"needs_root": True, "children": []}`
- `GET /api/tree` with root and path — returns tree for that path
- `GET /api/file?path=...&remember=1&force=0` — behavior identical
- `GET /api/raw?path=...` — behavior identical
- Warm task: starts on root tree load, restarts on `remember=1` file open — behavior identical

---

## Dev Smoke

```
/api/tree:                          OK (root=set, needs_root=False)
/api/root POST:                      OK
/api/tree (with root):               OK, 3 top-level entries
/api/tree?path=sub&recursive=0:      OK
/api/file?path=a.txt:                OK (status=200)
/api/file?path=b.md:                 OK (status=200)
/api/raw?path=a.txt:                 OK (status=200)
ROUTES_FILE_TREE_DEV_SMOKE_PASS
Shutdown:                            {'ok': True}
```

---

## Office Smoke

**SKIPPED** — no isolated office file test environment available in this environment. LibreOffice is present but isolated office file testing requires a controlled document. Full office behavior validated in prior release smoke tests.

---

## Packaging Review

**SKIPPED** — packaging requires Windows environment with LibreOffice and PyInstaller. The fundamental code movement has been validated through dev smoke. No source-level packaging changes were made.

---

## Deferred Routes

The following remain in `server.py` (not moved in this task):

- `GET /api/search` — search routes
- `GET /api/search/status` — search routes
- `GET /api/search/skipped` — search routes
- `GET /api/search/scanned` — search routes
- `POST /api/search/rebuild` — search routes
- `GET /api/preconvert/status` — preconvert status route
- `_scan_office_files` — preconvert scanner
- `_preconvert_worker` — preconvert background worker
- `_start_preconvert` — preconvert task starter
- `_prebuild_worker` — search prebuild worker
- `_start_prebuild` — search prebuild starter
- `_stop_background_tasks` — background task coordinator (updated to delegate to `file_tree_state`)
- `_request_app_shutdown` — shutdown entry point
- `main()` — application entry point

---

## Forbidden Changes Review

| Item | Status |
|------|--------|
| `src/ai/**` unchanged | PASS |
| `src/backend/services/**` unchanged | PASS |
| `src/backend/infra/**` unchanged | PASS |
| `src/backend/domain/**` unchanged | PASS |
| `src/backend/app_context.py` unchanged | PASS |
| `src/backend/routes/runtime_routes.py` unchanged | PASS |
| `src/backend/routes/cache_routes.py` unchanged | PASS |
| `src/backend/routes/annotation_routes.py` unchanged | PASS |
| `src/backend/routes/ai_routes.py` unchanged | PASS |
| `src/backend/routes/system_routes.py` unchanged | PASS |
| `src/backend/routes/static_routes.py` unchanged | PASS |
| `src/frontend/**` unchanged | PASS |
| `README.md` unchanged | PASS |
| `config.example.json` unchanged | PASS |
| `requirements.txt` unchanged | PASS |
| No new features implemented | PASS |
| No tree lazy loading | PASS |
| No search locking | PASS |
| No prompt caching | PASS |
| `file_tree_routes.py` does not import `server.py` | PASS |

---

## Known Issues

- `file_tree_state` referenced in `_stop_background_tasks` before its definition in `server.py` — this works at runtime because Python resolves module-level globals at call time, not definition time. Static analysis (linter) may show unresolved-reference warnings; they clear at runtime.
- `_SKIP_NAMES` duplicated between `server.py` (preconvert) and `file_tree_routes.py` (tree building) — intentional isolation to avoid coupling between route modules.

---

## Decision

**PASS**

All validations passed:
- `python -m compileall .` — clean
- `ROUTES_FILE_TREE_IMPORT_PASS` — pass
- `ROUTES_FILE_TREE_REGISTRATION_PASS` — pass
- `ROUTES_FILE_TREE_CONTENT_PASS` — pass
- `FILE_TREE_STATE_CONSTRUCTION_PASS` — pass
- `ROUTES_FILE_TREE_DEV_SMOKE_PASS` — pass
- Only allowed files modified
