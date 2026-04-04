#!/usr/bin/env python3
"""
Package the current generated game into a zipped release artifact.

Example:
    python tooling/package_release.py --version v0.2
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

REPO_ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = REPO_ROOT / "generated" / "game"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"


def run_cargo_build() -> None:
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=GAME_DIR,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("cargo build --release failed.")


def resolve_binary() -> Path:
    bin_name = "worldsmith-game.exe" if platform.system() == "Windows" else "worldsmith-game"
    path = GAME_DIR / "target" / "release" / bin_name
    if not path.exists():
        raise SystemExit(f"Expected binary not found: {path}")
    return path


def package(version: str, include: list[Path]) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    platform_tag = platform.system().lower()
    zip_name = f"worldsmith-game-{version}-{platform_tag}.zip"
    zip_path = ARTIFACTS_DIR / zip_name

    if zip_path.exists():
        zip_path.unlink()

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        binary = resolve_binary()
        archive.write(binary, arcname=binary.name)
        for extra in include:
            if extra.exists():
                archive.write(extra, arcname=extra.relative_to(REPO_ROOT))

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package worldsmith release artifact.")
    parser.add_argument("--version", required=True, help="Version/tag name (e.g., v0.2).")
    parser.add_argument(
        "--include",
        nargs="*",
        default=[],
        help="Additional files to include (paths relative to repo root).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    include_paths = [
        GAME_DIR / "README.md",
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "README.md",
        REPO_ROOT / "work" / f"generation_report_{args.version}.md",
        REPO_ROOT / "work" / f"pipeline_run_{args.version}.md",
    ]
    include_paths.extend(REPO_ROOT / rel for rel in args.include)

    run_cargo_build()
    zip_path = package(args.version, include_paths)

    print(f"Release artifact created: {zip_path}")


if __name__ == "__main__":
    main()
