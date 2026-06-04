# Review: BACKEND-SERVICE-EXTRACT-SMOKE-V1

## Summary

All validations passed. The extracted `RuntimeStateStore` and `TtsCache` modules work correctly in dev runtime, with all API endpoints responding as expected and state flush behavior preserved.

## Baseline
- Branch: main
- Commit: 6b74d6b (HEAD -> main, origin/main)
- Remote: origin (https://github.com/yydshly/file_read_on_web.git)

## Prior Blocker
Port 8770 was previously occupied by an old packaged app process from `RELEASE-PACKAGED-SMOKE-V1`. The user exited that process, and this run completed successfully on the default port 8770.

## Static Validation

| Check | Result |
|-------|--------|
| `python -m compileall .` | PASS |
| `IMPORT_AND_CONSTANTS_PASS` | PASS |
| `SERVICE_EXTRACT_CONTENT_PASS` | PASS |

## RuntimeStateStore Validation

| Check | Result |
|-------|--------|
| `RUNTIME_STATE_STORE_PASS` | PASS |
| config.json never modified during migration | PASS |
| `get_last_root()` / `set_last_root()` | PASS |
| `get_last_file()` / `set_last_file()` | PASS |
| `flush(force=True)` | PASS |

## TtsCache Validation

| Check | Result |
|-------|--------|
| `TTS_CACHE_STORE_PASS` | PASS |
| `normalize_text()` 5000-char cap | PASS |
| `put()` / `get()` cache round-trip | PASS |
| `stats()` returns correct file/byte counts | PASS |
| `cleanup()` returns removed/kept/bytes | PASS |
| `clear()` removes all entries | PASS |

## Dev Server Smoke

| Check | Result |
|-------|--------|
| Dev server started on port 8770 | PASS |
| `DEV_SERVER_API_SMOKE_PASS` | PASS |

## API Compatibility Review

| Endpoint | Result | Details |
|----------|--------|---------|
| `/api/health` | PASS | ok=true |
| `/api/version` | PASS | ok=true, frozen=false (dev mode) |
| `/api/root` GET | PASS | returns root, last_file, needs_root |
| `/api/root` POST | PASS | sets root, returns last_file |
| `/api/cache/stats` | PASS | tts_audio/office_pdf/total_bytes present, TtsCache.MAX_BYTES/MAX_AGE_DAYS used |
| `/api/ai/tts/stats` | PASS | files/bytes returned |
| `/api/ai/tts/clear` | PASS | removed count returned |
| `/api/shutdown` | PASS | service stops cleanly, state flushed |

## Runtime Mode Review

| Check | Result |
|-------|--------|
| Dev mode path behavior unchanged | PASS — APP_DIR, DATA_DIR, etc. remain in server.py |
| Packaged mode path behavior unchanged | PASS — no path logic modified |
| `state_store.flush(force=True)` called on shutdown | PASS |
| `state_store.get_last_root()` used in `_resolve_initial_root()` | PASS |
| TtsCache class attributes accessible as `TtsCache.MAX_BYTES` etc. | PASS |

## Forbidden Changes Review

| Area | Result |
|------|--------|
| server.py | Unchanged (no modifications in this task) |
| runtime_state.py | Unchanged (created in prior extraction task) |
| tts_cache.py | Unchanged (created in prior extraction task) |
| static/** | Unchanged |
| ai/** | Unchanged |
| converter.py | Unchanged |
| search.py | Unchanged |
| annotations.py | Unchanged |
| logging_setup.py | Unchanged |
| scripts/** | Unchanged |
| README/docs | Unchanged |
| Generated artifacts | Not committed |

## Known Issues
- None

## Decision
**PASS**
