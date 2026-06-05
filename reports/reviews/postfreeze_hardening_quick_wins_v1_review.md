# Review: POSTFREEZE-HARDENING-QUICK-WINS-V1

## Summary

Post-freeze hardening pass applying 5 targeted quick-win fixes after v0.1.0 baseline freeze. No tag moved, no APP_VERSION changed.

## Baseline

- Tag: `v0.1.0` at commit `897320f`
- Branch: `main`
- Remote: `origin` (https://github.com/yydshly/file_read_on_web.git)

## Changed Files

- `src/backend/infra/safeio.py` — os.replace retry helper
- `src/backend/infra/logging_setup.py` — logging init fallback
- `src/backend/routes/cache_routes.py` — OSError-tolerant _dir_stats and _file_stats
- `src/backend/services/tts_cache.py` — OSError-tolerant stats
- `src/backend/services/converter.py` — OSError-tolerant cache_stats
- `config.example.json` — enable_vision=false added to minimax provider
- `docs/INDEX.md` — new project documentation navigation index

## SafeIO Replace Retry

Added `_replace_with_retry(src, dst)` wrapping `os.replace` with retry delays `(0.02, 0.05, 0.1, 0.2, 0.4)s` and transient error detection for `PermissionError` and Windows error codes `{5, 32, 33}`. Original unique temp filename pattern preserved. Behavior validated with simulated flaky replace.

## Logging Fallback

`init_logging` now catches `OSError` during log directory/file creation and falls back to `StreamHandler(sys.stderr)` or `NullHandler` if stderr is unavailable. Returns log_dir path normally. Warning logged to "browse" logger when file logging is unavailable.

## Cache Stats Hardening

All `cache_stats` / `stats` / `_dir_stats` functions now iterate tolerantly — catching `OSError` around `is_file()` and `stat()` calls and continuing, rather than failing the entire stat request if a file disappears mid-enumeration.

## Config Example Update

Added `"enable_vision": false` to the `minimax` provider config. Meaning: Vision is disabled by default; set `enable_vision=true` only after the product flow actually wires Vision/OCR.

## Docs Index

Created `docs/INDEX.md` providing navigation to: release/baseline docs, architecture section, reviews directory, development rules, and deferred items list.

## Route/API Compatibility

All required routes (`/api/health`, `/api/version`, `/api/root`, `/api/tree`, `/api/file`, `/api/search`, `/api/ai/status`, `/api/preconvert/status`, `/api/cache/stats`) remain registered. No route behavior changed.

## Dev Smoke

Import validation, safeio content/behavior, logging fallback, cache stats content, config example, docs index, and route sanity all passed.

## Package Smoke

SKIPPED — packaging not modified in this hardening pass.

## Forbidden Changes Review

- `server.py` — unchanged
- `src/backend/routes/*` — only `cache_routes.py` modified
- `src/backend/services/*` — only `tts_cache.py` and `converter.py` modified
- `src/backend/app_context.py` — unchanged
- `src/backend/domain/app_metadata.py` — unchanged
- `src/ai/**` — unchanged
- `src/frontend/**` — unchanged
- `scripts/**` — unchanged
- `packaging/**` — unchanged
- `README.md` — unchanged
- `docs/95-release-baseline-freeze-v1.md` — unchanged

## Known Deferred Items

- Prompt caching
- `/api/tree recursive=1` optimization
- Large directory lazy loading
- Real summarize-first / RAG
- Cross-document RAG
- PDF.js viewer
- Vision/OCR

## Decision

PASS

All 5 fixes implemented, all validations pass, no forbidden files modified, no tag moved, no APP_VERSION changed.
