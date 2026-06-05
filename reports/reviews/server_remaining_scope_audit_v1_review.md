# Review: SERVER-REMAINING-SCOPE-AUDIT-V1

## Summary

Audit of remaining `server.py` content after route split milestones at commit `3b29789 Split static route registration`. Working tree clean. All validations pass. No source modifications made.

---

## Baseline

```
commit  3b29789 Split static route registration
branch  main
origin  https://github.com/yydshly/file_read_on_web.git
```

Already split routes:
- `src/backend/routes/runtime_routes.py` — runtime/health/version
- `src/backend/routes/cache_routes.py` — cache stats/clear/cleanup
- `src/backend/routes/annotation_routes.py` — annotations CRUD
- `src/backend/routes/ai_routes.py` — AI status/summarize/chat/tts
- `src/backend/routes/system_routes.py` — root/shutdown/reveal/pick-folder
- `src/backend/routes/static_routes.py` — static file serving

---

## Current Route Split Status

All previously-split route groups are correctly extracted via `include_router` from their respective modules. No `@app.*` decorators for those groups remain in `server.py`.

**Remaining `@app.*` decorators in `server.py`:**

| Line | Decorator | Route |
|------|-----------|-------|
| 518 | `@app.on_event("startup")` | `_on_startup` |
| 525 | `@app.on_event("shutdown")` | `_on_shutdown` |
| 538 | `@app.get("/api/tree")` | `api_tree` |
| 555 | `@app.get("/api/preconvert/status")` | `api_preconvert_status` |
| 565 | `@app.get("/api/file")` | `api_file` |
| 605 | `@app.get("/api/raw")` | `api_raw` |
| 630 | `@app.get("/api/search")` | `api_search` |
| 646 | `@app.get("/api/search/status")` | `api_search_status` |
| 655 | `@app.get("/api/search/skipped")` | `api_search_skipped` |
| 662 | `@app.get("/api/search/scanned")` | `api_search_scanned` |
| 671 | `@app.post("/api/search/rebuild")` | `api_search_rebuild` |

---

## Remaining server.py Inventory

### ENTRYPOINT_AND_PATH_MODEL
- `_ensure_stdio_for_noconsole()` — lines 51–61
- `_app_base_dir()` — lines 64–67
- `_resource_base_dir()` — lines 70–73
- `_is_writable_dir()` — lines 76–84
- `_data_base_dir()` — lines 87–99
- `APP_DIR`, `DATA_DIR`, `RESOURCE_DIR`, `STATIC_DIR`, `CACHE_DIR`, `TTS_CACHE_DIR`, `CONFIG_PATH`, `STATE_PATH`, `ANNO_PATH`, `SEARCH_INDEX_PATH`, `DEFAULT_ROOT_REL` — lines 102–112
- `main()` — lines 843–984

### APP_CONTEXT_AND_SERVICE_WIRING
- `anno_store`, `tts_cache`, `state_store`, `ai_doc_service` — lines 114–117
- `ctx = AppContext(...)` — lines 120–138
- `app = FastAPI()` — line 140
- AI provider wiring in `main()` — lines 917–930

### HELPERS_STILL_USED_BY_ROUTES
- `_has_root()` — lines 166–167
- `_require_root()` — lines 194–197
- `_safe_resolve()` — lines 200–211
- `_skip_tree_entry()` — lines 240–257
- `_build_tree()` — lines 260–281
- `_iter_files_in_tree_order()` — lines 284–300

### TREE_ROUTES
- `api_tree()` — line 538 (route: `/api/tree`)
- `_start_warm_after_tree()` — line 482
- `_restart_warm()` — line 491
- `_cancel_warm_task()` — line 502

### FILE_PREVIEW_ROUTES
- `api_file()` — line 565 (route: `/api/file`)
- `api_raw()` — line 605 (route: `/api/raw`)

