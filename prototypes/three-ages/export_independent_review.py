#!/usr/bin/env python3
"""Generate blind second-annotator worksheets from pilot image evidence.

Primary review fields are intentionally omitted. The outputs contain pinned
provenance and blank independent-review fields; they are not training labels.
"""
from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
IMAGE_SOURCE = "three-ages-image-review.csv"
IMAGE_OUTPUT = "three-ages-independent-image-review.csv"
IMAGE_EVIDENCE = (
    "source_id", "name", "address", "asset_id", "epoch", "source_url",
    "image_url", "preview", "preview_sha256", "licence", "credit",
    "source_observation",
)
IMAGE_REVIEW = ("identity_verdict", "facade_label", "facade_observation", "reviewer", "reviewed_at")
STRUCTURAL_SOURCE = "three-ages-structural-review.csv"
STRUCTURAL_OUTPUT = "three-ages-independent-structural-review.csv"
STRUCTURAL_EVIDENCE = (
    "source_id", "name", "address", "comparison_id", "area_asset_ids", "area_epochs",
    "area_source_urls", "area_image_urls", "area_previews", "area_preview_sha256",
    "area_licences", "area_credits", "case_latitude", "case_longitude",
    "crop_source_center_pixels", "crop_box_pixels", "crop_size_pixels",
    "case_crop_previews", "case_crop_pixel_sha256", "source_observation",
)
STRUCTURAL_REVIEW = ("structural_observation", "reviewer", "reviewed_at")


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def write_rows(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def export_channel(data_dir: Path, source_name: str, output_name: str,
                   evidence_fields: tuple[str, ...], review_fields: tuple[str, ...],
                   key_field: str, channel: str) -> Path:
    source_path, output_path = data_dir / source_name, data_dir / output_name
    fields = evidence_fields + review_fields
    source_fields, source_rows = read_rows(source_path)
    missing = set(evidence_fields) - set(source_fields)
    if missing:
        raise RuntimeError(f"{channel} source worksheet missing evidence fields: {sorted(missing)}")
    key_fields = key_field.split("|")
    row_key = lambda row: "|".join(row.get(field, "") for field in key_fields)
    keys = [row_key(row) for row in source_rows]
    if any(not all(row.get(field) for field in key_fields) for row in source_rows) or len(set(keys)) != len(keys):
        raise RuntimeError(f"{channel} source worksheet has missing or duplicate {key_field} values")

    prior_rows: dict[str, dict[str, str]] = {}
    if output_path.exists():
        prior_fields, previous = read_rows(output_path)
        if prior_fields != list(fields):
            raise RuntimeError(f"existing independent {channel} worksheet has unexpected columns")
        for row in previous:
            key = row_key(row)
            if not all(row.get(field) for field in key_fields) or key in prior_rows:
                raise RuntimeError(f"independent {channel} worksheet has missing or duplicate {key_field}")
            prior_rows[key] = row

    fresh = {row_key(row): row for row in source_rows}
    removed = set(prior_rows) - set(fresh)
    if removed and any(any(prior_rows[key].get(field, "").strip() for field in review_fields) for key in removed):
        raise RuntimeError(f"refusing to discard independent {channel} annotations for removed keys: {sorted(removed)}")

    merged = []
    for key, source in fresh.items():
        previous = prior_rows.get(key, {})
        provenance = {field: source.get(field, "") for field in evidence_fields}
        mismatches = [field for field in evidence_fields if previous and previous.get(field, "") != provenance[field]]
        if mismatches:
            raise RuntimeError(f"refusing to attach independent {channel} annotation {key} after evidence changed: {mismatches}")
        merged.append({**provenance, **{field: previous.get(field, "") for field in review_fields}})
    write_rows(output_path, fields, merged)
    return output_path


def export(data_dir: Path = DATA) -> tuple[Path, Path]:
    image = export_channel(data_dir, IMAGE_SOURCE, IMAGE_OUTPUT, IMAGE_EVIDENCE, IMAGE_REVIEW, "asset_id", "image")
    structural = export_channel(data_dir, STRUCTURAL_SOURCE, STRUCTURAL_OUTPUT, STRUCTURAL_EVIDENCE, STRUCTURAL_REVIEW, "source_id|comparison_id", "structural")
    return image, structural


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    image, structural = export(args.data_dir)
    print(f"blind independent image-review worksheet: {image}")
    print(f"blind independent structural-review worksheet: {structural}")


if __name__ == "__main__":
    main()
