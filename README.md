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

第一版建议使用 PyInstaller 的目录模式：

```powershell
python -m pip install pyinstaller

pyinstaller `
  --onedir `
  --name "资料浏览器" `
  --add-data "static;static" `
  server.py
```

生成目录：

```text
dist/资料浏览器/
```

可以将该目录压缩后分发给用户。

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
