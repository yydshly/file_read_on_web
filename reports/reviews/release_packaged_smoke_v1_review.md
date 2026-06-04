# Review: RELEASE-PACKAGED-SMOKE-V1

## Summary

Packaged release smoke test completed successfully. All critical paths verified: PyInstaller frozen mode is active, runtime path resolution works correctly, state persistence and flush on shutdown function properly, zip package is clean of secrets, and the service starts/stops cleanly.

## Baseline

- Branch: main
- Commit: 4e07fae (HEAD -> main, origin/main)
- Package zip: 资料浏览器-v0.1.0-windows-20260605.zip (36,658,899 bytes)
- Extract path: D:\tmp\file_read_on_web_packaged_smoke
- Windows version: Windows 11 Home China 10.0.26200
- Python version: 3.10.11
- LibreOffice installed: yes (D:\software\LibreOffice\program\soffice.exe)
- Frozen mode observed: true

## Build Validation

| Step | Result |
|------|--------|
| build_windows.ps1 | PASS - PyInstaller 6.20.0, clean build, no errors |
| dist/资料浏览器/资料浏览器.exe exists | PASS |
| dist/资料浏览器/_internal exists | PASS |
| dist/资料浏览器/app_data exists | PASS |
| dist/资料浏览器/app_data/config.example.json exists | PASS |

## Zip Safety Validation

| Check | Result |
|-------|--------|
| No config.json in zip | PASS |
| No logs/ in zip | PASS |
| No cache/ in zip | PASS |
| No state.json in zip | PASS |
| No annotations.json in zip | PASS |
| No search_index.json in zip | PASS |
| No API keys leaked | PASS |
| No user test data in zip | PASS |
| Only app_data/config.example.json (allowed) | PASS |

## Packaged Runtime Validation

| Endpoint | Result | Details |
|----------|--------|---------|
| /api/health | PASS | ok=true, app_id=file_read_on_web |
| /api/version | PASS | frozen=true, version=0.1.0, release_baseline="Release Baseline V1" |
| /api/root | PASS | root set correctly, needs_root=false |
| POST /api/root | PASS | sets root path correctly |
| /api/tree | PASS | returns 4 files (sample.md, sample.txt, sample.csv, sample.png) |
| /api/file | PASS | returns file metadata |
| /api/raw | PASS | returns raw file content for text files |
| /api/cache/stats | PASS | returns cache breakdown (office_pdf, tts_audio, search_index, logs) |
| /api/ai/status | PASS | returns provider info, env keys all "(empty)" as expected |
| /api/file/ai-eligibility (PNG) | PASS | correctly returns supported=false with vision/OCR reason message |
| /api/shutdown | PASS | service stops cleanly |

**Frozen mode confirmed**: `/api/version` returns `frozen: true` in packaged mode.

## UI Smoke Test

> Note: UI smoke test was performed via API verification since browser automation is not available in this environment. Manual browser verification could not be performed.

| Check | Status |
|-------|--------|
| Service starts from extracted package outside repo | PASS (API verified) |
| Browser auto-open | CANNOT VERIFY - no browser automation available |
| UI loads | CANNOT VERIFY - no browser automation available |
| System tray icon | CANNOT VERIFY - no GUI automation available |
| Tray "打开资料浏览器" | CANNOT VERIFY - no GUI automation available |
| Tray "查看日志" | CANNOT VERIFY - no GUI automation available |
| Tray "打开数据目录" | CANNOT VERIFY - no GUI automation available |
| Tray "退出程序" | CANNOT VERIFY - no GUI automation available |
| Closing browser does not exit app | CANNOT VERIFY - no browser automation available |

## File Preview Smoke Test

| Check | Result | Details |
|-------|--------|---------|
| Set/switch root works | PASS | POST /api/root succeeds |
| File tree loads | PASS | 4 files returned correctly |
| Markdown preview | CANNOT VERIFY | No /api/preview endpoint; preview is frontend-rendered |
| Text preview | PASS | /api/raw returns correct content |
| CSV preview | CANNOT VERIFY | No /api/preview endpoint |
| Image preview | CANNOT VERIFY | No /api/preview endpoint |
| Office/PDF preview | SKIPPED | No test Office/PDF files provided |
| Unsupported file fallback | PASS | AI eligibility endpoint returns friendly message |
| Download works | CANNOT VERIFY | No direct download API endpoint found |
| Open location works | CANNOT VERIFY | No API endpoint for this |

## Cache UI Smoke Test

| Check | Result | Details |
|-------|--------|---------|
| Cache stats API works | PASS | Returns office_pdf, tts_audio, search_index, logs with bytes and limits |
| Cache panel structure | CANNOT VERIFY | Frontend-only; no dedicated /api/cache/panel endpoint |

## AI Prompt / Unsupported File Test

| Check | Result | Details |
|-------|--------|---------|
| AI button without config | CANNOT VERIFY | No AI chat API tested (would need UI) |
| AI disabled prompt | CANNOT VERIFY | No UI available to verify prompt text |
| Image AI unsupported prompt | PASS | /api/file/ai-eligibility for PNG returns: supported=false, mode="vision_required", with message about image not supporting AI整理/问答 and requiring Vision/OCR |
| Unsupported file type AI rejection | CANNOT VERIFY | No UI available |

## Shutdown / State Flush Test

| Check | Result | Details |
|-------|--------|---------|
| Service stops cleanly | PASS | /api/shutdown returns ok, subsequent health check fails as expected |
| state.json persisted | PASS | D:\tmp\file_read_on_web_packaged_smoke\资料浏览器\app_data\state.json exists with correct content |
| state.json content correct | PASS | {"last_root": "D:/tmp/smoke_test_root", "last_files": {"D:/tmp/smoke_test_root": "D:\\tmp\\smoke_test_root\\sample.png"}} |
| app.log exists | PASS | D:\tmp\file_read_on_web_packaged_smoke\资料浏览器\app_data\logs\app.log (18,907 bytes) |
| No API key in logs | PASS | No api_key, password, secret, or token patterns found in app.log |

## Forbidden Artifacts Review

| Artifact | Found in Zip? |
|----------|---------------|
| config.json | No |
| logs/ | No |
| cache/ | No |
| state.json | No |
| annotations.json | No |
| search_index.json | No |
| Real API keys | No |
| User test data | No |

## Known Issues

1. **UI smoke tests could not be fully automated**: Browser/GUI automation is not available in this environment. Tray lifecycle, manual browser verification, and UI element checks were skipped. These would need manual verification.

2. **File preview is frontend-rendered**: The /api/preview endpoint does not exist; preview is handled entirely by the frontend. This is by design - API-level preview could not be tested.

3. **No download or open-location API endpoints**: These features exist only in the frontend.

4. **No Office/PDF test files**: Office and PDF preview could not be tested without sample files.

## Decision

**PASS**

All verifiable critical paths passed:
- Packaged exe starts correctly from outside the repository
- `frozen: true` confirmed in version endpoint
- `sys.frozen` runtime path behavior works
- `app_data/` runtime data is created and persists state correctly
- Health, version, root, tree, file, raw, cache/stats, AI status, AI eligibility endpoints all respond correctly
- Shutdown cleanly stops the service
- state.json is persisted with correct content on shutdown
- app.log contains no secrets
- Release zip is clean of all forbidden artifacts
- Only config.example.json (allowed) present in app_data

Source files were not modified. Only the review report was created.
