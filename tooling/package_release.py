#!/usr/bin/env python3
"""
Package the current generated game source into a release archive.

Produces a platform-independent source archive that users can build with
`cargo build --release`. Includes Cargo.lock for reproducibility
(see Decision 18 in work/decisions.md).

Example:
    python tooling/package_release.py --version 2026.01
"""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

REPO_ROOT = Path(__file__).resolve().parents[1]
GAME_DIR = REPO_ROOT / "generated" / "game"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"

EXCLUDED_DIRS = {"target", ".git", "__pycache__"}
EXCLUDED_FILES = {".DS_Store", ".gitkeep"}


def collect_game_sources() -> list[Path]:
    if not GAME_DIR.is_dir():
        raise SystemExit(f"Generated game directory not found: {GAME_DIR}")

    paths: list[Path] = []
    for path in sorted(GAME_DIR.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.relative_to(GAME_DIR).parts):
            continue
        if path.name in EXCLUDED_FILES:
            continue
        paths.append(path)
    return paths


def package(version: str, extras: list[Path]) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    zip_name = f"worldsmith-game-{version}-src.zip"
    zip_path = ARTIFACTS_DIR / zip_name

    if zip_path.exists():
        zip_path.unlink()

    arc_root = f"worldsmith-game-{version}"

    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as archive:
        for source in collect_game_sources():
            arcname = f"{arc_root}/{source.relative_to(GAME_DIR)}"
            archive.write(source, arcname=arcname)
        archive.write(REPO_ROOT / "LICENSE", arcname=f"{arc_root}/LICENSE")
        for extra in extras:
            if not extra.exists():
                raise SystemExit(f"Extra include not found: {extra}")
            arcname = f"{arc_root}/{extra.relative_to(REPO_ROOT)}"
            archive.write(extra, arcname=arcname)

    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package worldsmith source release artifact.")
    parser.add_argument(
        "--version",
        required=True,
        help="Tag name following the yyyy.vv scheme (e.g., 2026.01).",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        default=[],
        help="Additional files to include, relative to the repo root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extras = [REPO_ROOT / rel for rel in args.include]
    zip_path = package(args.version, extras)
    print(f"Release artifact created: {zip_path}")


if __name__ == "__main__":
    main()
