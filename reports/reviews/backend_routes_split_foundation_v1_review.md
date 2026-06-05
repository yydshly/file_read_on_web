# Review: BACKEND-ROUTES-SPLIT-FOUNDATION-V1

## Summary

Successfully split foundation runtime and cache routes into dedicated route modules. The route split pattern is proven safe with all validations passing.

## Changed Files

- `server.py` - Updated to import and include new route routers; removed old route handlers
- `src/backend/routes/__init__.py` - New package init
- `src/backend/routes/runtime_routes.py` - New runtime routes module
- `src/backend/routes/cache_routes.py` - New cache routes module

## Route Modules Added

- `src/backend/routes/__init__.py` - Package marker
- `src/backend/routes/runtime_routes.py` - Contains `create_runtime_router()` factory
- `src/backend/routes/cache_routes.py` - Contains `create_cache_router()` factory with `_dir_stats()` helper

## Runtime Routes Split

- `/api/health` - Moved to `runtime_routes.py`
- `/api/version` - Moved to `runtime_routes.py`

## Cache Routes Split

- `/api/cache/clear` - Moved to `cache_routes.py`
- `/api/cache/stats` - Moved to `cache_routes.py`
- `/api/cache/cleanup` - Moved to `cache_routes.py`
- `_dir_stats()` helper - Moved to `cache_routes.py` as private helper

## Server Integration

- Added imports for `create_runtime_router` and `create_cache_router` from new route modules
- Included both routers after `ctx` exists and after `_has_root()` is defined
- Removed old route handlers: `api_health`, `api_version`, `api_cache_clear`, `api_cache_stats`, `api_cache_cleanup`, `_dir_stats`

## Route Registration Review

- All required routes present and registered exactly once
- No duplicate path registrations for moved routes
- All other routes (tree, file, search, AI, annotation, root, shutdown) remain in server.py

## API Compatibility Review

- Response schemas preserved exactly as before
- Endpoint paths unchanged
- HTTP method types unchanged

## Dev Smoke

- All runtime/cache endpoints verified working via smoke test
- `/api/health` returns correct structure with `ok`, `app_id`, `app_name`, `version`, `soffice`, `needs_root`
- `/api/version` returns correct structure with `ok`, `release_baseline`, `frozen`
- `/api/cache/stats` returns all cache categories
- `/api/cache/cleanup` runs successfully
- `/api/cache/clear` runs successfully
- Server shutdown via `/api/shutdown` works correctly

## Packaging Review

- `scripts/build_windows.ps1` executed successfully
- Build completed without errors
- All validation checks passed (static bundled, exe exists, _internal exists, app_data exists, config.example copied)

## Deferred Routes

- file/tree/search routes remain in server.py
- AI routes remain in server.py
- annotation routes remain in server.py
- root/shutdown/pick-folder/reveal remain in server.py

## Forbidden Changes Review

- AI routes unchanged: PASS
- file/search/tree routes unchanged: PASS
- annotation routes unchanged: PASS
- frontend unchanged: PASS
- backend services unchanged: PASS
- packaging/spec files unchanged: PASS
- generated artifacts not committed: PASS

## Known Issues

- None

## Decision

PASS
