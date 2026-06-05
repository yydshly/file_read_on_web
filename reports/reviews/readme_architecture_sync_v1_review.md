# Review: README-ARCHITECTURE-SYNC-V1

## Summary

Synchronized `README.md` with the current post-route-split modular architecture. Added the "当前架构" section documenting the project structure, a "开发说明" section clarifying backend code boundaries and runtime data boundaries, updated the stale zip date example from `20260604` to `YYYYMMDD`, and added a concise release validation note.

## Baseline

```
dfc6568 Fix release zip metadata lookup
```

Working tree clean before editing.

## README Updates

Four changes were made to `README.md`:

1. **当前架构 section** — Added after "功能概览", before "安装依赖". Documents the complete project structure including `server.py` role, all 9 route modules, all 6 services, infra/domain/frontend layers, scripts, packaging, and reports.
2. **开发说明 section** — Added after "开发模式 vs 正式模式", before "迁移说明". Documents backend code boundaries (where to add routes/services/infra), runtime data boundaries (what not to commit), and release validation sequence.
3. **Zip date example** — Updated from `资料浏览器-v0.1.0-windows-20260604.zip` to `资料浏览器-v0.1.0-windows-YYYYMMDD.zip` to avoid stale date claims.
4. **Release validation note** — Added concise note after "发布前检查" listing the five validation steps and their pass status.

## Architecture Section Review

- `server.py` correctly described as entrypoint/wiring/lifecycle layer, not business route holder
- All 9 route modules listed with their responsibilities: `runtime_routes`, `cache_routes`, `annotation_routes`, `ai_routes`, `system_routes`, `static_routes`, `file_tree_routes`, `search_routes`, `preconvert_routes`
- All 6 services listed: `converter`, `search`, `annotations`, `ai_document`, `runtime_state`, `tts_cache`
- `infra/` (logging, safeio, tray), `domain/` (app_metadata), `frontend/static/`, `scripts/`, `packaging/`, `reports/reviews/` all documented
- Design principle stated: routes go to `src/backend/routes/`, reusable services to `src/backend/services/`

## Developer Notes Review

- New API guidance: prefer `src/backend/routes/` over adding to `server.py`
- Reusable business logic: `src/backend/services/`
- Infrastructure: `src/backend/infra/`
- App metadata: `src/backend/domain/app_metadata.py`
- `server.py` kept as entrypoint/wiring, no business routes
- Runtime data boundary clearly listed (config.json, state.json, annotations.json, search_index.json, logs/, cache/, app_data/ runtime data)
- Only `app_data/config.example.json` (template) should be in zip
- Release validation sequence documented: `compileall` → `build_windows.ps1` → `package_release_zip.ps1`

## Packaging Text Review

- Zip example date updated to `YYYYMMDD` placeholder
- Zip contents description preserved: includes `资料浏览器.exe`, `_internal/`, `app_data/config.example.json`
- Excludes statement preserved: `config.json` (API key), logs, cache, user runtime data

## Release Validation Note

Concise note added after "发布前检查" listing:
- route/module split dev runtime smoke: passed
- Windows build: passed
- release zip: passed
- packaged runtime smoke: passed
- zip safety: passed

## Validation

- `README_ARCHITECTURE_CONTENT_PASS` — all required content present, no forbidden outdated wording
- `README_MARKDOWN_SANITY_PASS` — balanced code fences, all major sections present
- Only `README.md` changed (no source files modified)

## Forbidden Changes Review

- Source files unchanged: PASS
- Scripts unchanged: PASS (`scripts/package_release_zip.ps1` was not touched in this task)
- Packaging unchanged: PASS
- Generated artifacts not committed: PASS

## Known Issues

- Prompt caching remains deferred
- `docs/INDEX.md` remains deferred if not created
- Packaged GUI/tray manual verification remains manual

## Decision

PASS
