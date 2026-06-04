@echo off
REM Build script wrapper for 资料浏览器
REM Double-click to run, or run from command line.
REM Requires PowerShell (available by default on Windows 10/11).

setlocal
cd /d "%~dp0.."

echo.
echo ========================================
echo   资料浏览器 - Windows 打包脚本
echo ========================================
echo.
echo Running PowerShell build script...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"

echo.
if %ERRORLEVEL% neq 0 (
    echo Build failed. Press any key to exit.
    pause >nul
) else (
    echo Build succeeded. Press any key to exit.
    pause >nul
)

endlocal
