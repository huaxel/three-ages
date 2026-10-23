#!/usr/bin/env python3
"""Build a Colab-sized training pack: 256px JPEGs mirroring the corpus layout.

The fine-tuning model sees 224px inputs, so full-resolution files only waste
upload bandwidth and Colab disk. Output keeps the image-root/building/file
layout, so train_contrastive.py runs unchanged against --image-root PACK/pub.
Prints a file count + byte total for the Drive upload at the end.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[2] / 'local' / 'training'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from epoch_data import load_manifest  # noqa: E402

LONG_EDGE = 256


def pack(manifest_path: str, src_root: str, dst_root: Path) -> tuple[int, int]:
    n, total = 0, 0
    for row in load_manifest(manifest_path):
        src = Path(src_root) / row["building_id"] / row["filename"]
        if not src.is_file():
            continue
        dst = dst_root / row["building_id"] / row["filename"]
        if dst.is_file():
            n += 1
            total += dst.stat().st_size
            continue
        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                im.thumbnail((LONG_EDGE, LONG_EDGE))
                dst.parent.mkdir(parents=True, exist_ok=True)
                im.save(dst, "JPEG", quality=80)
        except Exception:
            continue
        n += 1
        total += dst.stat().st_size
        if n % 2000 == 0:
            print(f"  {dst_root.name}: {n} files ...", flush=True)
    return n, total


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pack-root", default=str(ROOT / "colab-pack"))
    args = ap.parse_args()
    pack_root = Path(args.pack_root)
    n1, b1 = pack(str(ROOT / "manifest.csv"), "local/monument-inbox",
                  pack_root / "pub")
    print(f"pub: {n1} files, {b1 / 1e9:.2f} GB", flush=True)
    n2, b2 = pack(str(ROOT / "mapillary_manifest.csv"), "local/mapillary-inbox",
                  pack_root / "map")
    print(f"map: {n2} files, {b2 / 1e9:.2f} GB", flush=True)
    print(f"TOTAL {n1 + n2} files, {(b1 + b2) / 1e9:.2f} GB -> upload {pack_root} "
          f"+ both manifest CSVs to Drive, mount at /content/drive, and run "
          f"train_contrastive.py with --image-root/--mapillary-root pointing there.")


if __name__ == "__main__":
    main()
