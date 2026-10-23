#!/usr/bin/env python3
"""Build the Mapillary training manifest: one row per fetched facing frame.

Same column shape as the publisher manifest so epoch_data.load_manifest reads
both. Differences are honest: caption_year comes from the EXIF-grade capture
timestamp (not a caption guess), drawing_flag is always 0 (all photographs),
and styles are empty (the publisher's weak labels do not transfer to a
different photographer's framing). Splits reuse split_of, so a building sits
in the same split on both poles -- no leakage by construction.
"""
from __future__ import annotations

import csv
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parents[2] / 'local' / 'training'
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from epoch_data import capture_era, split_of  # noqa: E402


def main() -> None:
    inbox = ROOT.parent / "mapillary-inbox"
    rows = []
    for manifest_path in sorted(inbox.glob("*/manifest.json")):
        building_id = manifest_path.parent.name
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for image in manifest.get("images", []):
            stamp = image.get("shot_date", "")
            year = None
            if stamp.isdigit():
                year = datetime.datetime.fromtimestamp(
                    int(stamp) / 1000, datetime.timezone.utc).year
            rows.append({
                "building_id": building_id,
                "municipality": manifest.get("municipality", ""),
                "filename": image["filename"],
                "source_filename": image["image_id"],
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
                "username": image.get("username", ""),
                "page_url": image.get("page_url", ""),
            })
    out = ROOT / "mapillary_manifest.csv"
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with_data = sum(1 for r in rows if r["capture_era"])
    print(f"wrote {out}: {len(rows)} frames from "
          f"{len({r['building_id'] for r in rows})} buildings, {with_data} dated")


if __name__ == "__main__":
    main()
