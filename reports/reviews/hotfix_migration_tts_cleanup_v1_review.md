# Review: HOTFIX-MIGRATION-TTS-CLEANUP-V1

## Summary

Three small, narrow correctness fixes:

- **Fix A** — `init_logging(DATA_DIR)` now runs **before** `_migrate_legacy_state()`
  in `main()`. Migration log messages reliably reach `app.log`, including in
  PyInstaller `--noconsole` builds where stderr may be unavailable.
- **Fix B** — `_migrate_legacy_state()` is now **state-only**. It imports
  legacy `last_root` / `last_files` from `config.json` into `state.json` and
  force-flushes the result to disk, but **no longer mutates or rewrites
  `config.json`** under any circumstance. The strict
  `config.json = user-editable / state.json = auto-managed` contract is now
  preserved.
- **Fix C** — `/api/ai/tts` normalises the effective text once via the new
  module-level constant `_TTS_TEXT_LIMIT_CHARS = 5000`. Cache lookup,
  provider call, and cache write all operate on the same `tts_text`, so
  inputs that differ only beyond the cap collapse to a single cache entry.

No new product features, no module splits, no packaging changes, no path
constants changed.

## Changed Files

- `server.py`
- `reports/reviews/hotfix_migration_tts_cleanup_v1_review.md` (this file)

## Fix A: Logging Before Migration

Previously in `main()`:

```python
DATA_DIR.mkdir(...)
_migrate_legacy_state()        # logger handlers not configured yet
log_dir = init_logging(DATA_DIR)
```

Now:

```python
DATA_DIR.mkdir(...)
log_dir = init_logging(DATA_DIR)
log = get_logger("browse")
_migrate_legacy_state()        # any logger.info/warning lands in app.log
```

This required no change to `logging_setup.py` or the migration body itself —
only the call order in `main()`.

## Fix B: State-Only Legacy Migration

Previous behaviour:

1. `cfg = _load_config()` then `cfg.pop("last_root")` / `cfg.pop("last_files")`
2. `_save_state(moved)` — debounced (500 ms) in-memory write
3. `atomic_write_json(CONFIG_PATH, cfg)` — synchronous rewrite of `config.json`
4. Optional `_doc` placeholder injected into `cfg`

Two problems with that flow:

- A 500 ms race window between the synchronous `config.json` rewrite and the
  debounced `state.json` flush. A crash inside that window left
  `config.json` legacy-free but `state.json` missing → user’s last root
  permanently lost.
- The server-side rewrite of `config.json` violated the contract that
  config.json is user-editable and must not be auto-mutated.

New behaviour:

```python
if STATE_PATH.exists():
    return
cfg = _load_config()
if not isinstance(cfg, dict):
    return

moved: dict = {}
if "last_root" in cfg:
    moved["last_root"] = cfg["last_root"]
if "last_files" in cfg:
    moved["last_files"] = cfg["last_files"]
if not moved:
    return

_save_state(moved)
_flush_state(force=True)        # durable before we report success

log = get_logger("browse")
if STATE_PATH.exists():
    log.info("迁移：legacy last_root / last_files 已导入 state.json；"
             "config.json 中旧字段将被忽略")
else:
    log.warning("迁移：state.json 落盘失败，config.json 保持不变以便下次启动重试")
```

Key invariants:

- `cfg.pop(...)` is gone; legacy keys are only **read** from cfg.
- `atomic_write_json(CONFIG_PATH, ...)` is gone from this function.
- The optional `_doc` hint injection is gone.
- If flush fails, `config.json` is untouched → migration will retry on the
  next startup.
- Function is still idempotent: second run sees `STATE_PATH.exists()` and
  returns immediately.

## Fix C: TTS Cache Normalisation

New module-level constant alongside the TTS cache helpers:

```python
_TTS_TEXT_LIMIT_CHARS = 5000
```

This is the single source of truth for the effective TTS text length on the
server side. It matches the in-provider truncation in `ai/minimax.py` and
`ai/mimo.py`. The provider modules are intentionally **not modified** in
this task.

`api_ai_tts` now normalises once:

```python
raw_text = body.text
if not raw_text.strip():
    raise HTTPException(400, "text 不能为空")
tts_text = raw_text[:_TTS_TEXT_LIMIT_CHARS]
```

…and uses `tts_text` for all three operations:

- `_tts_cache_get(provider.name, tts_text, body.voice, body.speed)`
- `provider.tts(tts_text, voice=body.voice, speed=body.speed)`
- `_tts_cache_put(provider.name, tts_text, body.voice, body.speed, audio, mime)`

The two cache calls remain offloaded to the default executor via
`loop.run_in_executor`; the inner call is wrapped in a `lambda` so the call
site reads as the literal `_tts_cache_get(provider.name, tts_text, ...)` /
`_tts_cache_put(provider.name, tts_text, ...)` form. Behaviour is identical
to the previous positional-args form.

## Runtime Mode Review

Path model is unchanged:

- `APP_DIR` — exe directory in frozen mode, `__file__` parent in dev.
- `RESOURCE_DIR` — `sys._MEIPASS` when frozen, else `__file__` parent.
- `DATA_DIR` — writable area: `APP_DIR/app_data` portable when writable,
  else `%LOCALAPPDATA%/资料浏览器`; in dev equals `APP_DIR`.
- `CONFIG_PATH`, `STATE_PATH`, `CACHE_DIR`, `TTS_CACHE_DIR` — all derived
  from `DATA_DIR`.

None of these constants or the helpers that compute them
(`_app_base_dir`, `_resource_base_dir`, `_data_base_dir`,
`_is_writable_dir`) were touched.

`sys.frozen` / `sys._MEIPASS` references are preserved.

## Validation

| Step | Result |
|---|---|
| `git status -sb` before edit (clean main) | PASS |
| `python -m compileall .` | PASS |
| `HOTFIX_CONTENT_PASS` (source-text contract checks) | PASS |
| `MIGRATION_STATE_ONLY_PASS` (tmp-dir functional test) | PASS |
| `TTS_NORMALIZATION_PASS` (effective-text → same cache key) | PASS |
| `IMPORT_PASS` (`import server`) | PASS |
| changed-files scope | PASS (`server.py`, plus this review) |

`MIGRATION_STATE_ONLY_PASS` specifically verified:

- `state.json` is created with the migrated keys.
- `config.json` is **byte-for-byte unchanged** before and after migration.
- A second migration run is idempotent and still doesn’t touch
  `config.json`.

## Forbidden Changes Review

- `static/**`, `scripts/**`, `ai/**`, `converter.py`, `search.py`,
  `annotations.py`, `safeio.py`, `logging_setup.py`, `tray_controller.py`,
  `app_metadata.py`, `README.md`, `docs/**`, `requirements.txt`,
  `config.example.json` — **untouched**.
- `dist/**`, `build/**`, `release_packages/**`, `app_data/**`, `cache/**`,
  `logs/**`, runtime JSON files, `*.zip`, `*.exe` — **untouched**.
- Path constants and frozen-mode helpers — **untouched**.
- Packaging behaviour — **untouched**.

## Decision

**PASS**
