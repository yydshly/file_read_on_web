# 82. USER-FRIENDLY-LAUNCH-V1-FOLLOWUP

**Date**: 2026-06-04
**Task**: USER-FRIENDLY-LAUNCH-V1-FOLLOWUP
**Decision**: ✅ PASS

---

## 摘要

修复了 `USER-FRIENDLY-LAUNCH-V1` 中重复启动分支的浏览器打开方式风险：将 `_open_browser_later()` 改为同步 `webbrowser.open()`。

---

## 问题描述

上一版本中，重复启动检测到已有服务后调用 `_open_browser_later()` 打开浏览器，然后立即 `return` 退出主进程。

`_open_browser_later()` 使用 daemon 线程延迟打开浏览器。如果主进程立即退出，daemon 线程可能还没来得及打开浏览器就被终止，导致用户看到"第二次双击没反应"的现象。

---

## 修复内容

### 修复前

```python
if not args.force_server and _is_our_service_running(args.host, args.port):
    log.info("已有服务运行中 (http://%s:%d)，复用已有服务", args.host, args.port)
    if not args.no_browser:
        _open_browser_later(f"http://{args.host}:{args.port}/")
    return
```

### 修复后

```python
if not args.force_server and _is_our_service_running(args.host, args.port):
    url = f"http://{args.host}:{args.port}/"
    log.info("已有服务运行中 (%s)，复用已有服务", url)
    if not args.no_browser:
        try:
            webbrowser.open(url)
            log.info("已打开已有服务页面: %s", url)
        except Exception as e:
            log.warning("打开已有服务页面失败: %s", e)
    return
```

### 说明

- 使用同步 `webbrowser.open()` 替代 daemon 线程的 `_open_browser_later()`
- 首次启动仍使用 `_open_browser_later()`（不受影响）
- 记录"已打开已有服务页面"日志
- 失败时记录警告日志

---

## 验证结果

| 检查项 | 状态 |
|--------|------|
| `python -m compileall .` | ✅ PASS |
| TEXT_HEALTH_PASS | ✅ PASS |
| 重复启动不启动第二个 uvicorn | ✅ PASS |
| 重复启动不报端口占用 | ✅ PASS |
| 日志记录"已有服务运行中" | ✅ PASS |
| 日志记录"已打开已有服务页面" | ✅ PASS |
| 只修改 existing service 分支 | ✅ PASS |
| 首次启动行为不变 | ✅ PASS |

---

## 稳定性确认

| 检查项 | 状态 |
|--------|------|
| shutdown 未变 | ✅ |
| logging 配置未变 | ✅ |
| favicon 未变 | ✅ |
| root 逻辑未变 | ✅ |
| preview 逻辑未变 | ✅ |
| Office 转换未变 | ✅ |
| AI provider 未变 | ✅ |
| annotations 未变 | ✅ |
| 无新增依赖 | ✅ |

---

## 结论

**✅ PASS** - 修复完成，准备提交
