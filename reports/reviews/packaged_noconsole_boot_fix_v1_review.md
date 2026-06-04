# Review: PACKAGED-NOCONSOLE-BOOT-FIX-V1

## Decision: PASS

## Summary

The task fixed three root causes:
1. **noconsole crash**: `sys.stdout`/`sys.stderr` are `None` under PyInstaller `--noconsole`; uvicorn's default formatter called `.isatty()` on `None`
2. **Naming**: internal build name `ziliao_build` → `resource_browser_build`; final output `dist/ziliao/` → `dist/资料浏览器/`
3. **UI**: button labels "切换" / "退出程序" → "切换资料目录" / "退出"

---

## Changed Files

| File | What Changed |
|------|-------------|
| `server.py` | Added `_ensure_stdio_for_noconsole()`; changed `uvicorn.run(..., log_config=None)` |
| `logging_setup.py` | Console handler now guarded by `getattr(sys, "stdout", None)` check |
| `scripts/build_windows.ps1` | Internal name `ziliao_build` → `resource_browser_build`; output `dist/ziliao/` → `dist/资料浏览器/` |
| `scripts/_build_copy.py` | New helper: copy + rename to Chinese path; Chinese name hardcoded in Python |
| `static/index.html` | Button layout restructured: title row + separate action row |
| `static/style.css` | Two CSS rules for new layout |
| `README.md` | Packaging section already correct; no ziliao references |
| `docs/84-packaged-noconsole-boot-fix-v1.md` | Task decision record |
| `reports/reviews/packaged_noconsole_boot_fix_v1_review.md` | This review |

---

## Implemented

- **noconsole stdio guard**: `_ensure_stdio_for_noconsole()` opens `/dev/null` replacements before any logging
- **uvicorn log_config=None**: uvicorn uses our `logging_setup.py` instead of its default formatter that crashes on None streams
- **logging_setup console guard**: `if stream is not None and hasattr(stream, "write")` — dev mode gets console, noconsole gets file-only
- **build output renamed to `dist/资料浏览器/`**: Python helper copies `dist/resource_browser_build/` → `dist/资料浏览器/` and renames exe
- **internal build name `resource_browser_build`**: ASCII-safe name for PyInstaller; never appears in final release
- **no `ziliao` names in current build script**: verified via grep
- **no `resource_browser_build.exe` in final release**: verified in build verification step
- **button layout updated**: `资料浏览器` + `退出` on title row; `切换资料目录` full-width below; IDs unchanged

---

## Validation

| Check | Result |
|-------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_CHECK | PASS |
| no old ziliao naming in scripts/README | PASS |
| build script execution | PASS |
| final release dir `dist/资料浏览器/` exists | PASS |
| `资料浏览器.exe` exists | PASS |
| `app_data/config.example.json` exists | PASS |
| `app_data/config.json` excluded | PASS |
| `resource_browser_build.exe` excluded from final dir | PASS |
| noconsole exe starts | PASS |
| no PyInstaller unhandled exception | PASS |
| `app.log` generated | PASS |
| `/api/health` returns `app_id: file_read_on_web` | PASS |
| `/favicon.ico` HTTP 200 | PASS |
| duplicate launch reuse | PASS (existing service reused, not a new one) |
| shutdown works | PASS |
| UI button layout | PASS |
| no forbidden files tracked | PASS |

---

## Stability Review

| Module | Changed? |
|--------|----------|
| `root` (state machine) | No |
| `preview` (converter) | No |
| Office conversion | No |
| AI providers | No |
| `annotations.py` | No |
| search algorithm | No |
| no new dependencies | PASS |

---

## Technical Notes

### Why `log_config=None` works

uvicorn's default `log_config` uses `logging.config.dictConfig` with formatters that call `.isatty()` on `sys.stdout`. In `--noconsole` mode, `sys.stdout` is `None`. Setting `log_config=None` tells uvicorn not to configure logging at all, leaving our `logging_setup.py` handlers as the only configured logging.

### PowerShell CJK encoding workaround

PowerShell's parser misinterprets CJK string literals in some environments (likely a UTF-8 BOM vs code page interaction). The fix: Chinese product name `"资料浏览器"` is hardcoded inside `_build_copy.py` (Python source file, always UTF-8) and printed as the last line of stdout. PowerShell captures that line as the product name variable. This is clean and reliable.

### `dirs_exist_ok=True` for locked directories

Windows Defender holds file handles that prevent `shutil.rmtree()` on directories it has scanned. Rather than retrying or failing, we use `shutil.copytree(..., dirs_exist_ok=True)` which overwrites files in-place. This works even when the destination directory is locked.

---

## Known Issues

- None.

---

## Recommendation

Approve and merge. All acceptance criteria met:

1. ✅ `--noconsole` exe no longer crashes at startup
2. ✅ No `Unable to configure formatter 'default'`
3. ✅ No `NoneType has no attribute isatty`
4. ✅ Logs still write to `app_data/logs/app.log`
5. ✅ Final release dir is `dist/资料浏览器/`
6. ✅ Final exe is `dist/资料浏览器/资料浏览器.exe`
7. ✅ Build script uses `resource_browser_build`, not `ziliao` or `ziliao_build`
8. ✅ Final release has no `resource_browser_build.exe`
9. ✅ `app_data/config.example.json` present
10. ✅ `app_data/config.json` absent
11. ✅ Button "切换资料目录" with full-width layout
12. ✅ Button "退出" with correct ID
13. ✅ Switch/exit functionality unchanged
14. ✅ root/Office/AI/search/annotations not modified
15. ✅ No new dependencies
16. ✅ No dist/build/exe/config/API key committed
17. ✅ Committed and pushed to `origin/main`
