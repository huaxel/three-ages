#!/usr/bin/env python3
"""Build the Mapillary training manifest: one row per fetched facing frame.

Same column shape as the publisher manifest so epoch_data.load_manifest reads
both. Differences are honest: caption_year comes from the EXIF-grade capture
timestamp (not a caption guess), drawing_flag is always 0 (all photographs),
and styles are empty (the publisher's weak labels do not transfer to a
different photographer's framing). Splits reuse split_of, so a building sits
in the same split on both poles. This prevents building-ID split overlap, not
capture-sequence dependence; explicit native sequence evidence is preserved.
"""
from __future__ import annotations

import csv
import datetime
import io
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[2] / 'local' / 'training'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from epoch_data import capture_era, split_of  # noqa: E402
from sequence_metadata import sequence_id, sequence_groups  # noqa: E402


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    ap.add_argument('--inbox', default=str(DATA.parent / 'mapillary-inbox'))
    ap.add_argument('--out', default=str(DATA / 'mapillary_manifest.csv'))
    args = ap.parse_args()
    inbox = Path(args.inbox)
    out = Path(args.out)
    if os.path.lexists(out):
        raise FileExistsError(f"refusing existing output: {out}")
    if not inbox.is_dir():
        raise ValueError(f"inbox is not a directory: {inbox}")
    rows = []
    seen_images = set()
    for manifest_path in sorted(inbox.glob("*/manifest.json")):
        building_id = manifest_path.parent.name
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("images"), list):
            raise ValueError(f"{manifest_path}: expected object with images list")
        if 'building_id' in manifest and str(manifest['building_id']).strip() != building_id:
            raise ValueError(f'{manifest_path}: building_id differs from cache directory')
        municipality = manifest.get("municipality", "")
        if municipality is None:
            municipality = ''
        if not isinstance(municipality, str):
            raise ValueError(f"{manifest_path}: municipality must be a string")
        for image in manifest["images"]:
            if not isinstance(image, dict):
                raise ValueError(f"{manifest_path}: image must be an object")
            seq = sequence_id(image)
            for field in ("filename", "username", "page_url"):
                value = image.get(field, "")
                if field != 'filename' and value is None:
                    value = ''
                if not isinstance(value, str) or (field == "filename" and not value.strip()):
                    raise ValueError(f"{manifest_path}: invalid {field}")
            filename = image['filename']
            if filename in ('.', '..') or '/' in filename or '\\' in filename:
                raise ValueError(f'{manifest_path}: filename must be a plain disk name')
            key = (building_id, filename)
            if key in seen_images:
                raise ValueError(f'{manifest_path}: duplicate image filename')
            seen_images.add(key)
            image_id = image.get("image_id")
            if (isinstance(image_id, bool) or not isinstance(image_id, (str, int))
                    or not str(image_id).strip() or isinstance(image_id, int) and image_id < 0):
                raise ValueError(f"{manifest_path}: invalid image_id")
            image_id = str(image_id).strip()
            stamp = image.get("shot_date", "")
            if stamp is None:
                stamp = ""
            if isinstance(stamp, int) and not isinstance(stamp, bool):
                stamp = str(stamp)
            if (not isinstance(stamp, str)
                    or (stamp and (not stamp.isascii() or not stamp.isdigit()))):
                raise ValueError(f"{manifest_path}: invalid shot_date milliseconds")
            year = None
            if stamp.isdigit():
                year = datetime.datetime.fromtimestamp(
                    int(stamp) / 1000, datetime.timezone.utc).year
            rows.append({
                "building_id": building_id,
                "municipality": municipality,
                "filename": image["filename"],
                "source_filename": image_id,
                "sequence_id": seq,
                "caption": "",
                "caption_year": year or "",
                "capture_era": capture_era(year),
                "drawing_flag": 0,
                "width": "", "height": "",
                "styles": "", "typologies": "",
                "contributor_years": "",
                "latitude": "", "longitude": "",
                "split": split_of(building_id),
                "shot_date": stamp,
                "username": image.get("username") or "",
                "page_url": image.get("page_url") or "",
            })
    if not rows:
        raise ValueError("no image rows in inbox")
    sequence_groups(rows)  # Validate repeated native source IDs before any output.
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    # Exclusive creation also refuses dangling symlinks and a racing writer.
    with open(out, "x", newline="", encoding="utf-8") as handle:
        # Never unlink a path on failure: a concurrent actor could have replaced
        # its directory entry. Partial NEW output is safer than deleting data.
        handle.write(buffer.getvalue())
    with_data = sum(1 for r in rows if r["capture_era"])
    print(f"wrote {out}: {len(rows)} frames from "
          f"{len({r['building_id'] for r in rows})} buildings, {with_data} dated")


if __name__ == "__main__":
    main()
