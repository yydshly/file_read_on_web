# Release Baseline V1 — 资料浏览器 Windows MVP

```
baseline_name:  Release Baseline V1
product_name:    资料浏览器
target_platform: Windows
runtime_shape:   本地后台服务 + 浏览器 UI + 系统托盘
branch:         main
baseline_commit: 3f7bfc4
date:           2026-06-04
```

---

## 1. 当前产品形态

资料浏览器是一个 Windows 本地资料浏览工具。

**运行方式：**

1. 用户双击 `资料浏览器.exe`
2. 后台 FastAPI 服务启动（无终端窗口）
3. 默认浏览器打开 `http://127.0.0.1:8770/`
4. 系统托盘显示资料浏览器图标
5. 用户关闭浏览器后，后台服务仍运行，可通过托盘重新打开
6. 用户可通过页面"退出"或托盘"退出程序"关闭后台服务

**重要说明：**

- 当前 UI 运行在用户**默认浏览器**中，不是独立 WebView 桌面窗口
- Windows 任务栏图标通常是**浏览器图标**，不显示资料浏览器独立图标
- 托盘图标代表后台服务仍在运行

---

## 2. 已实现功能范围

| 功能 | 状态 | 说明 |
|------|------|------|
| 资料目录选择 | ✓ | 可切换不同根目录 |
| 文件树浏览 | ✓ | 递归展开，含文件名排序 |
| 文件名筛选 | ✓ | 前端 UI 输入框 |
| 全文搜索 | ✓ | 基于已索引文档内容 |
| Markdown/Text 预览 | ✓ | 前端渲染 |
| PDF 预览 | ✓ | iframe 内联显示 |
| 图片预览 | ✓ | 直接显示 |
| Office 转 PDF 预览 | ✓ | doc/docx/xls/xlsx/ppt/pptx → LibreOffice → PDF |
| 收藏 | ✓ | 持久化到 annotations.json |
| 标签 | ✓ | 每个文件独立标签，支持 palette |
| 笔记 | ✓ | 每个文件独立笔记 |
| 打开本地位置 | ✓ | API + Windows Explorer 集成 |
| 下载原文件 | ✓ | /api/raw 接口 |
| AI 未配置状态 | ✓ | 友好提示，不崩溃 |
| AI 文档整理 | △ | 依赖 config.json + API key |
| 系统托盘 | ✓ | 4 项菜单 |
| 日志 | ✓ | app_data/logs/app.log |
| 重复启动复用已有服务 | ✓ | 端口检测 + health API |
| 页面退出 | ✓ | /api/shutdown → 干净退出 |
| 托盘退出 | ✓ | 与页面退出共用同一退出逻辑 |

---

## 3. 打包方式

**唯一推荐打包命令：**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

**输出目录：**

```
dist/资料浏览器/
  资料浏览器.exe      ← 主程序（--noconsole，无终端）
  _internal/         ← PyInstaller 运行时文件
  app_data/          ← 运行数据目录
    config.example.json  ← 配置模板（AI key 参考此文件）
```

**禁止发布的内容：**

```
dist/  目录本身（发布前应 zip 压缩）
_build/  目录
resource_browser_build.exe  ← 内部中间产物
config.json  ← 包含真实 API key
任何包含真实 key 的文件
```

> 打包脚本会自动排除 config.json，只复制 config.example.json。

---

## 4. 运行数据目录

打包版优先使用：

```
dist/资料浏览器/app_data/
```

其中包含：

| 文件 | 说明 |
|------|------|
| `config.example.json` | 配置模板，复制为 config.json 后填写 key |
| `config.json` | 用户手动创建，包含 AI key，**不得发布** |
| `state.json` | 自动管理：上次目录、上次文件 |
| `annotations.json` | 收藏、标签、笔记 |
| `search_index.json` | 搜索索引缓存 |
| `logs/app.log` | 应用运行日志 |
| `cache/` | Office 转 PDF 缓存 |

> 如果程序目录不可写，程序会回退到用户本地应用数据目录（`%LOCALAPPDATA%\资料浏览器`）。

**迁移说明：**

