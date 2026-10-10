#!/usr/bin/env python3
"""Tests for the standalone blind-review bundle."""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from build_independent_review_bundle import IMAGE_ALLOWED_FIELDS, STRUCTURAL_ALLOWED_FIELDS, build


def write_csv(path: Path, fields: tuple[str, ...], row: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp) / "data"
        data.mkdir()
        (data / "historical").mkdir()
        (data / "structural").mkdir()
        photo = b"licensed image bytes"
        crop = b"structural crop bytes"
        (data / "historical" / "photo.jpg").write_bytes(photo)
        (data / "structural" / "crop.png").write_bytes(crop)
        image_fields = IMAGE_ALLOWED_FIELDS
        image = {field: "" for field in image_fields}
        image.update({"asset_id": "photo-1", "preview": "data/historical/photo.jpg", "preview_sha256": hashlib.sha256(photo).hexdigest(), "licence": "CC BY 4.0", "credit": "Photographer", "facade_observation": "Independent observation", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        write_csv(data / "three-ages-independent-image-review.csv", image_fields, image)
        structural_fields = STRUCTURAL_ALLOWED_FIELDS
        structural = {field: "" for field in structural_fields}
        structural.update({"source_id": "case-1", "comparison_id": "epochs-1", "case_crop_previews": "data/structural/crop.png", "case_crop_pixel_sha256": "abc", "structural_observation": "Independent comparison", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        write_csv(data / "three-ages-independent-structural-review.csv", structural_fields, structural)
        output = build(data, Path(temp) / "review.zip")
        with zipfile.ZipFile(output) as archive:
            names = set(archive.namelist())
            if "evidence/data/historical/photo.jpg" not in names or "evidence/data/structural/crop.png" not in names:
                raise AssertionError("bundle omitted referenced evidence")
            if any("primary" in name.lower() for name in names):
                raise AssertionError("bundle contains primary review artifacts")
            payload = b"\n".join(archive.read(name) for name in names if name.endswith(".csv"))
            if b"confidence" in payload or b"Independent observation" not in payload:
                raise AssertionError("bundle unexpectedly contains a confidence field or lost reviewer input")
            manifest = json.loads(archive.read("SHA256SUMS.json"))
            for name, digest in manifest["files"].items():
                if hashlib.sha256(archive.read(name)).hexdigest() != digest:
                    raise AssertionError(f"bundle checksum mismatch: {name}")

        # An unexpected primary-review field must fail closed, never get packaged.
        image_fields = image_fields + ("confidence",)
        image["confidence"] = "high"
        write_csv(data / "three-ages-independent-image-review.csv", image_fields, image)
        try:
            build(data, Path(temp) / "unsafe.zip")
        except RuntimeError as error:
            if "possibly non-blind" not in str(error):
                raise
        else:
            raise AssertionError("unexpected confidence column was accepted into bundle")

    print("standalone blind-review bundle excludes primary annotations and verifies checksums")


if __name__ == "__main__":
    main()
