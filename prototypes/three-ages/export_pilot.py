#!/usr/bin/env python3
"""Export the source-linked Three Ages pilot as a review worksheet."""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUTPUT = DATA / "three-ages-pilot-export.csv"

FIELDS = [
    "source_id",
    "name",
    "address",
    "latitude",
    "longitude",
    "review_status",
    "register_status",
    "register_value",
    "register_source_kind",
    "register_source_url",
    "facade_status",
    "facade_value",
    "structure_status",
    "structure_value",
    "selection_reason",
    "next_step",
    "image_evidence_count",
    "image_evidence_ids",
    "image_evidence_epochs",
    "image_evidence_urls",
]


def main() -> None:
    source = json.loads((DATA / "grand-place-buildings.json").read_text())
    pilot = json.loads((DATA / "three-ages-pilot.json").read_text())
    sources = {str(record["id"]): record for record in source["records"]}
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for case in pilot["records"]:
            record = sources[case["source_id"]]
            writer.writerow({
                "source_id": case["source_id"],
                "name": record.get("name", ""),
                "address": record.get("address", ""),
                "latitude": record.get("latitude", ""),
                "longitude": record.get("longitude", ""),
                "review_status": pilot.get("review_status", ""),
                "register_status": case["register"]["status"],
                "register_value": case["register"]["value"] or "",
                "register_source_kind": case["register"].get("source", {}).get("kind", ""),
                "register_source_url": case["register"].get("source", {}).get("url") or case["register"].get("source", {}).get("claim_url", ""),
                "facade_status": case["facade"]["status"],
                "facade_value": case["facade"]["value"] or "",
                "structure_status": case["structure"]["status"],
                "structure_value": case["structure"]["value"] or "",
                "selection_reason": case["selection_reason"],
                "next_step": case["next_step"],
                "image_evidence_count": len(case["image_evidence"]),
                "image_evidence_ids": ";".join(str(asset.get("asset_id", "")) for asset in case["image_evidence"]),
                "image_evidence_epochs": ";".join(str(asset.get("epoch", "")) for asset in case["image_evidence"]),
                "image_evidence_urls": ";".join(asset.get("source_url", "") for asset in case["image_evidence"]),
            })
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