整体复制 `资料浏览器/` 目录（含 `app_data/`）到新电脑即可。API key 需用户自行在新环境的 `config.json` 中配置。

---

## 5. 配置文件说明

`app_data/config.example.json` 是配置模板。如需启用 AI 功能：

1. 将 `config.example.json` 复制为 `config.json`
2. 填写其中的 `ai` 配置块（provider、api_key 等）

**安全要求：**

- 发布包中**不得包含**真实的 `config.json`
- 发布包中**不得包含**任何 API key
- 用户的 `config.json` 只存在于本地，不应提交到任何共享位置

---

## 6. LibreOffice / Office 预览依赖

Office 文件预览依赖 **LibreOffice**（外部依赖，用户需自行安装）。

**已验证的安装路径：**

```
D:\software\LibreOffice\program\soffice.exe
```

**当前查找优先级：**

1. 环境变量 `SOFFICE_PATH`（完整路径）
2. 环境变量 `LIBREOFFICE_HOME`
3. `exe 同目录下 libreoffice/program/soffice.exe`
4. 系统 PATH 中的 `soffice`
5. `C:\Program Files\LibreOffice`
6. `C:\Program Files (x86)\LibreOffice`
7. `D:\software\LibreOffice`

**推荐用户安装位置（二选一）：**

```
C:\Program Files\LibreOffice
D:\software\LibreOffice
```

**自定义路径设置方式：**

```powershell
# 方式一：完整路径
$env:SOFFICE_PATH="D:\software\LibreOffice\program\soffice.exe"

# 方式二：目录
$env:LIBREOFFICE_HOME="D:\software\LibreOffice"
```

**支持格式：** `.doc` `.docx` `.xls` `.xlsx` `.ppt` `.pptx` 等 → 转换为 PDF 后预览。

> 注意：PDF、图片、文本、Markdown 预览**不依赖** LibreOffice。

---

## 7. 系统托盘说明

**启用规则：**

| 模式 | 默认状态 | 可用参数 |
|------|---------|---------|
| 正式打包 exe | 默认**启用**托盘 | `--no-tray` 禁用 |
| 开发模式 `python server.py` | 默认**不启用**托盘 | `--tray` 强制启用 |

**托盘菜单项：**

```
打开资料浏览器   → 在浏览器中重新打开应用
查看日志        → 打开 app_data/logs/app.log
打开数据目录    → 打开 app_data/ 文件夹
退出程序        → 停止后台服务并退出
```

**关闭浏览器 ≠ 退出程序：**

关闭浏览器页面后，后台 FastAPI 服务仍在运行。托盘图标持续显示。要真正退出，应使用：
- 页面右上角"退出"按钮，或
- 托盘菜单"退出程序"

---

## 8. 已验证测试记录

以下任务结果经手工验证：

**PACKAGED-RELEASE-SMOKE-TEST-V1**（commit d710e3c）

| 验证项 | 结果 |
|--------|------|
| 打包脚本执行 | PASS |
| exe 启动 | PASS |
| 无终端窗口 | PASS |
| 浏览器自动打开 | PASS |
| favicon 显示 | PASS |
| 无 root 状态提示 | PASS |
| 切换 root | PASS |
| 文件树加载 | PASS |
| Markdown/Text 预览 | PASS |
| PDF 预览 | PASS |
| 图片预览 | PASS |
| Office 转 PDF 预览 | PASS |
| 收藏/标签/笔记 | PASS |
| 全文搜索 | PASS |
| 打开位置 API | PASS |
| 下载 API | PASS |
| AI 未配置状态 | PASS |
| 重复启动复用已有服务 | PASS |
| 页面退出 | PASS |

**PACKAGED-MEDIA-OFFICE-SMOKE-TEST-V1**（commit c8adc31）

| 验证项 | 结果 |
|--------|------|
| PDF 预览 Content-Type | PASS (`application/pdf`) |
| 图片预览 Content-Type | PASS (`image/png`) |
| Office DOCX → PDF 转换 | PASS (`application/pdf`, 23906 bytes) |
| LibreOffice 被检测到 | PASS (`D:\software\LibreOffice\...`) |
| reveal API | PASS (`{"ok":true}`) |
| download API | PASS (raw bytes 返回正确) |
| 搜索"媒体预览测试" | PASS (test.txt 被找到) |
| 页面退出 | PASS |
| 无 ERROR 日志 | PASS |

