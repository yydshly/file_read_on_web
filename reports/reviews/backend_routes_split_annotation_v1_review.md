# Review: BACKEND-ROUTES-SPLIT-ANNOTATION-V1

## Summary

Successfully split annotation routes out of `server.py` into a dedicated route module. The annotation route module is properly integrated and AI annotation helpers remain intact.

## Changed Files

- `server.py` - Updated to import and include annotation router; removed old annotation route handlers; renamed `_anno_patch_async` to `_ai_anno_patch_async` for AI route usage
- `src/backend/routes/annotation_routes.py` - New annotation routes module

## Annotation Routes Split

- `GET /api/anno/all` - Moved to `annotation_routes.py`
- `GET /api/anno` - Moved to `annotation_routes.py`
- `PATCH /api/anno` - Moved to `annotation_routes.py`
- `PUT /api/anno/palette` - Moved to `annotation_routes.py`
- `_anno_patch_async` helper - Moved to `annotation_routes.py` as private helper
- `TagPaletteBody` - Moved to `annotation_routes.py`

## Server Integration

- Added import for `create_annotation_router` from annotation routes module
- Included annotation router after `ctx`, `_has_root`, `_require_root`, and `_safe_resolve` are defined
- Removed old annotation route handlers from `server.py`
- Renamed `_anno_patch_async` to `_ai_anno_patch_async` in `server.py` to preserve AI route functionality

## Annotation Write Offload Review

- `PATCH /api/anno` properly uses `run_in_executor` offload for annotation writes
- `_anno_patch_async` helper exists in annotation_routes.py with proper async offload pattern

## AI Annotation Helper Safety

- `_anno_patch_async` renamed to `_ai_anno_patch_async` in server.py for AI route usage
- AI routes (`/api/ai/summarize`, `/api/ai/chat`) continue to use `_ai_anno_patch_async`
- No circular imports or broken references

## Route Registration Review

- All annotation routes present and registered exactly once (no duplicates by path+method)
- All required routes present: health, version, cache, tree, file, search, AI, root, shutdown

## API Compatibility Review

- Response schemas preserved exactly as before
- Endpoint paths unchanged
- HTTP method types unchanged
- Error messages preserved: "invalid JSON body", "body must be a JSON object"

## Dev Smoke

- Server starts successfully
- Annotation routes work correctly with root set
- GET `/api/anno` returns empty dict for new file
- PATCH `/api/anno` creates annotation with proper fields
- PUT `/api/anno/palette` sets tag palette correctly
- GET `/api/anno/all` returns all files and tag_palette

## Packaging Review

- `scripts/build_windows.ps1` executed successfully
- Build completed without errors
- All validation checks passed (static bundled, exe exists, _internal exists, app_data exists, config.example copied)

## Deferred Routes

- file/tree/search routes remain in server.py
- AI routes remain in server.py
- root/shutdown/pick-folder/reveal remain in server.py

## Forbidden Changes Review

- AI routes unchanged: PASS (AI routes still use `_ai_anno_patch_async`)
- file/search/tree routes unchanged: PASS
- root/shutdown routes unchanged: PASS
- frontend unchanged: PASS
- backend services unchanged: PASS
- packaging/spec files unchanged: PASS
- generated artifacts not committed: PASS

## Known Issues

- None

## Decision

PASS
