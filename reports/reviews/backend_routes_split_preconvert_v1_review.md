# Review: BACKEND-ROUTES-SPLIT-PRECONVERT-V1

## Summary

Split preconvert-related route/state/worker logic out of `server.py` into a dedicated `preconvert_routes.py` route module. Moved `GET /api/preconvert/status`, the preconvert task/status state, office file scanner, background worker, and start/cancel helpers into `PreconvertRouteState`.

## Changed Files

- `server.py` — removed preconvert module-level variables and route handler; added import, state instantiation, router registration, and cancellation call in `_stop_background_tasks`
- `src/backend/routes/preconvert_routes.py` — new file containing `PreconvertRouteState` and `create_preconvert_router`

## Preconvert Route Split

`GET /api/preconvert/status` is the only endpoint. It returns a snapshot of the preconvert background task's progress. The route handler was removed from `server.py` and re-registered via `app.include_router(create_preconvert_router(ctx, preconvert_route_state))`.

## PreconvertRouteState Design

`PreconvertRouteState` follows the same pattern as `FileTreeRouteState` and `SearchRouteState`:
- Holds mutable task/status state (`preconvert_task`, `preconvert_status`)
- Takes `converter_mod`, `cache_dir`, `data_dir`, `static_dir` as constructor arguments
- Owns `cancel_preconvert_task()` and `start_preconvert()` methods
- `status()` returns the progress-augmented dict for the API response

## Preconvert Worker Migration

`_preconvert_worker` was converted to `PreconvertRouteState.preconvert_worker`:
- Uses `self.converter` instead of the global `converter`
- Uses `self.preconvert_status` instead of module-level `_preconvert_status`
- Uses `self.cache_dir` instead of module-level `CACHE_DIR`
- Uses `self.scan_office_files` instead of the standalone `_scan_office_files`
- Root-abort check uses `self.ctx.root` instead of module-level `ctx.root`

Messages preserved exactly: `"LibreOffice 未安装，跳过预转换"`, `"根目录变更，中止当前任务"`, `"已取消"`, and the completion summary line.

## Scan Behavior Review

`_scan_office_files` was converted to `PreconvertRouteState.scan_office_files`:
- Skips hidden directories and names in `_PRECONVERT_SKIP_NAMES`
- Skips `data_dir`, `cache_dir`, `static_dir` resolve-paths
- Skips hidden files
- Includes only files where `converter.classify(p) == "office"`

Skip names preserved: `__pycache__`, `node_modules`, `.git`, `.idea`, `.vscode`, `build`, `dist`, `app_data`, `_internal`, `libreoffice`, `LibreOffice`.

## Server Integration

After the `search_router` registration block, `preconvert_route_state` is instantiated and the router is included:

```python
preconvert_route_state = PreconvertRouteState(
    ctx,
    converter_mod=converter,
    cache_dir=CACHE_DIR,
    data_dir=DATA_DIR,
    static_dir=STATIC_DIR,
)

app.include_router(
    create_preconvert_router(ctx, preconvert_route_state)
)
```

`_stop_background_tasks` now calls `preconvert_route_state.cancel_preconvert_task()` instead of the old inline cancellation of `_preconvert_task`.

## Shutdown Boundary Review

`_stop_background_tasks` is unchanged in signature and still calls `search_route_state.reset_for_root_change_or_shutdown()`, `search_route_state.cancel_prebuild_task()`, `file_tree_state.reset_background_root()`, `file_tree_state.cancel_warm_task()`, and now also `preconvert_route_state.cancel_preconvert_task()`. All lifecycle functions remain in `server.py`.

## Route Registration Review

`/api/preconvert/status` is registered exactly once via `app.include_router`. No duplicate route exists. All required routes are present.

## API Compatibility Review

`GET /api/preconvert/status` returns exactly the same keys: `running`, `total`, `done`, `current`, `errors`, `started_at`, `finished_at`, `progress`. The `progress` calculation is unchanged: `round(done/total, 3)` when `total > 0`, else `0.0`.

## Dev Smoke

Server started with `python server.py --no-browser --no-tray`. `/api/preconvert/status` responded with all required keys and a `float` progress value. `/api/shutdown` confirmed shutdown request.

## Packaging Review

Not executed in this session — task is purely a route refactor with no packaging changes.

## Deferred Lifecycle

Explicitly confirmed not extracted:
- `_stop_background_tasks` remains in `server.py`
- `_request_app_shutdown` remains in `server.py`
- `_on_startup` remains in `server.py`
- `_on_shutdown` remains in `server.py`
- `main` remains in `server.py`
- tray/browser launch remains in `server.py`

## Forbidden Changes Review

- No lifecycle extraction beyond preconvert cancellation — deferred
- Search/file/tree/annotation/AI/system/static routes unchanged
- Frontend unchanged
- `src.ai` provider/task files unchanged
- Backend services unchanged
- `src/backend/app_context.py` unchanged
- No new endpoints, no new features, no re-enabled startup preconvert

## Known Issues

None.

## Decision

PASS
