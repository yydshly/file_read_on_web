"""Package a release directory into a versioned zip for distribution.

Usage:
    python scripts/_package_zip.py --release-dir "dist/资料浏览器" --out "release_packages/资料浏览器-v0.1.0-windows-20260604.zip"

Verifies required structure before zipping and validates contents after.
Exits non-zero on any error.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


def _verify_release_dir(release_dir: Path) -> None:
    """Check that the release directory has the expected structure."""
    errors: list[str] = []

    exe = release_dir / "资料浏览器.exe"
    if not exe.exists():
        errors.append(f"missing: {exe}")

    internal_dir = release_dir / "_internal"
    if not internal_dir.exists():
        errors.append(f"missing: {internal_dir}")

    config_example = release_dir / "app_data" / "config.example.json"
    if not config_example.exists():
        errors.append(f"missing: {config_example}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"  release dir verified: {release_dir}")


def _zip_directory(source_dir: Path, output_zip: Path) -> None:
    """Create a zip with the correct top-level folder structure."""
    # Top-level folder name = source directory name
    top_level = source_dir.name  # e.g. "资料浏览器"

    output_zip.parent.mkdir(parents=True, exist_ok=True)

    # Patterns to exclude from the zip
    EXCLUDE_NAMES = {
        # User runtime data
        "config.json",
        "state.json",
        "annotations.json",
        "search_index.json",
        # Cache and logs
        "logs",
        "cache",
    }
    EXCLUDE_STEMS = {"ziliao", "ziliao_build", "resource_browser_build"}

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in source_dir.rglob("*"):
            if not file_path.is_file():
                continue

            rel = file_path.relative_to(source_dir)  # e.g. app_data/config.json

            # Check each path component
            parts = rel.parts
            if any(part in EXCLUDE_NAMES for part in parts):
                continue
            # Check for forbidden name stems
            name_lower = str(rel).lower()
            if any(stem in name_lower for stem in EXCLUDE_STEMS):
                continue
            # Skip .pyc and __pycache__
            if ".pyc" in name_lower or "__pycache__" in name_lower:
                continue
            # Skip .log files
            if rel.suffix == ".log":
                continue

            # Target path inside zip: <top_level>/<relative_path>
            arcname = f"{top_level}/{rel.as_posix()}"
            zf.write(file_path, arcname)

    print(f"  zip created: {output_zip} ({output_zip.stat().st_size:,} bytes)")


def _verify_zip(output_zip: Path, release_dir: Path) -> None:
    """Re-open the zip and verify its contents."""
    errors: list[str] = []
    warnings: list[str] = []

    with zipfile.ZipFile(output_zip) as zf:
        names = zf.namelist()
        top_level = release_dir.name + "/"

        # Must have the top-level folder
        has_top = any(n.startswith(top_level) for n in names)
        if not has_top:
            errors.append(f"zip has no top-level folder '{top_level}'")

        required = [
            f"{top_level}资料浏览器.exe",
            f"{top_level}app_data/config.example.json",
        ]
        for r in required:
            if r not in names:
                errors.append(f"missing required: {r}")

        # Check _internal exists
        if not any(n.startswith(f"{top_level}_internal/") for n in names):
            errors.append("missing _internal/ files")

        forbidden = [
            f"{top_level}app_data/config.json",
            f"{top_level}app_data/state.json",
            f"{top_level}app_data/annotations.json",
            f"{top_level}app_data/search_index.json",
            f"{top_level}app_data/logs/",
            f"{top_level}app_data/cache/",
            "resource_browser_build.exe",
        ]
        for f in forbidden:
            if f.rstrip("/") in names or any(f.rstrip("/") in n for n in names):
                errors.append(f"forbidden file present: {f}")

        if any("/logs/" in n for n in names):
            errors.append("logs directory included")
        if any("/cache/" in n for n in names):
            errors.append("cache directory included")

        old_names = ["ziliao", "ziliao_build"]
        for old in old_names:
            if any(old.lower() in n.lower() for n in names):
                errors.append(f"old project name '{old}' found in zip")

    if errors:
        print("ERRORS:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print("  zip verified OK")
    print("ZIP_VERIFY_PASS")


def main() -> None:
    parser = argparse.ArgumentParser(description="Package a release directory into a zip.")
    parser.add_argument("--release-dir", required=True, help="Path to the release directory (e.g. dist/资料浏览器)")
    parser.add_argument("--out", required=True, help="Output zip path")
    args = parser.parse_args()

    release_dir = Path(args.release_dir).resolve()
    output_zip = Path(args.out).resolve()

    print(f"Packaging release: {release_dir}")
    print(f"Output zip: {output_zip}")

    _verify_release_dir(release_dir)
    _zip_directory(release_dir, output_zip)
    _verify_zip(output_zip, release_dir)


if __name__ == "__main__":
    main()
