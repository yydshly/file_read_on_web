# Packaging Spec Files

This directory contains PyInstaller packaging configurations for the application.

## Canonical Build Entry Point

**`scripts/build_windows.ps1`** is the recommended build entrypoint.

It runs PyInstaller with the correct `--add-data src/frontend/static` path and produces a properly named output in `dist/`.

## Spec File Roles

| Spec File | Role | Canonical? | Notes |
|---|---|---|---|
| `resource_browser_build.spec` | Primary ASCII-named spec used by build script | Yes | Produces internal build dir; final output renamed by Python helper |
| `ziliao.spec` | Alternate config with console=False | No | Legacy/reference; not used by build script |
| `ziliao_build.spec` | Alternate config with console=False | No | Legacy/reference; not used by build script |
| `资料浏览器.spec` | Chinese-named alternate config | No | Legacy/reference; not used by build script |
| `资料浏览器_noconsole.spec` | Chinese-named alternate config | No | Legacy/reference; not used by build script |

## All Specs Include

All specs include the required runtime hidden imports for tray/icon support:
- `pystray._win32`
- `PIL.Image`
- `PIL.ImageDraw`

## Why Track Specs Despite `*.spec` in `.gitignore`?

`.gitignore` contains `*.spec` to ignore auto-generated PyInstaller spec files that may appear at the repo root during development. The `!packaging/*.spec` negation ensures curated packaging configs in this directory are tracked.

## Static Assets Path

All specs reference `src/frontend/static` for the `--add-data` / `datas` path. This must remain consistent with `server.py`'s `STATIC_DIR = RESOURCE_DIR / "src" / "frontend" / "static"`.
