# Review: BACKEND-ROUTES-SPLIT-AI-V1

## Summary

Successfully split AI-related routes out of `server.py` into a dedicated route module. All AI routes are preserved with their helpers, models, and behavior intact.

## Changed Files

- `server.py` - Updated to import and include AI router; removed old AI route handlers and related helpers
- `src/backend/routes/ai_routes.py` - New AI routes module

## AI Routes Split

- `GET /api/file/ai-eligibility` - Moved to `ai_routes.py`
- `GET /api/ai/status` - Moved to `ai_routes.py`
- `POST /api/ai/summarize` - Moved to `ai_routes.py`
- `POST /api/ai/chat` - Moved to `ai_routes.py`
- `POST /api/ai/tts` - Moved to `ai_routes.py`
- `GET /api/ai/tts/stats` - Moved to `ai_routes.py`
- `POST /api/ai/tts/clear` - Moved to `ai_routes.py`
- `AiChatBody` - Moved to `ai_routes.py`
- `AiSummarizeBody` - Moved to `ai_routes.py`
- `AiTtsBody` - Moved to `ai_routes.py`
- `_ai_require_text` helper - Moved to `ai_routes.py` as private helper
- `_ai_require_tts` helper - Moved to `ai_routes.py` as private helper
- `_sse_stream` helper - Moved to `ai_routes.py` as private helper
- `_ai_anno_patch_async` helper - Moved to `ai_routes.py` as private helper

## Server Integration

- Added import for `create_ai_router` from AI routes module
- Included AI router after `ctx`, `_require_root`, and `_safe_resolve` are defined
- Removed all old AI route handlers and helper functions from `server.py`

## AI Status Review

- `/api/ai/status` calls `build_ai_status(ctx.ai_text_provider, ctx.ai_tts_provider)` exactly as before
- Response structure preserved

## AI Eligibility Review

- `/api/file/ai-eligibility` calls `ctx.ai_doc_service.eligibility(src, path)` exactly as before
- Supports async behavior preserved

## AI Summarize/Chat Review

- Stream and non-stream behavior preserved
- Cached summary behavior preserved
- Force behavior preserved
- Stage messages preserved
- `ai_tasks.summarize_document` and `ai_tasks.chat_about_document` calls preserved
- History handling preserved for chat
- Annotation save via `run_in_executor` preserved

## AI TTS Review

- Text normalization preserved
- X-TTS-Cache headers preserved
- Provider TTS call preserved
- Voice/speed behavior preserved
- Error handling preserved (400, 502 status codes)
- Cache write offloaded to executor

## SSE Streaming Review

- `_sse_stream` helper moved with full functionality
- SSE format preserved
- Dict payload handling preserved
- Empty item skip preserved
- Error frame behavior preserved
- `media_type="text/event-stream"` preserved

## Annotation Save Review

- AI summary annotation save uses `_ai_anno_patch_async` with `run_in_executor`
- Cached summary check uses `ctx.anno_store.get`
- Both stream and non-stream paths save annotations correctly

## Route Registration Review

- All AI routes present and registered exactly once
- All required routes present
- No duplicate path+method registrations

## API Compatibility Review

- Response schemas preserved exactly as before
- Endpoint paths unchanged
- HTTP method types unchanged
- Error messages preserved: "AI 未启用：请在 config.json.ai 中配置 active provider", "AI TTS 未启用：请配置 ai.tts_provider 或让 active provider 支持 TTS"

## Dev Smoke

- Server starts successfully with AI providers configured
- `/api/ai/status` returns proper status with masked credentials
- `/api/file/ai-eligibility` returns eligibility for sample file
- `/api/ai/tts/stats` returns stats
- `/api/ai/tts/clear` clears TTS cache
- Server shutdown via `/api/shutdown` works correctly

## Streaming Smoke

- SKIPPED (would require actual AI provider calls; status and lightweight endpoints verified)

## Packaging Review

- `scripts/build_windows.ps1` executed successfully
- Build completed without errors
- All validation checks passed (static bundled, exe exists, _internal exists, app_data exists, config.example copied)

## Deferred Routes

- file/tree/search routes remain in server.py
- root/shutdown/pick-folder/reveal remain in server.py
- static/index/favicon remain in server.py
- lifecycle/background task logic remains in server.py

## Forbidden Changes Review

- file/search/tree routes unchanged: PASS
- root/shutdown routes unchanged: PASS
- annotation routes unchanged: PASS
- frontend unchanged: PASS
- src.ai provider/task files unchanged: PASS
- backend services unchanged: PASS
- packaging/spec files unchanged: PASS
- generated artifacts not committed: PASS

## Known Issues

- None

## Decision

PASS
