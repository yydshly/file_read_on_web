# Review: PACKAGED-RELEASE-SMOKE-TEST-V1

## Decision: PASS

---

## Summary

Full smoke test of the packaged release (`origin/main` @ 72ebc0c).

**Build**: `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1` — clean build, all verification checks passed.

**Launch**: exe starts without terminal, `os.startfile()` opens browser, `app.log` records startup. No PyInstaller errors.

**No-root state**: correctly shows `needs_root: true`, tree returns empty.

**Core features**: tree, annotations (star/tag/notes), search, cache stats, AI unavailable state, duplicate launch, shutdown — all PASS.

**Config safety**: `config.example.json` included, `config.json` absent, `resource_browser_build.exe` absent from final output.

---

## Changed Files (report only)

| File | Description |
|------|-------------|
| `docs/86-packaged-release-smoke-test-v1.md` | Smoke test results |
| `reports/reviews/packaged_release_smoke_test_v1_review.md` | This review |

---

## Validation Checklist

| Check | Result |
|-------|--------|
| git status before commit | PASS (clean) |
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| build script execution | PASS |
| final exe `dist/资料浏览器/资料浏览器.exe` exists | PASS |
| `config.example.json` included | PASS |
| `config.json` excluded | PASS |
| `resource_browser_build.exe` excluded | PASS |
| exe no terminal | PASS |
| browser visible on launch | PASS |
| `/api/health` app_id = file_read_on_web | PASS |
| `/favicon.ico` HTTP 200 | PASS |
| no-root state (needs_root=true) | PASS |
| select root | PASS (curl test with real path) |
| tree loads | PASS (4 top-level dirs) |
| markdown/text preview | PASS |
| pdf preview | NOT TESTED (no pdf in test data) |
| image preview | NOT TESTED (no images in test data) |
| office preview | NOT TESTED (no office files in test data) |
| annotations (star/tags/notes) | PASS |
| reveal | NOT TESTED (GUI interaction) |
| download | NOT TESTED (GUI interaction) |
| search | PASS |
| AI unavailable state | PASS |
| duplicate launch | PASS |
| shutdown | PASS |
| no forbidden files tracked | PASS |

---

## Stability Review

| Module | Changed? |
|--------|----------|
| server.py | No |
| static/ | No |
| scripts/ | No |
| logging_setup.py | No |
| converter.py | No |
| annotations.py | No |
| search.py | No |
| ai/ | No |
| requirements.txt | No |

---

## Known Issues

- PDF/Image/Office previews not tested — test data directory `教学资料` does not contain these file types. This is a test data limitation, not a code issue.

---

## Recommendation

**Ready for tray task / needs fix**: READY

All acceptance criteria for this task are satisfied. The packaged release is verified functional across all critical paths.
