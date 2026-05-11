#!/usr/bin/env python3
"""
Readability drift-detector for texture images.

Scores each image on three orthogonal metrics computed at a small target
size (default 64x64) chosen to match in-game wall sampling density:

- edge_retention      mean edge intensity after downscale/upscale, divided
                      by the same measure on the original. Captures whether
                      silhouettes survive small-texture sampling.
- contrast_preservation  luminance stddev preserved through the same
                      downscale roundtrip. Captures whether tonal range
                      collapses at the target size.
- color_complexity    count of distinct colours in a median-cut quantize
                      capped at --quantize-cap (default 256). Cap is
                      deliberately decoupled from the constitution's
                      palette threshold N to keep the metric independent.

Output is a JSON array with one record per image. For successfully scored
images, `passed` is null and `violations` is empty until thresholds are
calibrated against a corpus. Unreadable inputs (corrupt, truncated, or
oversized) emit `passed: false` and a single `violations` entry naming the
underlying exception, so a directory of broken files is not confused with
an empty one.

Usage:

    python3 tooling/texture_evals/readability.py <path-or-dir>
    python3 tooling/texture_evals/readability.py <dir> --out report.json
    python3 tooling/texture_evals/readability.py <file> --target-size 64

Exit codes:
    0  success (one or more records emitted, or empty input)
    2  usage error / path not found
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tga"}
ZERO_EPS = 1e-6


def collect_images(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
        )
    raise FileNotFoundError(root)


def downscale_roundtrip(image: Image.Image, target_size: int) -> Image.Image:
    original_size = image.size
    small = image.resize((target_size, target_size), Image.Resampling.NEAREST)
    return small.resize(original_size, Image.Resampling.NEAREST)


def edge_mean(luminance: Image.Image) -> float:
    # FIND_EDGES leaves a 1-pixel artifact ring at the image border that biases
    # the mean upward on otherwise-flat images. Crop it off. Images smaller
    # than 3x3 have no interior pixels left after cropping, and no meaningful
    # edge content to begin with -- return 0.0 directly so a 2x2 solid square
    # doesn't masquerade as having perfect edge retention.
    w, h = luminance.size
    if w < 3 or h < 3:
        return 0.0
    edges = luminance.filter(ImageFilter.FIND_EDGES)
    edges = edges.crop((1, 1, w - 1, h - 1))
    return float(ImageStat.Stat(edges).mean[0])


def edge_retention(luminance: Image.Image, roundtrip_luminance: Image.Image) -> float:
    original_mean = edge_mean(luminance)
    if original_mean <= ZERO_EPS:
        return 0.0
    return edge_mean(roundtrip_luminance) / original_mean


def contrast_preservation(luminance: Image.Image, roundtrip_luminance: Image.Image) -> float:
    original_stddev = float(ImageStat.Stat(luminance).stddev[0])
    if original_stddev <= ZERO_EPS:
        return 0.0
    return float(ImageStat.Stat(roundtrip_luminance).stddev[0]) / original_stddev


def color_complexity(rgb: Image.Image, target_size: int, quantize_cap: int) -> int:
    small = rgb.resize((target_size, target_size), Image.Resampling.NEAREST)
    quantized = small.quantize(colors=quantize_cap, method=Image.Quantize.MEDIANCUT)
    colors = quantized.getcolors() or []
    return len(colors)


def _texture_name(path: Path, input_root: Path) -> str:
    if input_root.is_dir():
        return str(path.relative_to(input_root)).replace("\\", "/")
    return path.name


def score_image(path: Path, input_root: Path, target_size: int, quantize_cap: int) -> dict:
    try:
        with Image.open(path) as img:
            img.load()
            rgb = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        # Corrupt, truncated, or oversized images shouldn't abort the entire
        # scan. DecompressionBombError is a direct Exception subclass (not
        # OSError) so it has to be listed explicitly. The README contract is
        # one record per image -- dropping unreadable inputs would make a
        # directory of corrupt files indistinguishable from an empty one.
        # The passed=null/violations=[] rule in identity.md is the
        # pre-calibration default for successfully scored images; an I/O
        # failure is a different category and emits passed=false with the
        # error in violations.
        return {
            "texture": _texture_name(path, input_root),
            "passed": False,
            "scores": {},
            "violations": [f"unreadable: {type(exc).__name__}: {exc}"],
        }

    luminance = rgb.convert("L")
    roundtrip = downscale_roundtrip(rgb, target_size)
    roundtrip_luminance = roundtrip.convert("L")

    er = edge_retention(luminance, roundtrip_luminance)
    cp = contrast_preservation(luminance, roundtrip_luminance)
    cc = color_complexity(rgb, target_size, quantize_cap)

    return {
        "texture": _texture_name(path, input_root),
        "passed": None,
        "scores": {
            "edge_retention": round(er, 4),
            "contrast_preservation": round(cp, 4),
            "color_complexity": cc,
        },
        "violations": [],
    }


def run(input_path: Path, out_path: Optional[Path], target_size: int, quantize_cap: int) -> int:
    images = collect_images(input_path)
    records = [
        score_image(p, input_path, target_size, quantize_cap)
        for p in images
    ]
    payload = json.dumps(records, indent=2)
    if out_path is None:
        print(payload)
    else:
        out_path.write_text(payload + "\n", encoding="utf-8")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Texture readability drift-detector.")
    parser.add_argument("input", help="Image file or directory of images.")
    parser.add_argument("--out", help="Write JSON to this file instead of stdout.")
    parser.add_argument("--target-size", type=int, default=64,
                        help="Downscale target dimension in pixels (default 64).")
    parser.add_argument("--quantize-cap", type=int, default=256,
                        help="Max colours in median-cut quantize (default 256).")
    args = parser.parse_args(argv)

    if args.target_size <= 0:
        parser.error("--target-size must be > 0")
    if not 1 <= args.quantize_cap <= 256:
        parser.error("--quantize-cap must be in [1, 256]")

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"error: path not found: {input_path}", file=sys.stderr)
        return 2

    out_path = Path(args.out) if args.out else None
    return run(input_path, out_path, args.target_size, args.quantize_cap)


if __name__ == "__main__":
    sys.exit(main())
