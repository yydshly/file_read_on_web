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

### 大目录首次加载说明

首次打开很大的资料目录（如数万文件）时，加载可能较慢，原因是文件树扫描、搜索索引预建、Office 文件预热会同时进行。建议首次验证时使用较小的目录。

后续打开同一目录会利用缓存，速度会明显提升。

> 如果首次体验较慢，建议先用小目录（如几十到几百个文件）验证功能是否正常，再用于大目录。

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

**版本兼容性：**

较新版本的 LibreOffice 安装程序可能要求 Windows 10 或更高版本。如果当前系统为 Windows 7/8/8.1，安装程序会提示"需要 Windows 10 及更高版本"，这是操作系统与 LibreOffice 版本不兼容，不是本应用的问题。此时可尝试安装较旧版 LibreOffice，或在 Windows 10/11 机器上运行本应用。

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

> 修改环境变量后需重启应用才能生效。

---

### Office 预览失败排查

如果 Office 文件预览失败，按以下顺序检查：

1. **LibreOffice 未安装？** 确认已安装 LibreOffice，推荐路径见上。
2. **Windows 版本不兼容？** 较新版 LibreOffice 需要 Windows 10+。
3. **路径错误？** 确认 `SOFFICE_PATH` 或 `LIBREOFFICE_HOME` 指向 `program\soffice.exe`。
4. **首次转换慢？** 首次打开 Office 文件需要转换，可能需数秒；再次打开时使用缓存会更快。
5. **文件损坏或加密？** 部分损坏或加密的 Office 文件可能转换失败。
6. **缓存过期？** 可在页面"设置"中清除转换缓存后重试。

非 Office 格式（PDF、图片、Markdown、Text）**不依赖** LibreOffice，如果这些格式预览失败，问题不在 LibreOffice。

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

**发布 zip 应在仓库外验证。** 将 zip 解压到 `D:\tmp\` 或其他非项目目录后测试，不要在 `dist/`、`build/`、`release_packages/` 内直接测试。

验证要点：
- exe 启动无终端窗口 ✓
- 浏览器自动打开 ✓
- 托盘图标出现 ✓
- 关闭浏览器后服务仍在 ✓
- 托盘"退出"完全停止服务 ✓
- zip 中不包含 `config.json` ✓

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

**Q: LibreOffice 安装时提示需要 Windows 10 以上怎么办？**

A: 较新版 LibreOffice 需要 Windows 10/11。如果系统是 Windows 7/8/8.1，可尝试安装较旧版 LibreOffice，或在 Windows 10+ 机器上运行本应用。

**Q: 没装 LibreOffice 还能用吗？**

A: 可以。PDF、图片、Markdown、Text 预览不依赖 LibreOffice。只有 Office 文件（doc/docx/xls/xlsx/ppt/pptx）才需要 LibreOffice。

**Q: 为什么第一次打开大目录比较慢？**

A: 首次打开大目录时，文件树扫描、搜索索引预建、Office 文件预热会同时进行。建议首次验证使用较小的目录，后续会明显加快。

**Q: 发布 zip 应该在哪里测试？**

A: 应将 zip 解压到仓库外的目录（如 `D:\tmp\`）进行测试，不要在 `dist/`、`build/`、`release_packages/` 内直接运行。

---

## 发布前检查

正式分发前请执行：

- [Release Checklist V1](docs/94-release-checklist-v1.md)

---

## 当前稳定基线

- [Release Baseline V1](docs/89-release-baseline-v1.md)
- 版本：`0.1.0`
