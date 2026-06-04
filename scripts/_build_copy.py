"""Helper for build_windows.ps1: copy and rename build output.

Uses shutil.copytree with dirs_exist_ok=True to handle locked directories
(Windows Defender can hold a lock on the directory without blocking file overwrites).
The Chinese product name is hardcoded here to avoid PowerShell CJK encoding bugs.
"""
import shutil
import os
import sys

PROJECT_ROOT = sys.argv[1]
INTERNAL_NAME = sys.argv[2]   # e.g. "resource_browser_build"

# Hardcoded Chinese product name - avoids PowerShell CJK string encoding issues.
PRODUCT_NAME = "资料浏览器"


def copy_rename():
    src = os.path.join(PROJECT_ROOT, "dist", INTERNAL_NAME)
    dst = os.path.join(PROJECT_ROOT, "dist", PRODUCT_NAME)

    if not os.path.exists(src):
        raise RuntimeError(f"Build source not found: {src}")

    # Copy into existing directory using dirs_exist_ok (works even when
    # the destination directory is locked by Windows Defender).
    # We overwrite files in-place so the result always matches the latest build.
    shutil.copytree(src, dst, dirs_exist_ok=True)

    ascii_exe = os.path.join(dst, f"{INTERNAL_NAME}.exe")
    product_exe = os.path.join(dst, f"{PRODUCT_NAME}.exe")
    if os.path.exists(ascii_exe):
        os.rename(ascii_exe, product_exe)
        print(f"Renamed: {INTERNAL_NAME}.exe -> {PRODUCT_NAME}.exe", flush=True)

    print(f"Output: {dst}", flush=True)
    print(PRODUCT_NAME, flush=True)  # Last line: PowerShell captures this


if __name__ == "__main__":
    copy_rename()