### SEARCH_ROUTES
- `api_search()` — line 630 (route: `/api/search`)
- `api_search_status()` — line 646 (route: `/api/search/status`)
- `api_search_skipped()` — line 655 (route: `/api/search/skipped`)
- `api_search_scanned()` — line 662 (route: `/api/search/scanned`)
- `api_search_rebuild()` — line 671 (route: `/api/search/rebuild`)
- `_maybe_save_search_index()` — lines 620–627
- `_ensure_search_index_loaded()` — lines 507–515

### PRECONVERT_OR_PREBUILD_LIFECYCLE
- `_preconvert_status` dict — lines 145–148
- `_preconvert_task` — line 145
- `_scan_office_files()` — lines 305–325
- `_preconvert_worker()` — lines 328–367
- `_start_preconvert()` — lines 370–377
- `api_preconvert_status()` — line 555 (route: `/api/preconvert/status`)

### BACKGROUND_TASK_STATE
- `_prebuild_task` — line 381
- `_prebuild_root` — line 382
- `_background_root` — line 383
- `_warm_task` — line 384
- `_search_index_loaded_root` — line 385
- `_warm_office_candidates()` — lines 441–464
- `_warm_office_after_tree()` — lines 467–479
- `_start_prebuild()` — lines 419–425
- `_prebuild_worker()` — lines 388–416
- `_stop_background_tasks()` — lines 428–438

### STARTUP_SHUTDOWN_LIFECYCLE
- `_on_startup()` — lines 518–522 (empty stub; intentional — startup prebuild disabled)
- `_on_shutdown()` — lines 525–533
- `_request_app_shutdown()` — lines 795–828
- `_is_our_service_running()` — lines 761–780
- `_resolve_initial_root()` — lines 733–758
- `_delayed_exit()` — lines 783–789

### TRAY_AND_BROWSER_LAUNCH
- `_open_app_url()` — lines 688–711
- `_open_browser_when_ready()` — lines 714–730
- Tray wiring in `main()` — lines 937–957

### DEAD_OR_ORPHANED_CODE
- `_load_config()` — lines 155–158 (called once in `main()` line 917; config is read and then fields set on ctx — but runtime code does not re-read it)

---

## Remaining Route Groups

### Tree Routes
- **Paths:** `/api/tree`
- **Helper functions:** `_build_tree`, `_skip_tree_entry`, `_iter_files_in_tree_order`, `_has_root`, `_require_root`, `_safe_resolve`
- **Mutable globals:** `ctx.root`, `_background_root`, `_warm_task`
- **AppContext fields used:** `ctx.root`, `ctx.preconvert_enabled`, `ctx.state_store`
- **Service modules:** `converter`
- **Background tasks touched:** `_warm_task`, `_start_warm_after_tree`, `_restart_warm`
- **Risk level:** MEDIUM
- **Recommended split task name:** `BACKEND-ROUTES-SPLIT-FILE-TREE-V1`

**Reasoning:** Tree routes are tightly coupled to `_build_tree`, `_skip_tree_entry`, `_iter_files_in_tree_order`, `_warm_office_candidates`, and background warm tasks. The warm task chain (`_start_warm_after_tree` → `_restart_warm` → `_cancel_warm_task`) touches file route territory too (it pre-warms office files based on user position). Splitting tree independently requires extracting the warm task lifecycle cleanly, or coupling the split with file routes.

---

### File Preview Routes
- **Paths:** `/api/file`, `/api/raw`
- **Helper functions:** `_safe_resolve`, `_require_root`, `_has_root`
- **Mutable globals:** `_warm_task`, `ctx.root`, `ctx.preconvert_enabled`
- **AppContext fields used:** `ctx.root`, `ctx.state_store`, `ctx.preconvert_enabled`, `ctx.tts_cache`, `ctx.ai_doc_service`
- **Service modules:** `converter`
- **Background tasks touched:** `_restart_warm`, `_cancel_warm_task`
- **Risk level:** MEDIUM
- **Recommended split task name:** `BACKEND-ROUTES-SPLIT-FILE-TREE-V1`

