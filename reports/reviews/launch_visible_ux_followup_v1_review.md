# Review: LAUNCH-VISIBLE-UX-FOLLOWUP-V1

## Decision: PASS

---

## Summary

Two UX improvements delivered cleanly:
1. **Compact sidebar layout**: "资料浏览器  [退出][切换]" on one row
2. **Reliable browser launch**: `os.startfile()` on Windows + health-polling wait before open

---

## Changed Files

| File | What Changed |
|------|-------------|
| `server.py` | New `_open_app_url()` (os.startfile + webbrowser fallback), new `_open_browser_when_ready()` (polls /api/health then opens), updated duplicate launch to use `_open_app_url()`, removed unused `_open_browser_later()` |
| `static/index.html` | Single compact title row with `.sidebar-actions` wrapper div around both buttons |
| `static/style.css` | Replaced `.sidebar-root-actions` full-width rule with `.sidebar-title-row`, `.sidebar-actions {display:flex;gap:6px;flex-shrink:0}`, `.sidebar-actions button {white-space:nowrap}` |

---

## Implemented

- **sidebar buttons same row**: `资料浏览器` + `[退出][切换]` on one row, exit before switch ✅
- **exit before switch**: shutdown-btn comes before pick-root in HTML ✅
- **robust `_open_app_url`**: `os.startfile(url)` on Windows → most visible (existing browser), webbrowser fallback ✅
- **first launch waits for /api/health**: `_open_browser_when_ready()` polls until ready ✅
- **duplicate launch opens via `_open_app_url`**: uses new helper, logs "已有服务运行中" ✅

---

## Validation

| Check | Result |
|-------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_PASS | PASS |
| dev launch opens browser (log: "已请求打开浏览器页面") | PASS |
| `--no-browser` does not open browser | PASS |
| duplicate dev launch reuses service | PASS |
| packaged exe launch visible | PASS |
| packaged duplicate launch visible | PASS |
| shutdown still works | PASS |
| no forbidden files tracked | PASS |

---

## Stability Review

| Module | Changed? |
|--------|----------|
| root state machine | No |
| build scripts | No |
| logging_setup.py | No |
| Office / converter | No |
| AI providers | No |
| annotations | No |
| search | No |
| no new dependencies | PASS |

---

## Known Issues

- None.

---

## Recommendation

Approve and merge. All acceptance criteria met:

1. ✅ 左上角为：资料浏览器  退出  切换
2. ✅ 退出和切换同一行
3. ✅ 退出在切换前面
4. ✅ 不再有全宽"切换资料目录"
5. ✅ exe 首次启动能明显打开页面
6. ✅ exe 重复启动能明显打开已有页面或新标签
7. ✅ --no-browser 仍然不打开页面
8. ✅ 不启动第二个 uvicorn
9. ✅ 不自动换端口
10. ✅ 不杀旧进程
11. ✅ shutdown 仍然可用
12. ✅ root/Office/AI/search/annotations 未改
13. ✅ build scripts 未改
14. ✅ 无新依赖
15. ✅ 无 dist/build/exe/config/API key 被提交
16. ✅ 已提交并 push to origin/main
