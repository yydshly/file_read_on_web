# 81. USER-FRIENDLY-LAUNCH-V1

**Date**: 2026-06-04
**Task**: USER-FRIENDLY-LAUNCH-V1
**Decision**: ✅ PASS

---

## 摘要

在不改变核心业务逻辑的前提下，实现了软件启动体验优化：日志落盘、重复启动复用、退出程序入口、自定义 favicon。

---

## 实现的变更

### 1. 日志落盘 (`logging_setup.py`)

- 日志文件名从 `server.log` 改为 `app.log`
- 开发模式：console + file 双输出
- 打包模式：file 必须存在
- `maxBytes=2MB`，`backupCount=5`，避免无限增长

### 2. 启动日志丰富 (`server.py`)

新增日志字段：
```
程序启动: 资料浏览器
app_dir: ...
data: ...
config: ...
frozen: True/False
root: ...
LibreOffice: ...
host: 127.0.0.1  port: 8770
```

### 3. `app_id` 标识 (`server.py`)

`/api/health` 新增字段：
```json
{
  "app_id": "file_read_on_web",
  "app_name": "资料浏览器"
}
```

### 4. 重复启动复用 (`server.py`)

新增 `_is_our_service_running()` 函数：
- 启动前检测 8770 端口是否有本软件服务
- 通过 `/api/health` 响应中的 `app_id` 确认是本软件
- 确认为本软件后打开浏览器，当前进程退出
- 不杀旧进程，不换端口

### 5. `POST /api/shutdown` (`server.py`)

- 仅允许本地访问（127.0.0.1 / localhost / ::1）
- 清理残留 soffice 进程
- 延迟 0.6 秒后退出
- 日志记录退出请求

### 6. 页面退出按钮 (`static/index.html`, `static/app.js`)

- 左侧边栏标题区新增"退出程序"按钮
- 点击确认后 POST `/api/shutdown`
- 成功后在主视图显示"程序已退出，可以关闭此页面"
- 按钮禁用防重复点击

### 7. 浏览器 favicon

- `static/favicon.ico`（从 `assets/app.ico` 复制）
- `index.html` 添加 `<link rel="icon">` 和 `<link rel="shortcut icon">`
- 后端 `/favicon.ico` 路由返回同一文件
- 打包时正确嵌入 `_internal/static/favicon.ico`

### 8. README 更新

- 新增 `--noconsole` 打包命令说明
- 说明 `start.bat` 为开发调试入口
- 说明正式分发使用 `--noconsole`

---

## 未实现项

以下为任务明确禁止的项目，本轮未实现：

- ❌ 系统托盘
- ❌ WebView / Electron / Tauri / pywebview
- ❌ 自动杀旧进程
- ❌ 自动换端口（8770 被占用则不启动新服务）
- ❌ 修改 root 状态机
- ❌ 修改 Office 转换逻辑
- ❌ 修改 AI provider 逻辑
- ❌ 修改 annotations 数据结构
- ❌ 修改搜索算法
- ❌ 新增依赖

---

## 验证结果

| 检查项 | 状态 |
|--------|------|
| `python -m compileall .` | ✅ PASS |
| TEXT_HEALTH_PASS | ✅ PASS |
| `/api/health` 包含 `app_id` | ✅ PASS |
| `logs/app.log` 存在 | ✅ PASS |
| 启动日志包含所有字段 | ✅ PASS |
| 重复启动复用已有服务 | ✅ PASS |
| `POST /api/shutdown` 返回正确 | ✅ PASS |
| 服务器延迟后关闭 | ✅ PASS |
| 页面退出按钮存在 | ✅ PASS |
| favicon 路由 `/favicon.ico` | ✅ 200 |
| favicon 静态文件 `/static/favicon.ico` | ✅ 200 |
| favicon 打包进 exe | ✅ PASS |
| `--noconsole` 打包成功 | ✅ PASS |
| README 包含 noconsole 说明 | ✅ PASS |

---

## 稳定性确认

| 检查项 | 状态 |
|--------|------|
| root 逻辑未变 | ✅ |
| preview 逻辑未变 | ✅ |
| Office 转换未变 | ✅ |
| annotations schema 未变 | ✅ |
| AI provider 未变 | ✅ |
| 无新增依赖 | ✅ |
| 无自动杀进程 | ✅ |
| 无自动换端口 | ✅ |

---

## 已知问题

无阻塞问题。

---

## 验收标准

| # | 标准 | 状态 |
|---|------|------|
| 1 | 正式打包命令包含 --noconsole | ✅ |
| 2 | 无终端运行时有 app_data/logs/app.log | ✅ |
| 3 | /api/health 有 app_id=file_read_on_web | ✅ |
| 4 | 重复启动会复用已有服务 | ✅ |
| 5 | 页面有"退出程序"入口 | ✅ |
| 6 | POST /api/shutdown 能关闭服务 | ✅ |
| 7 | 浏览器 favicon 生效 | ✅ |
| 8 | 不改变 root/preview/Office/annotations/AI 逻辑 | ✅ |
| 9 | 不引入新依赖 | ✅ |
| 10 | 不提交 dist/build/exe/config.json/API key | ✅ |
| 11 | 提交并 push 到 origin/main | ✅ |

**结论**: ✅ **PASS** - 准备进入下一任务