**Reasoning:** File routes are relatively clean but deeply entangled with the warm-office background task system. They cannot be fully extracted without also handling the warm task callbacks that bridge file navigation to background pre-warming. Combining file + tree in one split (`BACKEND-ROUTES-SPLIT-FILE-TREE-V1`) is the natural seam.

---

### Search Routes
- **Paths:** `/api/search`, `/api/search/status`, `/api/search/skipped`, `/api/search/scanned`, `/api/search/rebuild`
- **Helper functions:** `_ensure_search_index_loaded`, `_maybe_save_search_index`
- **Mutable globals:** `_search_index_loaded_root`, `_last_search_index_save_at`
- **AppContext fields used:** `ctx.root`
- **Service modules:** `search_mod`
- **Background tasks touched:** `_prebuild_task`, `_prebuild_root`
- **Risk level:** LOW
- **Recommended split task name:** `BACKEND-ROUTES-SPLIT-SEARCH-V1`

**Reasoning:** Search routes are self-contained. They call `search_mod` functions and manage `_prebuild_task`. The `_prebuild_worker` and `_start_prebuild` are closely tied to search but do not touch tree/file routes. Low coupling to other route groups.

---

### Preconvert / Prebuild Assessment

**Preconvert status route** (`/api/preconvert/status`) is in `server.py` but the actual preconvert background logic (`_preconvert_worker`, `_start_preconvert`) is also in `server.py`. The preconvert lifecycle is entirely self-contained within `server.py`.

- **Risk level:** MEDIUM
- Preconvert is coupled to: `_scan_office_files`, `_preconvert_worker`, `_start_preconvert`, `_require_root`, `_has_root`, `converter`, `CACHE_DIR`
- Extracting preconvert routes requires also extracting its background worker and status state

**Search prebuild** (`_prebuild_worker`, `_start_prebuild`) is tightly coupled to search routes — it populates the search index that `api_search` reads.

- **Should remain:** within search routes split or as a shared background module

---

## Lifecycle / Shutdown Assessment

| Item | Current Status | Safe to Extract? |
|------|----------------|------------------|
| `_on_startup` | Empty stub (startup prebuild disabled intentionally) | N/A — already no-op |
| `_on_shutdown` | Calls `_stop_background_tasks` + `ctx.state_store.flush(force=True)` | Must stay in server.py until background tasks are extracted |
| `_stop_background_tasks` | Cancels `_preconvert_task`, `_prebuild_task`, `_warm_task` | Must stay until all three background systems are extracted |
| `_request_app_shutdown` | Flushes state, kills orphan soffice, stops tray, exits | Entry-point specific; should never move |
| `main()` | Full entry point; initializes everything | Entry-point specific; should never move |
| Tray controller init | In `main()` | Entry-point specific |
| Browser launch | `_open_browser_when_ready` in `main()` | Entry-point specific |
| Preconvert task | Global `_preconvert_task` + `_preconvert_status` | Should be extracted with preconvert routes |
| Prebuild task | Global `_prebuild_task` + `_prebuild_root` | Should be extracted with search routes |
| Warm task | Global `_warm_task` + `_background_root` | Should be extracted with tree/file routes |

**Conclusion:** `_request_app_shutdown`, `main()`, tray init, and browser launch are entrypoint-specific and should never move. `_on_shutdown` and `_stop_background_tasks` must remain in `server.py` until all three background task groups (preconvert, prebuild, warm) are extracted. The lifecycle functions are tightly coupled to background task state.

---

## Background State Assessment

