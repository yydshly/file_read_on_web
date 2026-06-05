# Release Baseline Freeze V1

## Summary

This document freezes the current project state as the stable v0.1.0 baseline after the full modularization, release validation, packaging-script fix, README architecture sync, and prefreeze stability/contract hotfix.

## Baseline

```
baseline_name:     Release Baseline Freeze V1
app_version:       0.1.0
product_name:      资料浏览器
target_platform:   Windows
runtime_shape:     本地后台服务 + 浏览器 UI + 系统托盘
branch:            main
source_baseline_commit: 4c20dee5906620151d60f14f95e0e53d74732768
source_baseline_message: Fix prefreeze stability and AI contract issues
freeze_commit:     <recorded after this document is committed>
date:             2026-06-05
```

## What Is Frozen

- **Modular backend architecture** — `server.py` is entrypoint/wiring/lifecycle only; all business API routes are in `src/backend/routes/`
- **Route modules:** `runtime_routes.py`, `cache_routes.py`, `annotation_routes.py`, `ai_routes.py`, `system_routes.py`, `static_routes.py`, `file_tree_routes.py`, `search_routes.py`, `preconvert_routes.py`
- **Service modules:** `converter.py`, `search.py`, `annotations.py`, `ai_document.py`, `runtime_state.py`, `tts_cache.py`
- **Infra modules:** `logging_setup.py`, `safeio.py`, `tray_controller.py`
- **Domain metadata:** `app_metadata.py` — APP_ID / APP_NAME / APP_VERSION / RELEASE_BASELINE
- **AI layer:** `src/ai/` — providers, tasks, model adapters
- **Frontend:** `src/frontend/static/` — browser UI static assets
- **Packaging:** `scripts/build_windows.ps1`, `scripts/package_release_zip.ps1`, `scripts/_package_zip.py`, `packaging/`
- **Prefreeze stability/contract fixes:**
  - `atomic_write_json` uses unique temp files (PID + thread ID + UUID) to avoid collision risk
  - Long-document AI eligibility wording no longer promises unimplemented "摘要 + 检索片段" behavior
  - Minimax Vision capability is disabled by default, gated by `enable_vision=true` config flag

## Completed Validation

| Validation | Result |
|------------|--------|
| `python -m compileall .` | PASS |
| Route registration smoke | PASS |
| Dev runtime smoke (all core APIs) | PASS |
| Windows build (`scripts/build_windows.ps1`) | PASS |
| Release zip generation (`scripts/package_release_zip.ps1`) | PASS |
| Packaged runtime smoke | PASS |
| Zip safety (no user data in zip) | PASS |
| README architecture sync | PASS |
| Prefreeze hotfix validation | PASS |
| Server unused import cleanup | PASS |

## Release Artifact

Latest generated release zip format:

```
release_packages/资料浏览器-v0.1.0-windows-YYYYMMDD.zip
```

Do not commit the zip to Git.

## Current Architecture

```
server.py
  entrypoint / path initialization / AppContext wiring / route registration / lifecycle

src/backend/routes/
  runtime_routes.py       健康检查与版本信息
  cache_routes.py         缓存统计、清理
  annotation_routes.py    收藏、标签、笔记
  ai_routes.py            AI 状态、文档整理、对话、TTS
  system_routes.py        根目录切换、打开位置、选择目录、退出
  static_routes.py        首页、favicon、静态资源挂载
  file_tree_routes.py     文件树、文件预览、原文件读取
  search_routes.py        全文搜索、索引状态、重建
  preconvert_routes.py    Office 预转换状态

src/backend/services/
  converter.py            文件类型识别、Markdown/Text 渲染、Office 转 PDF
  search.py               全文搜索、文本抽取、索引缓存
  annotations.py           收藏、标签、笔记数据
  ai_document.py          AI 文档加载、可用性判断
  runtime_state.py        最近根目录、最近文件等运行状态
  tts_cache.py            TTS 音频缓存

src/backend/infra/
  logging_setup.py        日志初始化
  safeio.py               安全 JSON 读写（含 unique temp file fix）
  tray_controller.py       Windows 系统托盘

src/backend/domain/
  app_metadata.py         APP_ID / APP_NAME / APP_VERSION / RELEASE_BASELINE

src/ai/
  providers / tasks / model adapters

src/frontend/static/
  浏览器 UI 静态资源

scripts/
  build_windows.ps1       构建 Windows 打包目录
  package_release_zip.ps1 生成发布 zip
  _package_zip.py         zip 打包与安全校验

packaging/
  PyInstaller spec 参考配置

reports/reviews/
  变更审查、冒烟测试、发布验证记录
```

## Known Deferred Items

These are intentionally not part of the frozen baseline:

- Prompt caching
- `docs/INDEX.md`
- `/api/tree recursive=1` optimization
- Packaged GUI/tray manual verification
- Logging initialization fallback
- Cache stats OSError hardening
- Windows `os.replace` retry hardening for rare target-file lock cases
- Large directory lazy loading
- Real summarize-first chat / RAG
- Cross-document RAG
- PDF.js viewer
- Vision/OCR

## Development Rule After Freeze

Future changes should not add business route logic back into `server.py`.

Recommended boundaries:

| Type | Location |
|------|----------|
| API route logic | `src/backend/routes/` |
| Reusable business services | `src/backend/services/` |
| Infrastructure helpers | `src/backend/infra/` |
| App metadata | `src/backend/domain/app_metadata.py` |
| Frontend assets | `src/frontend/static/` |

## Rollback Point

If later development introduces regressions, return to this baseline:

```
v0.1.0 tag → this freeze record commit
```

If the tag is absent, use the source baseline commit directly:

```
4c20dee5906620151d60f14f95e0e53d74732768
```

## Decision

Frozen as stable baseline.
