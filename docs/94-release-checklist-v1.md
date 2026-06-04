# Release Checklist V1 — 资料浏览器 0.1.0

```
product_name:     资料浏览器
app_version:      0.1.0
release_baseline:  Release Baseline V1
target_platform:  Windows
runtime_shape:    本地后台服务 + 浏览器 UI + 系统托盘
```

---

## 1. 基线信息

| 字段 | 值 |
|------|-----|
| product_name | 资料浏览器 |
| app_version | 0.1.0 |
| release_baseline | Release Baseline V1 |
| target_platform | Windows |
| runtime_shape | 本地后台服务 + 浏览器 UI + 系统托盘 |
| branch | main |

---

## 2. 发布前 Git 检查

```bash
git status -sb
git pull --ff-only origin main
git log --oneline --decorate -10
```

**检查点：**

```
[ ] 工作区干净（无未提交更改）
[ ] 当前分支 main
[ ] 远端已同步 origin/main
[ ] 无 dist/build/release_packages/zip/exe/config/API key
```

---

## 3. 静态检查

```bash
python -m compileall .
```

**文本健康检查：**

```bash
python - <<'PY'
from pathlib import Path

targets = [
    "README.md",
    "scripts/package_release_zip.ps1",
    "scripts/_package_zip.py",
    "server.py",
    "static/app.js",
    "app_metadata.py",
]
for p in targets:
    b = Path(p).read_bytes()
    assert b.count(b"\x00") == 0, f"NUL bytes in {p}"
    s = b.decode("utf-8-sig")
    assert "<placeholder>" not in s, f"Placeholder in {p}"
print("TEXT_HEALTH_PASS")
PY
```

**检查点：**

```
[ ] 所有目标文件 UTF-8 可读
[ ] 无 NUL 字节
[ ] 无 ??? 乱码占位符
[ ] 无编译错误
```

---

## 4. 版本检查

```bash
python - <<'PY'
from app_metadata import APP_ID, APP_NAME, APP_VERSION, RELEASE_BASELINE
print(APP_ID, APP_NAME, APP_VERSION, RELEASE_BASELINE)
assert APP_VERSION == "0.1.0", f"Wrong version: {APP_VERSION}"
PY
```

```bash
# 同时验证 API
python server.py --port 8770 --no-browser --no-tray &
sleep 3
curl http://127.0.0.1:8770/api/version
# 期望: {"app_id":"file_read_on_web","app_name":"资料浏览器","version":"0.1.0",...}
curl -X POST http://127.0.0.1:8770/api/shutdown
```

**检查点：**

```
[ ] APP_VERSION == "0.1.0"
[ ] /api/version 返回正确版本
[ ] 启动日志包含 version: 0.1.0
[ ] README 版本一致
[ ] zip 文件名版本一致
```

---

## 5. 打包检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
```

**检查点：**

```
[ ] dist/资料浏览器/资料浏览器.exe 存在
[ ] dist/资料浏览器/_internal/ 存在
[ ] dist/资料浏览器/app_data/config.example.json 存在
[ ] dist/资料浏览器/app_data/config.json 不存在
[ ] dist/资料浏览器/resource_browser_build.exe 不存在
[ ] 无旧 ziliao / ziliao_build 输出
```

---

## 6. 发布 zip 检查

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package_release_zip.ps1
```

**检查点：**

```
[ ] release_packages/资料浏览器-v0.1.0-windows-YYYYMMDD.zip 存在
[ ] ZIP_VERIFY_PASS 输出
[ ] zip 顶层目录是 资料浏览器/
[ ] zip 包含 资料浏览器.exe
[ ] zip 包含 _internal/
[ ] zip 包含 app_data/config.example.json
[ ] zip 不包含 app_data/config.json
[ ] zip 不包含 state.json / annotations.json / search_index.json
[ ] zip 不包含 logs/ / cache/
[ ] zip 不包含 resource_browser_build.exe
[ ] zip 不包含旧名 ziliao / ziliao_build
```

---

## 7. 解压启动检查

将 zip 解压到仓库外目录，例如 `D:\tmp\资料浏览器_release_test`。

