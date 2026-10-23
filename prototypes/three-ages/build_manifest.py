#!/usr/bin/env python3
"""Build the training manifest: one row per on-disk picture.

Joins the scraped records (labels) with the picture store (pixels): caption
year, capture era, drawing flag, styles, typologies, contributor years,
coordinates, and a deterministic building-level train/val/test split that
stays stable as the crawl grows.

Dedupes at build: the source occasionally lists the same file twice under
different captions/years (re-credited reprints); one row per physical
picture survives, keeping the earliest caption year. epoch_data.load_manifest
re-applies the same rule defensively.

Re-run at crawl freeze; probes filter to embedded ids, so a fresher manifest
never breaks them.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from epoch_data import capture_era, split_of  # noqa: E402
from scrape_monument import local_names  # noqa: E402

YEAR = re.compile(r"\b(1[89]\d\d|20[0-2]\d)\b")
DRAW = re.compile(r"\b(plan|projet|coupe|élévation|elevation|dessin|schéma|schema|"
                  r"relevé|gravure|maquette|perspective)\b", re.I)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scraped", default="local/scraped")
    parser.add_argument("--image-root", default="local/monument-inbox")
    parser.add_argument("--out", default="local/training/manifest.csv")
    args = parser.parse_args()

    records: dict[str, dict] = {}
    for path in glob.glob(str(Path(args.scraped) / "*.fr.json")):
        if path.endswith("rubrics.fr.json"):
            continue
        try:
            record = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(record, dict) or "building_id" not in record:
            continue  # journals and rubrics live beside the records
        records[str(record["building_id"])] = record

    best: dict[str, dict] = {}
    for building_id, record in records.items():
        municipality = record["city"]["name"]
        styles = sorted(t["value"] for t in record.get("tags") or [] if t["kind"] == "style")
        typos = sorted(t["value"] for t in record.get("tags") or [] if t["kind"] == "typology")
        cyears = sorted({y for c in record.get("contributors") or [] for y in c.get("years") or []})
        lat = (record.get("coordinates") or {}).get("latitude") or ""
        lon = (record.get("coordinates") or {}).get("longitude") or ""
        images = record.get("images") or []
        # Disk names go through the same collision-aware mapping as the
        # downloader and the audit: 571 raw filenames are shared by listings
        # that are distinct digital objects (different URLs and bytes), and the
        # renamed copies live on disk under their mapped names.
        for image, disk_name in zip(images, local_names(images)):
            if not os.path.exists(str(Path(args.image_root) / building_id / disk_name)):
                continue
            caption = image.get("caption") or ""
            found = YEAR.findall(caption)
            year = int(found[-1]) if found else None
            row = {"building_id": building_id, "municipality": municipality,
                   "filename": disk_name, "source_filename": image["filename"],
                   "caption": caption,
                   "caption_year": year or "", "capture_era": capture_era(year),
                   "drawing_flag": int(bool(DRAW.search(caption))),
                   "width": image.get("width") or "", "height": image.get("height") or "",
                   "styles": "|".join(styles), "typologies": "|".join(typos),
                   "contributor_years": "|".join(cyears),
                   "latitude": lat, "longitude": lon, "split": split_of(building_id)}
            best[f"{building_id}/{disk_name}"] = row

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(next(iter(best.values()))))
        writer.writeheader()
        writer.writerows(best.values())
    print(f"wrote {out}: {len(best)} pictures from {len({r['building_id'] for r in best.values()})} buildings")


if __name__ == "__main__":
    main()