| Global | Type | Route Group | Purpose |
|--------|------|-------------|---------|
| `_preconvert_task` | `asyncio.Task\|None` | Preconvert | Background office→PDF preconvert |
| `_preconvert_status` | `dict` | Preconvert | Status dict for API |
| `_prebuild_task` | `asyncio.Task\|None` | Search | Background search index prebuild |
| `_prebuild_root` | `Path\|None` | Search | Root at time of prebuild start |
| `_background_root` | `Path\|None` | Tree/Warm | Root at time of warm start |
| `_warm_task` | `asyncio.Task\|None` | Tree/Warm | Background office pre-warm |
| `_search_index_loaded_root` | `Path\|None` | Search | Tracks which root's index is loaded |
| `_last_search_index_save_at` | `float` | Search | Debounce timer for index saves |
| `_search_index_save_lock` | `threading.Lock` | Search | Thread-safe save coordination |

**All background state is intertwined with routes.** Extracting any route group requires also extracting its associated background globals and workers.

---

## Dead or Orphaned Code

- `_load_config()` (lines 155–158): Only called once at `main()` line 917. The result is used to initialize `ctx.ai_text_provider` and `ctx.ai_tts_provider` directly — the function itself is not called by any route. It could theoretically be inlined into `main()`, but it is small and harmless.

---

## Known Risk Review

1. **file/tree/search routes still coupled to root/path/cache/search helpers** — CONFIRMED. `_has_root`, `_require_root`, `_safe_resolve` are used by all remaining route groups. These helpers depend on `ctx.root`.

2. **search.py `_get_text` cache concurrency issue remains or not** — Cannot confirm from `server.py` audit alone. Not present in `server.py`.

3. **safeio.atomic_write_json fixed tempfile name issue remains or not** — Not visible in `server.py`.

4. **`/api/tree` default `recursive=1` remains or not** — CONFIRMED: line 539 shows `async def api_tree(path: str = "", recursive: int = 1)`. Default is still `1` (recursive). This was a known risk item.

5. **Prompt caching not implemented** — Not in scope of this audit.

6. **README may be out of sync after route/module split** — Not verified in this audit.

7. **docs/ may need INDEX.md** — Not in scope of this audit.

8. **reports/reviews volume is growing** — Confirmed; this is the 34th review report.

---

## Recommended Next Task

**`BACKEND-ROUTES-SPLIT-FILE-TREE-V1`**

Rationale:
- Search routes (`/api/search*`) are the most self-contained remaining group — risk LOW — but there is value in completing the file+tree+search trio together since all three share the `_has_root`/`_require_root`/`_safe_resolve` helper pattern.
- Tree routes and file routes are deeply entangled through the warm-office background task (`_warm_task`, `_restart_warm`, `_cancel_warm_task`). They must be split together.
- Search routes can be split independently but would leave tree+file as a larger, more complex follow-up.
- The preconvert status route is also in `server.py` but preconvert background workers are tightly coupled to `server.py` lifecycle; extracting it now would be premature.
- Splitting file+tree together gives a clean extraction boundary: all warm-task state moves with it, search stays behind in `server.py`.

**Recommended extraction order:**
1. `BACKEND-ROUTES-SPLIT-FILE-TREE-V1` ← next
2. `BACKEND-ROUTES-SPLIT-SEARCH-V1`
3. `LIFECYCLE-EXTRACT-V1` (after all route groups are extracted)

---

## Validation

| Check | Result |
|-------|--------|
| `git status -sb` before audit | CLEAN (working tree clean at baseline 3b29789) |
| `python -m compileall .` | PASS |
| `SERVER_REMAINING_AUDIT_IMPORT_PASS` | PASS |
| `SERVER_REMAINING_AUDIT_ROUTES_PASS` | PASS |
| Changed files scope | PASS (only `reports/reviews/server_remaining_scope_audit_v1_review.md`) |

---

## Forbidden Changes Review

No source files were modified. All route decorators for already-split groups confirmed absent. No new endpoints, features, or behaviors introduced.

---

## Decision

**PASS**

All validations pass. Working tree clean. Audit complete. No source files modified.
