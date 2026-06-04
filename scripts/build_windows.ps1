<#
.SYNOPSIS
    Build the packaged Windows exe for the file browser app.
.DESCRIPTION
    Builds a reproducible --noconsole PyInstaller package.
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

# Internal ASCII name: avoids PyInstaller + non-ASCII path issues.
# Final published output uses the Chinese name (managed by Python helper).
$internalName = "resource_browser_build"

$pyArgs = @(
    "--onedir",
    "--noconsole",
    "--noconfirm",
    "--clean",
    "--name", $internalName,
    "--icon", "assets/app.ico",
    "--add-data", "static;static",
    "--hidden-import", "pystray._win32",
    "--hidden-import", "PIL.Image",
    "--hidden-import", "PIL.ImageDraw",
    "server.py"
)

& python -m PyInstaller @pyArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Build completed" -ForegroundColor Green

# --- Use Python helper for copy/rename to Chinese-named directory ---
Write-Host "`n[5/6] Setting up output directory..." -ForegroundColor Yellow

# Python helper has the Chinese name hardcoded internally, prints it as last line.
# PowerShell captures stdout; take the last non-empty line to get the product name.
$output = & python (Join-Path $ScriptDir "_build_copy.py") $ProjectRoot $internalName
$lines = @($output -split "`n" | Where-Object { $_ -and $_.Trim() })
if ($lines.Count -eq 0) {
    Write-Host "ERROR: Python helper produced no output" -ForegroundColor Red
    exit 1
}
$productName = $lines[-1].Trim()
if (-not $productName) {
    Write-Host "ERROR: Python helper did not return product name" -ForegroundColor Red
    exit 1
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Python copy/rename failed" -ForegroundColor Red
    exit 1
}

# Remove the internal build directory now that we have copied
$internalBuiltDir = Join-Path $ProjectRoot "dist\$internalName"
if (Test-Path $internalBuiltDir) {
    Remove-Item -Recurse -Force $internalBuiltDir
    Write-Host "  Cleaned up internal build dir: $internalName" -ForegroundColor Gray
}

# --- Create app_data subdirectory and copy config.example.json ---
$appDataDir = Join-Path $ProjectRoot "dist\$productName\app_data"
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

$releaseDir = Join-Path $ProjectRoot "dist\$productName"
$exePath    = Join-Path $releaseDir "$productName.exe"
$internalDir = Join-Path $releaseDir "_internal"
$staticInInternal = Join-Path $internalDir "static"
$staticInRoot = Join-Path $releaseDir "static"

$results = @{
    "release dir exists"           = (Test-Path $releaseDir)
    "exe exists"                   = (Test-Path $exePath)
    "_internal exists"             = (Test-Path $internalDir)
    "app_data exists"              = (Test-Path $appDataDir)
    "config.example copied"        = (Test-Path $dstConfig)
    "static bundled"               = ((Test-Path $staticInInternal) -or (Test-Path $staticInRoot))
    "real config.json excluded"    = -not (Test-Path $realConfig)
    "no internal exe leaked"       = -not (Test-Path (Join-Path $releaseDir "$internalName.exe"))
}

$allOk = $true
foreach ($key in $results.Keys) {
    $val = $results[$key]
    $color = if ($val) { "Green" } else { "Red" }
    $statusStr = if ($val) { "OK" } else { "FAIL" }
    if (-not $val) { $allOk = $false }
    Write-Host ("  {0}: {1}" -f $key, $statusStr) -ForegroundColor $color
}

if (-not $allOk) {
    Write-Host "`nERROR: Build verification failed" -ForegroundColor Red
    exit 1
}

Write-Host "`nBuild complete! Output: dist\$productName\" -ForegroundColor Cyan
Write-Host "Start: dist\$productName\$productName.exe" -ForegroundColor Cyan
