# 83. PACKAGED-BUILD-SCRIPT-V1

**Date**: 2026-06-04
**Task**: PACKAGED-BUILD-SCRIPT-V1
**Decision**: ✅ PASS

---

## 摘要

新增 `scripts/build_windows.ps1` 一键打包脚本，固化 PyInstaller 打包流程，确保每次打包使用一致的 `--noconsole` 参数，并自动设置 `app_data/config.example.json`。

---

## 实现的变更

### 1. scripts/build_windows.ps1

主打包脚本，实现以下功能：

| 步骤 | 功能 |
|------|------|
| 1/6 | 检查必要文件（server.py, static/, assets/app.ico, config.example.json） |
| 2/6 | 检查 PyInstaller 是否可用，支持 `-InstallPyInstaller` 参数 |
| 3/6 | 清理 `build/` 和 `dist/` |
| 4/6 | 执行 PyInstaller（`--onedir --noconsole --noconfirm --clean`） |
| 5/6 | 使用 Python 可靠复制/重命名到中文目录 `dist/ziliao`，并复制 `config.example.json` |
| 6/6 | 验证所有关键产物，报告结果 |

关键设计：
- 使用 ASCII 中间名 `ziliao_build` 避免 PowerShell 的中文路径问题
- 使用 Python `shutil.copytree` 可靠复制目录结构
- exe 重命名为 `资料浏览器.exe`
- 输出目录：`dist/ziliao/`

### 2. scripts/build_windows.bat

双击入口脚本，仅调用 PowerShell 脚本，不含复杂逻辑。

### 3. README.md 更新

- 优先推荐使用 `scripts/build_windows.ps1`
- 说明开发模式 vs 正式模式区别
- 说明配置文件处理
- 保留手动打包命令供参考

---

## 打包产物结构

```
dist/ziliao/
  资料浏览器.exe      ← 主程序（无终端）
  _internal/        ← Python 运行时
  app_data/          ← 运行数据目录
    config.example.json  ← 配置模板
```

---

## 验证结果

| 检查项 | 状态 |
|--------|------|
| PyInstaller 检查 | ✅ |
| build 清理 | ✅ |
| dist 清理 | ✅ |
| `--noconsole` 参数 | ✅ |
| `--icon assets/app.ico` | ✅ |
| `--add-data static;static` | ✅ |
| exe 生成 | ✅ |
| `_internal/` 生成 | ✅ |
| `app_data/` 生成 | ✅ |
| `config.example.json` 复制 | ✅ |
| `config.json` 未泄露 | ✅ |
| static 资源打包 | ✅ |
| exe 启动（无终端） | ✅ |
| `/api/health` 返回 app_id | ✅ |
| `/favicon.ico` 返回 200 | ✅ |
| 重复启动复用 | ✅ |
| Shutdown 关闭服务 | ✅ |

---

## 稳定性确认

| 检查项 | 状态 |
|--------|------|
| server.py 未变 | ✅ |
| 启动逻辑未变 | ✅ |
| shutdown 未变 | ✅ |
| favicon 逻辑未变 | ✅ |
| root 逻辑未变 | ✅ |
| preview 逻辑未变 | ✅ |
| Office 转换未变 | ✅ |
| AI provider 未变 | ✅ |
| annotations 未变 | ✅ |
| 无新增依赖 | ✅ |

---

## 结论

**✅ PASS** - 脚本可用于正式打包发布
