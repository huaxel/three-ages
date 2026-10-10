#!/usr/bin/env python3
"""Tests for safe import of blind-review ZIPs."""
from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from build_independent_review_bundle import (
    BALAT_ALLOWED_FIELDS, BALAT_WORKSHEET, COMMONS_ALLOWED_FIELDS, COMMONS_WORKSHEET,
    IMAGE_ALLOWED_FIELDS, STRUCTURAL_ALLOWED_FIELDS, build,
)
from import_independent_review_bundle import import_bundle


def write_csv(path: Path, fields: tuple[str, ...], row: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def csv_with_update(body: bytes, updates: dict[str, str]) -> bytes:
    reader = csv.DictReader(io.StringIO(body.decode("utf-8"), newline=""))
    fields = list(reader.fieldnames or [])
    rows = list(reader)
    rows[0].update(updates)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        data = root / "data"
        (data / "historical").mkdir(parents=True)
        (data / "structural").mkdir()
        (data / "historical" / "img.jpg").write_bytes(b"photo")
        (data / "historical" / "balat.jpg").write_bytes(b"balat")
        (data / "historical" / "commons.jpg").write_bytes(b"commons")
        (data / "structural" / "crop.png").write_bytes(b"crop")

        image = {field: "" for field in IMAGE_ALLOWED_FIELDS}
        image.update({"source_id": "005", "name": "Case", "address": "Address", "asset_id": "asset-1", "epoch": "1942", "source_url": "source", "image_url": "image", "preview": "data/historical/img.jpg", "preview_sha256": "hash", "licence": "CC BY 4.0", "credit": "credit"})
        write_csv(data / "three-ages-independent-image-review.csv", IMAGE_ALLOWED_FIELDS, image)

        structural = {field: "" for field in STRUCTURAL_ALLOWED_FIELDS}
        structural.update({"source_id": "005", "comparison_id": "epochs", "case_crop_previews": "data/structural/crop.png", "case_crop_pixel_sha256": "hash"})
        write_csv(data / "three-ages-independent-structural-review.csv", STRUCTURAL_ALLOWED_FIELDS, structural)

        for filename, schema, photo, preview in (
            (BALAT_WORKSHEET, BALAT_ALLOWED_FIELDS, "balat-1", "data/historical/balat.jpg"),
            (COMMONS_WORKSHEET, COMMONS_ALLOWED_FIELDS, "commons-1", "data/historical/commons.jpg"),
        ):
            row = {field: "" for field in schema}
            row.update({"photo_id": photo, "preview": preview, "preview_sha256": "hash", "licence": "CC BY 4.0", "credit": "credit"})
            write_csv(data / filename, schema, row)

        bundle = build(data, root / "original.zip")
        returned = root / "returned.zip"
        with zipfile.ZipFile(bundle) as original, zipfile.ZipFile(returned, "w", zipfile.ZIP_DEFLATED) as edited:
            for name in original.namelist():
                body = original.read(name)
                if name == "three-ages-independent-image-review.csv":
                    body = csv_with_update(body, {
                        "identity_verdict": "confirmed", "facade_label": "Baroque",
                        "facade_observation": "Independent facade note", "reviewer": "Reviewer B",
                        "reviewed_at": "2026-10-10",
                    })
                edited.writestr(name, body)
        imported = import_bundle(returned, data)
        if len(imported) != 4:
            raise AssertionError("importer did not update all independent worksheets")
        with (data / "three-ages-independent-image-review.csv").open(newline="", encoding="utf-8") as handle:
            review = next(csv.DictReader(handle))
        if review["facade_label"] != "Baroque" or review["preview"] != "data/historical/img.jpg":
            raise AssertionError("import failed to copy annotations or localize paths")

        before = {path: path.read_bytes() for path in imported}
        tampered = root / "tampered.zip"
        with zipfile.ZipFile(bundle) as original, zipfile.ZipFile(tampered, "w", zipfile.ZIP_DEFLATED) as edited:
            for name in original.namelist():
                body = original.read(name)
                if name == "three-ages-independent-image-review.csv":
                    body = csv_with_update(body, {"address": "Tampered address", "facade_label": "Art Deco"})
                edited.writestr(name, body)
        try:
            import_bundle(tampered, data)
        except RuntimeError as error:
            if "evidence changed" not in str(error):
                raise
        else:
            raise AssertionError("changed evidence was imported")
        if any(path.read_bytes() != body for path, body in before.items()):
            raise AssertionError("failed import modified a local review worksheet")

    print("review ZIP import preserves provenance and rejects tampering")


if __name__ == "__main__":
    main()
