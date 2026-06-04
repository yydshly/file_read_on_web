# Task 85: LAUNCH-VISIBLE-UX-FOLLOWUP-V1

## Background

After PACKAGED-NOCONSOLE-BOOT-FIX-V1, the packaged exe starts reliably but:

1. **Sidebar layout**: the "资料浏览器 + [切换资料目录]" stacked layout was a regression from the desired compact single-row design "资料浏览器 [退出] [切换]"
2. **Browser launch visibility**: `webbrowser.open()` in `--noconsole` mode is unreliable; users couldn't tell if the app had started

## Changes

### 1. static/index.html — compact sidebar layout

Changed from two-row layout to single compact row:

```html
<div class="row sidebar-title-row">
  <strong>资料浏览器</strong>
  <div class="sidebar-actions">
    <button id="shutdown-btn" type="button" title="退出后台服务">退出</button>
    <button id="pick-root" type="button" title="切换根目录">切换</button>
  </div>
</div>
```

Button IDs unchanged: `shutdown-btn`, `pick-root`.

### 2. static/style.css — sidebar-actions styling

Replaced the full-width `.sidebar-root-actions` block with:

```css
.sidebar-title-row {
  justify-content: space-between;
  gap: 8px;
}

.sidebar-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.sidebar-actions button {
  white-space: nowrap;
}
```

### 3. server.py — robust URL opening

**New `_open_app_url(url)`** — uses `os.startfile()` on Windows (most reliable, opens in existing browser window/tab), falls back to `webbrowser.open(new=2)` on other platforms:

```python
def _open_app_url(url: str) -> bool:
    log = get_logger("browse")
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)
        else:
            webbrowser.open(url, new=2)
        log.info("已请求打开浏览器页面: %s", url)
        return True
    except Exception as e:
        log.warning("打开浏览器页面失败: %s", e)
        try:
            webbrowser.open(url, new=2)
            log.info("已通过 webbrowser fallback 打开页面: %s", url)
            return True
        except Exception as e2:
            log.warning("webbrowser fallback 也失败: %s", e2)
            return False
```

**New `_open_browser_when_ready(url, health_url, timeout=8.0)`** — polls `/api/health` until the server is ready, then calls `_open_app_url()`:

```python
def _open_browser_when_ready(url, health_url, timeout=8.0):
    def _open():
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                import urllib.request
                with urllib.request.urlopen(health_url, timeout=0.4) as resp:
                    if resp.status == 200:
                        break
            except Exception:
                time.sleep(0.25)
        _open_app_url(url)
    threading.Thread(target=_open, daemon=True).start()
```

**First launch**: replaced `_open_browser_later()` with `_open_browser_when_ready()`, waiting for `/api/health` before opening.

**Duplicate launch**: replaced direct `webbrowser.open()` with `_open_app_url()`.

**Removed**: `_open_browser_later()` (no longer used).

### 4. app.js

No changes required. `pickBtn.textContent = '切换'` was already in place (unicode escape `切换`).

## Validation Results

| Check | Result |
|-------|--------|
| `python -m compileall .` | PASS |
| TEXT_HEALTH_CHECK | PASS |
| dev launch — log shows "已请求打开浏览器页面" | PASS |
| `--no-browser` — no browser open | PASS |
| packaged exe — log shows "已请求打开浏览器页面" | PASS |
| packaged exe — `/api/health` returns `app_id: file_read_on_web` | PASS |
| packaged duplicate launch — log shows "已有服务运行中" + "已请求打开浏览器页面" | PASS |
| compact sidebar layout: 退出 + 切换 on same row | PASS |

## Files Changed

- `server.py` — `_open_app_url`, `_open_browser_when_ready`, duplicate launch updated
- `static/index.html` — compact sidebar layout
- `static/style.css` — `.sidebar-actions` flexbox styles
- `static/app.js` — unchanged

## Files NOT Changed (stability)

- `logging_setup.py` — unchanged
- `scripts/build_windows.ps1`, `scripts/build_windows.bat`, `scripts/_build_copy.py` — unchanged
- `converter.py`, `annotations.py`, `search.py`, `ai/` — unchanged
- `requirements.txt` — no new dependencies
