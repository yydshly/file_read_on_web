# 资料浏览器

本项目是一个 Windows 本地资料浏览工具：用浏览器作为界面，用本地 Python 服务读取资料目录、预览 PDF/图片/文本/Markdown，并通过 LibreOffice 将 Word、Excel、PPT 等 Office 文档转换为 PDF 后预览。

**当前形态：** 本地 FastAPI 后台服务 + 用户默认浏览器 UI + 系统托盘。

> **重要说明：**
> - 当前 UI 运行在用户**默认浏览器**中，不是独立 WebView 桌面窗口。
> - **关闭浏览器不等于退出程序。** 后台服务持续运行，直到使用页面"退出"或托盘"退出程序"。
> - Windows 任务栏通常显示浏览器图标，不显示资料浏览器独立图标。

**当前版本：** `0.1.0` — Release Baseline V1

---

## 功能概览

| 功能 | 状态 |
|------|------|
| 资料目录选择 | ✓ |
| 文件树浏览 | ✓ |
| 文件名筛选 | ✓ |
| 全文搜索 | ✓ |
| Markdown/Text 预览 | ✓ |
| PDF 预览 | ✓ |
| 图片预览 | ✓ |
| Office 转 PDF 预览 | ✓（依赖 LibreOffice） |
| 收藏 / 标签 / 笔记 | ✓ |
| 打开本地位置 | ✓ |
| 下载原文件 | ✓ |
| 系统托盘 | ✓ |
| 重复启动复用服务 | ✓ |
| AI 文档整理 | △（需配置 config.json） |

---

## 安装依赖

```powershell
python -m pip install -r requirements.txt
```

建议使用 Python 3.10 或更新版本。

---

## 开发模式启动

```powershell
# 默认启动（自动打开浏览器）
python server.py

# 指定端口
python server.py --port 8770

# 不自动打开浏览器
python server.py --no-browser

# 强制启用托盘（开发模式默认不显示托盘）
python server.py --tray

# 禁用托盘
python server.py --no-tray
```

> **开发模式默认不启用托盘**，可用 `--tray` 强制启用。

---

## 打包版启动

```powershell
双击 dist/资料浏览器/资料浏览器.exe
```

**启动行为：**
- 无终端窗口（后台服务）
- 默认浏览器自动打开 `http://127.0.0.1:8770/`
- 系统托盘显示资料浏览器图标
- 重复双击 exe 不会启动第二个服务，会复用已有服务并打开页面

---

## 基本使用流程

1. 启动程序
2. 如果未选择资料目录，点击左上角"切换"选择资料文件夹
3. 左侧文件树加载
4. 点击文件预览（PDF / 图片 / Office / Markdown / Text）
5. 可使用收藏、标签、笔记
6. 顶部搜索框回车进行文档内容搜索
7. 点击"打开位置"在资源管理器中定位本地文件
8. 点击"下载"下载原文件
9. 需要退出时：点击页面右上角"退出"**或**托盘"退出程序"

> **关闭浏览器 ≠ 退出程序。** 程序在后台持续运行，直到使用"退出"。

---

## 配置 AI

AI 功能（如文档整理）需要手动配置：

1. 复制 `app_data/config.example.json` 为 `app_data/config.json`
2. 填写 `config.json` 中的 AI 相关字段（provider、api_key 等）

```powershell
# 示例：复制配置模板
copy app_data\config.example.json app_data\config.json
```

> **安全提醒：不要将 `config.json`（包含真实 API key）提交到 Git 或放入发布包。**

---

## LibreOffice 依赖

Office 文件（`.doc` `.docx` `.xls` `.xlsx` `.ppt` `.pptx`）预览依赖 **LibreOffice**。

PDF、图片、Markdown、Text **不依赖** LibreOffice。

**推荐安装路径（二选一）：**

```
C:\Program Files\LibreOffice
D:\software\LibreOffice
```

**已验证路径：** `D:\software\LibreOffice\program\soffice.exe`

**自定义路径设置：**

```powershell
# 方式一：完整路径
$env:SOFFICE_PATH="D:\software\LibreOffice\program\soffice.exe"

# 方式二：安装目录
$env:LIBREOFFICE_HOME="D:\software\LibreOffice"
```

---

## 打包

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

**输出：** `dist/资料浏览器/`

```
dist/资料浏览器/
  资料浏览器.exe      ← 主程序（无终端）
  _internal/         ← 运行时文件
  app_data/          ← 运行数据
    config.example.json  ← 配置模板
```

---

## 生成发布 zip

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_release_zip.ps1
```

**输出示例：**

```
release_packages/资料浏览器-v0.1.0-windows-20260604.zip
```

**包含：** `资料浏览器.exe`、`_internal/`、`app_data/config.example.json`

**不含：** `config.json`（含 API key）、日志、缓存、用户运行数据

---

## 系统托盘

正式打包版默认显示托盘图标。

**托盘菜单：**

- **打开资料浏览器** — 在浏览器中重新打开应用
- **查看日志** — 打开 `app_data/logs/app.log`
- **打开数据目录** — 打开 `app_data/` 文件夹
- **退出程序** — 停止后台服务并退出

**关闭浏览器 ≠ 退出程序。** 要真正退出，应使用页面"退出"或托盘"退出程序"。

---

## 开发模式 vs 正式模式

| | 开发模式 | 正式打包 |
|---|---------|---------|
| 启动方式 | `python server.py` 或双击 `start.bat` | 双击 `资料浏览器.exe` |
| 终端窗口 | 显示 | **不显示** |
| 日志文件 | `logs/app.log` | `app_data/logs/app.log` |
| 托盘 | 默认不显示 | 默认显示 |
| 重复启动 | 端口冲突 | 自动复用已有服务 |

---

## 迁移说明

打包版会把运行数据写入 `app_data/`。迁移时整体复制 `资料浏览器/` 目录即可。

如果程序目录不可写，会自动改写到 `%LOCALAPPDATA%\资料浏览器\`。

---

## 常见问题

**Q: 双击 exe 后为什么没有窗口？**

A: 这是无终端后台服务，默认会打开浏览器，并在系统托盘显示图标。不是独立桌面窗口。

**Q: 关闭浏览器后程序还在吗？**

A: 在。关闭浏览器不等于退出程序。需要使用页面"退出"或托盘"退出程序"来停止服务。

**Q: Office 文件打不开怎么办？**

A: 安装 LibreOffice，推荐 `C:\Program Files\LibreOffice` 或 `D:\software\LibreOffice`。

**Q: AI 功能不能用怎么办？**

A: 复制 `app_data/config.example.json` 为 `app_data/config.json`，填写 API key。

**Q: 点击"打开位置"后没看到资源管理器？**

A: 程序会尽量前置资源管理器窗口，如果被系统阻止，请查看任务栏。

**Q: 重复双击 exe 为什么没有反应？**

A: 程序检测到已有服务运行，会自动打开已有浏览器页面，不会启动第二个服务。

---

## 发布前检查

正式分发前请执行：

- [Release Checklist V1](docs/94-release-checklist-v1.md)

---

## 当前稳定基线

- [Release Baseline V1](docs/89-release-baseline-v1.md)
- 版本：`0.1.0`