**TRAY-APP-LAUNCH-V1**（commit 3f7bfc4）

| 验证项 | 结果 |
|--------|------|
| 打包 exe 默认托盘 | PASS (`tray_enabled=True`, `tray_started=True`) |
| 开发模式默认无托盘 | PASS (`tray_enabled=False`) |
| `python server.py --tray` | PASS (托盘正常显示) |
| `python server.py --no-tray` | PASS (托盘不显示) |
| 托盘菜单"打开资料浏览器" | PASS |
| 托盘菜单"查看日志" | PASS |
| 托盘菜单"打开数据目录" | PASS |
| 托盘菜单"退出程序" | PASS |
| 页面退出 → 托盘消失 | PASS |
| 重复启动无第二个托盘 | PASS |

---

## 9. 当前已知限制

| # | 限制 | 说明 |
|---|------|------|
| 1 | UI 运行在默认浏览器中 | 不是独立 WebView 桌面窗口；任务栏显示浏览器图标 |
| 2 | Office 预览依赖 LibreOffice | 用户需自行安装配置；无内置轻量方案 |
| 3 | AI 能力依赖 config.json + API key | 不配置则 AI 功能灰显，不崩溃 |
| 4 | 收藏/标签/笔记按绝对路径分桶 | 换电脑/换盘符/移动目录后需重建 annotations |
| 5 | search_index 为全局文件 | 后续可按 workspace/root 拆分，支持多资料库 |
| 6 | 暂不支持扫描版 PDF OCR | scanned PDFs 无法用于 AI 整理/搜索 |
| 7 | 暂无安装包/版本号/自动更新 | 用户需手动复制目录或制作 zip 分发 |
| 8 | 暂无 WebView/Electron/Tauri 方案 | 当前形态依赖用户默认浏览器 |

---

## 10. 当前不建议立即做的事

```
1. 不建议立即做大重构
   → 当前形态稳定，保持最小变更节奏

2. 不建议立即引入 workspace/root_id 数据模型
   → 产品化阶段再设计，当前绝对路径方案够用

3. 不建议立即做 OCR/RAG
   → 依赖外部服务，引入复杂度，当前手动索引够用

4. 不建议立即做 WebView/Electron/Tauri
   → 引入巨大复杂度，当前浏览器方案已验证可用

5. 不建议把 LibreOffice 强行打进默认轻量包
   → 包体巨大(>300MB)，增加分发成本；
   → 用户已有 LibreOffice 时重复安装；
   → 当前外部依赖方案已够用
```

---

## 11. 推荐后续路线

| 优先级 | 任务 | 说明 |
|--------|------|------|
| 1 | VERSIONING-V1 | 增加 `APP_VERSION` 常量；`/api/version`；README 显示当前版本 |
| 2 | RELEASE-ZIP-PACKAGE-V1 | 打包后自动生成 zip；名称含版本号+日期；发布包不含 config.json |
| 3 | RELEASE-CHECKLIST-V1 | 固化发布前检查清单（验证项、禁止项） |
| 4 | INSTALLER-EVALUATION-V1 | 评估 Inno Setup / NSIS；是否需要独立安装包 |
| 5 | DEV-VS-PACKAGED-RUNTIME-DIFF-V1 | 文档化 `start.bat` 和 exe 运行时差异 |
| 6 | WORKSPACE-DATA-MODEL-V1 | 产品化阶段再设计 root/workspace 数据迁移方案 |

---

## 12. 快速启动参考

**打包（Windows）：**

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

**运行打包版：**

```
双击 dist/资料浏览器/资料浏览器.exe
```

**运行开发版：**

```powershell
python server.py --port 8770
```

**开发版启用托盘：**

```powershell
python server.py --tray
```

**禁用托盘：**

```powershell
python server.py --no-tray
dist\资料浏览器\资料浏览器.exe --no-tray
```