```
[ ] 解压后存在 资料浏览器/资料浏览器.exe
[ ] app_data/config.example.json 存在
[ ] app_data/config.json 不存在
[ ] 双击 exe 无终端窗口
[ ] 默认浏览器打开 http://127.0.0.1:8770/
[ ] 系统托盘显示资料浏览器图标
[ ] /api/version 返回 "0.1.0"
```

---

## 8. 核心功能 Smoke Test

```
[ ] 无 root 状态正常（提示选择目录）
[ ] 点击"切换"可选择资料目录
[ ] 文件树正常加载
[ ] Markdown / Text 预览正常
[ ] PDF 预览正常
[ ] 图片预览正常
[ ] Office 预览正常（LibreOffice 可用时）
[ ] 搜索正常（关键词搜索可返回结果）
[ ] 收藏功能正常
[ ] 标签功能正常
[ ] 笔记功能正常
[ ] "打开位置"正常（资源管理器打开）
[ ] "下载"正常
[ ] AI 未配置状态友好提示
```

---

## 9. 生命周期检查

```
[ ] 重复双击 exe 不启动第二个长期服务
[ ] 重复双击 exe 会打开已有浏览器页面
[ ] 关闭浏览器后服务仍在，托盘仍在
[ ] 托盘"打开资料浏览器"可用
[ ] 托盘"查看日志"可用
[ ] 托盘"打开数据目录"可用
[ ] 托盘"退出程序"可用
[ ] 页面"退出"可用
[ ] 退出后 /api/health 不可访问
[ ] 退出后托盘消失
```

---

## 10. 日志检查

```
[ ] app_data/logs/app.log 存在
[ ] 日志包含 app_dir / data / config / root 信息
[ ] 日志包含 version: 0.1.0
[ ] 日志包含 release_baseline: Release Baseline V1
[ ] 日志无明显 ERROR 级别错误
[ ] 日志无 API key 泄漏
```

---

## 11. 发布包安全检查

```
[ ] zip 中无 config.json
[ ] zip 中无 API key
[ ] zip 中无 logs/ cache/
[ ] zip 中无用户测试资料
[ ] Git 中无 release_packages/
[ ] Git 中无 *.zip
[ ] Git 中无 dist/ build/ *.exe
[ ] Git 中无 config.json
```

---

## 12. 发布判定

**Decision: PASS / FAIL**

### PASS 条件（全部满足）

```
[ ] 所有阻塞项（Git、静态、版本、打包、zip）通过
[ ] zip 可解压启动
[ ] /api/version 返回 0.1.0
[ ] config.json / API key 未进入发布包
[ ] 核心预览 / 搜索 / 收藏 / 标签 / 笔记链路正常
[ ] 退出和托盘生命周期正常
```

### FAIL 条件（任一满足）

```
[ ] 打包失败
[ ] zip 内容错误或损坏
[ ] exe 无法启动
[ ] config.json / API key 泄漏到发布包
[ ] 预览 / 搜索 / 收藏 / 标签 / 笔记核心链路失败
[ ] 退出或托盘不可用
```

---

## 快速执行脚本

```powershell
# 完整发布前检查（不含 GUI 验证）
powershell -ExecutionPolicy Bypass -File scripts/package_release_zip.ps1
python - <<'PY'
from pathlib import Path
import zipfile, sys

# 1. 静态检查
for p in ["README.md","server.py","app_metadata.py","static/app.js"]:
    assert Path(p).exists(), f"Missing: {p}"

# 2. 版本检查
from app_metadata import APP_VERSION
assert APP_VERSION == "0.1.0", f"Wrong version: {APP_VERSION}"

# 3. zip 内容检查
zips = sorted(Path("release_packages").glob("资料浏览器-v0.1.0-windows-*.zip"))
assert zips, "No release zip found"
zp = zips[-1]
with zipfile.ZipFile(zp) as z:
    names = z.namelist()
assert "资料浏览器/资料浏览器.exe" in names
assert "资料浏览器/app_data/config.example.json" in names
assert "资料浏览器/app_data/config.json" not in names
assert not any("/logs/" in n or "/cache/" in n for n in names)
print("QUICK_CHECK_PASS")
PY
```
