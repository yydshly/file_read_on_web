# 资料浏览器

本项目是一个本地资料浏览工具：用浏览器作为界面，用本地 Python 服务读取资料目录、预览 PDF/图片/文本/Markdown，并通过 LibreOffice 将 Word、Excel、PPT 等 Office 文档转换为 PDF 后预览。

## 功能概览

- 浏览本地资料目录
- 预览 PDF、图片、文本、Markdown
- 通过 LibreOffice 预览 `.doc`、`.docx`、`.xls`、`.xlsx`、`.ppt`、`.pptx` 等 Office 文件
- Office 转换结果会缓存在本地 `cache/` 目录
- 支持收藏、标签、笔记
- 支持文档内容搜索，搜索索引按需加载和保存

## 安装依赖

建议使用 Python 3.10 或更新版本。

```powershell
python -m pip install -r requirements.txt
```

## LibreOffice 配置

Office 文档预览依赖 LibreOffice。PDF、图片、文本和 Markdown 不依赖 LibreOffice。

程序会按以下顺序查找 LibreOffice：

1. `SOFFICE_PATH`：完整 `soffice.exe` 路径
2. `LIBREOFFICE_HOME`：LibreOffice 安装目录
3. 软件目录下的内置目录：`libreoffice/` 或 `LibreOffice/`
4. 系统 `PATH` 中的 `soffice` 或 `soffice.exe`
5. 常见安装路径，例如 `C:\Program Files\LibreOffice`

如果 LibreOffice 安装在自定义路径，可以设置环境变量：

```powershell
$env:SOFFICE_PATH="D:\software\LibreOffice\program\soffice.exe"
```

或：

```powershell
$env:LIBREOFFICE_HOME="D:\software\LibreOffice"
```

如果希望长期生效，可以在 Windows 系统环境变量中配置。

## 启动

```powershell
python server.py --port 8770
```

或双击：

```text
start.bat
```

启动后浏览器会打开：

```text
http://127.0.0.1:8770/
```

## 使用流程

1. 启动程序
2. 在左侧浏览资料目录
3. 点击文件进行预览
4. 如需切换资料根目录，点击左上角“切换”
5. 搜索框回车后进行文档内容搜索

首次打开 Office 文件时需要转换为 PDF，可能较慢；转换完成后会写入 `cache/`，下次打开会直接使用缓存。

## 运行数据

以下文件属于运行数据：

- `config.json`：最近目录和最近文件
- `annotations.json`：收藏、标签、笔记
- `search_index.json`：搜索索引缓存
- `cache/`：Office 转换后的 PDF 缓存

迁移时，建议至少保留：

```text
config.json
annotations.json
```

如果希望迁移后少做转换和索引，也可以一起保留：

```text
cache/
search_index.json
```

## 打包建议

### 推荐：使用打包脚本

正式打包请使用项目提供的脚本（自动包含 `--noconsole`）：

```powershell
# 方式一：PowerShell 直接运行
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1

# 方式二：双击运行（自动调用 PowerShell）
scripts\build_windows.bat
```

首次运行如果提示 PyInstaller 未安装，请先执行：

```powershell
python -m pip install pyinstaller
```

### 手动打包命令（供参考）

```powershell
# 开发调试（显示终端）
pyinstaller `
  --onedir `
  --name "资料浏览器" `
  --icon "assets/app.ico" `
  --add-data "static;static" `
  server.py

# 正式分发（无终端）- 脚本已自动包含这些参数
pyinstaller `
  --onedir `
  --noconsole `
  --name "资料浏览器" `
  --icon "assets/app.ico" `
  --add-data "static;static" `
  server.py
```

### 打包产物结构

```text
dist/资料浏览器/
  资料浏览器.exe      ← 主程序（无终端）
  _internal/         ← 运行时文件
  app_data/          ← 运行数据目录
    config.example.json  ← 配置模板（AI 等配置参考此文件）
```

### 配置文件说明

`app_data/config.example.json` 是配置模板。如需启用 AI 功能，将其复制为 `app_data/config.json` 并填入 key。

**注意**：不要将真实的 `config.json`（包含 API key）打包发布。

### 开发模式 vs 正式模式

| | 开发模式 | 正式打包 |
|---|---------|---------|
| 启动方式 | `python server.py` 或 `start.bat` | 双击 `资料浏览器.exe` |
| 终端窗口 | 显示 | **不显示** |
| 日志文件 | `logs/app.log` | `app_data/logs/app.log` |
| 重复启动 | 可能端口冲突 | 自动复用已有服务 |

### 迁移说明

打包版会把运行数据写入程序目录下的 `app_data/`。迁移到新电脑时，连同 `app_data/` 一起复制即可；如果程序目录不可写，会自动改写到当前用户的本地应用数据目录。

## 系统托盘

正式打包版默认显示系统托盘图标。关闭浏览器页面不等于退出程序，后台服务继续运行。

托盘菜单：

- **打开资料浏览器** — 在浏览器中重新打开应用
- **查看日志** — 打开 `app_data/logs/app.log`
- **打开数据目录** — 打开 `app_data` 文件夹
- **退出程序** — 停止后台服务并退出

如需禁用托盘，可使用 `--no-tray` 参数（仅限命令行启动时）。开发模式（`python server.py`）默认不启用托盘，可用 `--tray` 手动启用。

## 打包 LibreOffice

如需做“完整版”，可以将 LibreOffice 一起放入程序目录：

```text
资料浏览器/
  资料浏览器.exe
  static/
  libreoffice/
    program/
      soffice.exe
```

程序会优先检测 `libreoffice/program/soffice.exe`。注意保留 LibreOffice 的许可证和版权说明文件。

也可以不内置 LibreOffice，让用户自行安装。此时包体更小，维护更简单。
