#!/usr/bin/env python3
"""Export the task-B label queue as a self-contained workbench bundle.

Reads local/training/taskb_queue.csv (gitignored working copy) plus the
training manifest, and writes prototypes/three-ages/data/taskb-queue.json:
one record per queue row with the review context (suggestion, rebuild flag,
excerpts, proxy timeline) and up to 4 facade preview images.

Serve the repo root over HTTP (python3 -m http.server) and open
prototypes/three-ages/taskb_review.html. Image paths in the bundle are
root-relative, so the workbench must be served from the root, not opened
as a file.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
QUEUE = ROOT / "local" / "training" / "taskb_queue.csv"
MANIFEST = ROOT / "local" / "training" / "manifest.csv"
INBOX = ROOT / "local" / "monument-inbox"
OUT = Path(__file__).resolve().parent / "data" / "taskb-queue.json"
ERAS = ["pre-1850", "1850-1892", "1893-1914", "1918-1940", "1945-1975", "post-1975"]
PHOTOS_PER_BUILDING = 4


def load_manifest_photos() -> dict[str, list[dict]]:
    photos: dict[str, list[dict]] = {}
    with open(MANIFEST, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("drawing_flag", "0").strip() == "1":
                continue
            preview = INBOX / row["building_id"] / "preview" / row["filename"]
            full = INBOX / row["building_id"] / row["filename"]
            path = preview if preview.exists() else (full if full.exists() else None)
            if path is None:
                continue
            photos.setdefault(row["building_id"], []).append({
                "src": path.relative_to(ROOT).as_posix(),
                "capture_era": row.get("capture_era", ""),
                "caption": (row.get("caption", "") or "")[:80],
            })
    return photos


def main() -> None:
    if not QUEUE.exists():
        raise SystemExit(f"queue not found: {QUEUE}")
    photos = load_manifest_photos()
    records = []
    with open(QUEUE, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            bid = row["building_id"]
            records.append({
                "building_id": bid,
                "identity_name": row.get("identity_name", ""),
                "address": row.get("address", ""),
                "styles": row.get("styles", ""),
                "proxy_years": row.get("proxy_years", ""),
                "proxy_bin": row.get("proxy_bin", ""),
                "primary_years": row.get("primary_years", ""),
                "suggested_era": row.get("suggested_era", ""),
                "rebuild_flag": row.get("rebuild_flag", ""),
                "notice_excerpt": row.get("notice_excerpt", ""),
                "notice_sources": row.get("notice_sources", ""),
                "notice_url": row.get("notice_url", ""),
                "labelled_era": row.get("construction_era", ""),
                "photos": photos.get(bid, [])[:PHOTOS_PER_BUILDING],
                "photo_count": len(photos.get(bid, [])),
            })
    labelled = sum(1 for r in records if r["labelled_era"])
    OUT.write_text(json.dumps(
        {"eras": ERAS, "records": records}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} ({len(records)} rows, {labelled} already labelled)")
    missing = [r["building_id"] for r in records if not r["photos"]]
    if missing:
        print(f"no servable photos for {len(missing)} rows (showing first 5): {missing[:5]}")


if __name__ == "__main__":
    sys.exit(main())
