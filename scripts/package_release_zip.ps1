<#
.SYNOPSIS
    Build and package the release zip for the file browser app.

    1. Runs scripts/build_windows.ps1 to produce dist/file_browser/
    2. Reads APP_VERSION from app_metadata.py
    3. Stamps the zip with the current date (YYYYMMDD)
    4. Produces release_packages/file_browser-v<VERSION>-windows-<DATE>.zip
    5. Verifies the zip contents

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/package_release_zip.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $ProjectRoot

Write-Host "== Release ZIP package ==" -ForegroundColor Cyan

# Step 1: Build the release directory
& powershell -ExecutionPolicy Bypass -File "scripts/build_windows.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: build_windows.ps1 failed" -ForegroundColor Red
    exit 1
}

# Step 2: Read APP_VERSION from app_metadata.py
$AppVersion = python -c "from app_metadata import APP_VERSION; print(APP_VERSION)"
if (-not $AppVersion) {
    Write-Host "ERROR: APP_VERSION was empty" -ForegroundColor Red
    exit 1
}
Write-Host ("  App version: {0}" -f $AppVersion) -ForegroundColor Green

# Step 3: Determine output paths
$DateStamp = Get-Date -Format "yyyyMMdd"
$OutDir = Join-Path $ProjectRoot "release_packages"
$ZipName = ("file_browser-v{0}-windows-{1}.zip" -f $AppVersion, $DateStamp)
$ZipPath = Join-Path $OutDir $ZipName

Write-Host ("  Output: {0}" -f $OutDir) -ForegroundColor Green
Write-Host ("  Zip name: {0}" -f $ZipName) -ForegroundColor Green

# Step 4: Package with the Python helper
python "scripts/_package_zip.py" --release-dir "dist/资料浏览器" --out $ZipPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: _package_zip.py failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Release package created successfully" -ForegroundColor Cyan
