# Review: BACKEND-ROUTES-SPLIT-SYSTEM-V1

## Summary

Successfully split system/control routes out of `server.py` into a dedicated route module. All system routes are preserved with their helpers and behavior intact. Lifecycle implementations remain in `server.py` and are passed as callables.

## Changed Files

- `server.py` - Updated to import and include system router; removed old system route handlers and helpers
- `src/backend/routes/system_routes.py` - New system routes module

## System Routes Split

- `GET /api/root` - Moved to `system_routes.py`
- `POST /api/root` - Moved to `system_routes.py`
- `POST /api/reveal` - Moved to `system_routes.py`
- `POST /api/pick-folder` - Moved to `system_routes.py`
- `POST /api/shutdown` - Moved to `system_routes.py`
- `RootBody` - Moved to `system_routes.py`
- `_bring_explorer_to_front_later` helper - Moved to `system_routes.py`

## Server Integration

- Added import for `create_system_router` from system routes module
- Included system router after `_request_app_shutdown` is defined (to satisfy dependency)
- Removed all old system route handlers and helper functions from `server.py`

## Root Route Review

- `GET /api/root` behavior preserved with proper needs_root handling
- `POST /api/root` behavior preserved including the hotfix that does NOT clear search text cache on root change
- Path resolution uses `ctx.paths.app_dir` for relative paths
- Background tasks stopped on root change via `stop_background_tasks` callable

## Reveal Route Review

- `POST /api/reveal` behavior preserved for all platforms (Windows/macOS/Linux)
- Windows uses `explorer /select,"<path>"` with proper command-line escaping
- `_bring_explorer_to_front_later` helper preserves ctypes-based foreground attempt
- Response shape preserved: ok, path, parent, foreground_attempted

## Pick Folder Review

- `POST /api/pick-folder` behavior preserved
- tkinter imports inside handler
- Thread-based picker with 300s timeout
- Initial directory uses `ctx.root` if available, else `ctx.paths.app_dir`
- Returns `{"path": None}` or `{"path": selected[0]}`
- Error message "tkinter unavailable: {e}" preserved

## Shutdown Route Review

- `POST /api/shutdown` behavior preserved
- Localhost check preserved: 403 for non-local access with message "仅允许本地访问"
- Calls `request_app_shutdown` callable with proper reason format
- Returns success message "程序正在退出"

## Lifecycle Boundary Review

- `_request_app_shutdown` remains in `server.py` (passed as callable)
- `_stop_background_tasks` remains in `server.py` (passed as callable)
- Startup/shutdown event handlers remain in `server.py`
- Tray controller lifecycle remains in `server.py`
- `main()` function remains in `server.py`

## Route Registration Review

- All system routes present and registered exactly once per path+method
- GET and POST for `/api/root` are correctly registered as separate methods
- All required routes present in server

## API Compatibility Review

- Response schemas preserved exactly as before
- Endpoint paths unchanged
- HTTP method types unchanged
- Error messages preserved: "仅允许本地访问", "tkinter unavailable: {e}", "not a directory: ..."

## Dev Smoke

- Server starts successfully
- `GET /api/root` returns proper structure with root, last_file, needs_root
- `POST /api/root` updates root and returns correct response
- `GET /api/root` after set returns the new root
- `POST /api/reveal` returns proper response with foreground_attempted
- Server shutdown via `/api/shutdown` works correctly

## Pick Folder Smoke

- SKIPPED - requires manual GUI interaction (tkinter dialog)

## Packaging Review

- `scripts/build_windows.ps1` executed successfully
- Build completed without errors
- All validation checks passed (static bundled, exe exists, _internal exists, app_data exists, config.example copied)

## Deferred Routes

- file/tree/search routes remain in server.py
- static/index/favicon remain in server.py
- lifecycle/background task logic remains in server.py

## Forbidden Changes Review

- file/search/tree routes unchanged: PASS
- static routes unchanged: PASS
- lifecycle functions unchanged: PASS
- frontend unchanged: PASS
- src.ai provider/task files unchanged: PASS
- backend services unchanged: PASS
- packaging/spec files unchanged: PASS
- generated artifacts not committed: PASS

## Known Issues

- None

## Decision

PASS
