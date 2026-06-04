<#
.SYNOPSIS
    Build the packaged Windows exe for 资料浏览器.

.DESCRIPTION
    This script builds a reproducible --noconsole PyInstaller package.
    Run from any directory; must be called with -ExecutionPolicy Bypass.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
#>

param(
    [switch]$InstallPyInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- Locate project root ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")

Write-Host "Project root: $ProjectRoot" -ForegroundColor Cyan
Set-Location $ProjectRoot

# --- Check required files ---
$requiredFiles = @(
    "server.py",
    "static",
    "static/favicon.ico",
    "assets/app.ico",
    "config.example.json",
    "README.md"
)

Write-Host "`n[1/6] Checking required files..." -ForegroundColor Yellow
foreach ($f in $requiredFiles) {
    $path = Join-Path $ProjectRoot $f
    if (-not (Test-Path $path)) {
        Write-Host "ERROR: Required file missing: $f" -ForegroundColor Red
        exit 1
    }
    Write-Host "  OK: $f" -ForegroundColor Green
}

# --- Check PyInstaller ---
Write-Host "`n[2/6] Checking PyInstaller..." -ForegroundColor Yellow
if ($InstallPyInstaller) {
    Write-Host "  Installing PyInstaller..." -ForegroundColor Cyan
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: PyInstaller install failed" -ForegroundColor Red; exit 1 }
} else {
    python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: PyInstaller not found." -ForegroundColor Red
        Write-Host "Install it with:" -ForegroundColor Yellow
        Write-Host "  python -m pip install pyinstaller" -ForegroundColor White
        Write-Host "Or run with -InstallPyInstaller:" -ForegroundColor Yellow
        Write-Host "  powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1 -InstallPyInstaller" -ForegroundColor White
        exit 1
    }
    $pyinstVersion = python -m PyInstaller --version
    Write-Host "  OK: PyInstaller $pyinstVersion" -ForegroundColor Green
}

# --- Clean old build artifacts ---
Write-Host "`n[3/6] Cleaning old build artifacts..." -ForegroundColor Yellow
$cleanupTargets = @("build", "dist", "dist_temp")
foreach ($t in $cleanupTargets) {
    if (Test-Path $t) {
        Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue
        Write-Host "  Removed: $t" -ForegroundColor Gray
    }
}

# --- Run PyInstaller to a temp ASCII-named directory ---
Write-Host "`n[4/6] Running PyInstaller (--noconsole)..." -ForegroundColor Yellow

$asciiName = "ziliao_build"
$pyArgs = @(
    "--onedir",
    "--noconsole",
    "--noconfirm",
    "--clean",
    "--name", $asciiName,
    "--icon", "assets/app.ico",
    "--add-data", "static;static",
    "server.py"
)

& python -m PyInstaller @pyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Build completed" -ForegroundColor Green

# --- Use Python for reliable copy/rename to Chinese-named directory ---
Write-Host "`n[5/6] Setting up output directory..." -ForegroundColor Yellow

$pythonCode = @"
import shutil, os, sys
src = r'$ProjectRoot\dist\$asciiName'
dst = r'$ProjectRoot\dist\ziliao'
if os.path.exists(dst):
    shutil.rmtree(dst)
shutil.copytree(src, dst)
ascii_exe = os.path.join(dst, '$asciiName.exe')
chinese_exe = os.path.join(dst, '资料浏览器.exe')
if os.path.exists(ascii_exe):
    os.rename(ascii_exe, chinese_exe)
    print('Renamed: $asciiName.exe -> 资料浏览器.exe')
print('Copied to:', dst)
"@

python -c $pythonCode

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python copy/rename failed" -ForegroundColor Red
    exit 1
}

# --- Create app_data subdirectory and copy config.example.json ---
$appDataDir = Join-Path $ProjectRoot "dist/ziliao/app_data"
if (-not (Test-Path $appDataDir)) {
    New-Item -ItemType Directory -Path $appDataDir -Force | Out-Null
    Write-Host "  Created: app_data/" -ForegroundColor Gray
}

$srcConfig = Join-Path $ProjectRoot "config.example.json"
$dstConfig = Join-Path $appDataDir "config.example.json"
Copy-Item $srcConfig $dstConfig -Force
Write-Host "  Copied: config.example.json -> app_data/" -ForegroundColor Green

$realConfig = Join-Path $appDataDir "config.json"
if (Test-Path $realConfig) {
    Write-Host "  WARNING: Removing real config.json from output" -ForegroundColor Red
    Remove-Item $realConfig -Force
}

# --- Verify output ---
Write-Host "`n[6/6] Verifying build output..." -ForegroundColor Yellow

$dstDir = Join-Path $ProjectRoot "dist/ziliao"
$exePath = Join-Path $dstDir "ziliao.exe"
$internalDir = Join-Path $dstDir "_internal"
$staticInInternal = Join-Path $internalDir "static"
$staticInRoot = Join-Path $dstDir "static"

$results = @{
    "exe exists"            = (Test-Path $exePath)
    "_internal exists"       = (Test-Path $internalDir)
    "app_data exists"       = (Test-Path $appDataDir)
    "config.example copied"  = (Test-Path $dstConfig)
    "static bundled"        = ((Test-Path $staticInInternal) -or (Test-Path $staticInRoot))
    "real config.json copied" = (Test-Path $realConfig)
}

# For "real config.json copied", false is GOOD (means we did not leak it)
$allOk = $true
foreach ($key in $results.Keys) {
    $val = $results[$key]
    if ($key -eq "real config.json copied") {
        # For this key, false = good (no leak), true = bad (leaked)
        $color = if ($val) { "Red" } else { "Green" }
        $statusStr = if ($val) { "true (BAD - leaked!)" } else { "false (good - not leaked)" }
        if ($val) { $allOk = $false }
    } else {
        $color = if ($val) { "Green" } else { "Red" }
        $statusStr = if ($val) { "true" } else { "false" }
        if (-not $val) { $allOk = $false }
    }
    Write-Host ("  {0}: {1}" -f $key, $statusStr) -ForegroundColor $color
}

Write-Host "`nBuild result:" -ForegroundColor Cyan
foreach ($key in $results.Keys) {
    if ($key -eq "real config.json copied") {
        Write-Host ("  - {0}: {1}" -f $key, $(if ($results[$key]) { "true" } else { "false" }))
    } else {
        Write-Host ("  - {0}: {1}" -f $key, $(if ($results[$key]) { "true" } else { "false" }))
    }
}

if (-not $allOk) {
    Write-Host "`nERROR: Build verification failed" -ForegroundColor Red
    exit 1
}

Write-Host "`nBuild complete! Output: dist/ziliao/" -ForegroundColor Cyan
Write-Host "Rename 'ziliao' to Chinese name manually if desired." -ForegroundColor Gray
Write-Host "Next: distribute the 'dist/ziliao/' directory." -ForegroundColor Gray
