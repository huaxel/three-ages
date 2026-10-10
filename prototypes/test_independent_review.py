#!/usr/bin/env python3
"""Tests for blinded facade and structural second-annotator handoffs."""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from export_independent_review import (
    IMAGE_EVIDENCE, IMAGE_REVIEW, STRUCTURAL_EVIDENCE, STRUCTURAL_REVIEW, export,
)


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp)
        image_fields = IMAGE_EVIDENCE + (
            "annotation_status", "identity_note", "facade_observation",
            "structural_observation", "reviewer", "reviewed_at", "confidence",
        )
        image = {field: f"evidence:{field}" for field in IMAGE_EVIDENCE}
        image.update({
            "asset_id": "photo-1", "annotation_status": "reviewed image annotation",
            "identity_note": "PRIMARY SECRET", "facade_observation": "PRIMARY SECRET",
            "structural_observation": "PRIMARY SECRET", "reviewer": "primary",
            "reviewed_at": "2026-01-01", "confidence": "high",
        })
        write_csv(data / "three-ages-image-review.csv", image_fields, [image])

        structural_fields = STRUCTURAL_EVIDENCE + (
            "annotation_status", "identity_note", "identity_evidence_ids",
            "identity_evidence_urls", "identity_evidence_observations",
            "structural_observation", "reviewer", "reviewed_at", "confidence",
        )
        structural = {field: f"evidence:{field}" for field in STRUCTURAL_EVIDENCE}
        structural.update({
            "comparison_id": "comparison-1", "annotation_status": "reviewed structural comparison",
            "identity_note": "PRIMARY SECRET", "structural_observation": "PRIMARY SECRET",
            "reviewer": "primary", "reviewed_at": "2026-01-01", "confidence": "high",
        })
        write_csv(data / "three-ages-structural-review.csv", structural_fields, [structural])

        image_output, structural_output = export(data)
        image_columns, image_rows = read_csv(image_output)
        if image_columns != list(IMAGE_EVIDENCE + IMAGE_REVIEW):
            raise AssertionError("independent image worksheet columns do not match blind schema")
        if any(image_rows[0][field] for field in IMAGE_REVIEW):
            raise AssertionError("independent image annotation fields should start blank")
        if any("PRIMARY SECRET" in value for value in image_rows[0].values()):
            raise AssertionError("primary image review leaked into independent worksheet")

        structural_columns, structural_rows = read_csv(structural_output)
        if structural_columns != list(STRUCTURAL_EVIDENCE + STRUCTURAL_REVIEW):
            raise AssertionError("independent structural worksheet columns do not match blind schema")
        if any(structural_rows[0][field] for field in STRUCTURAL_REVIEW):
            raise AssertionError("independent structural annotation fields should start blank")
        if any("PRIMARY SECRET" in value for value in structural_rows[0].values()):
            raise AssertionError("primary structural review leaked into independent worksheet")

        image_rows[0].update({"facade_label": "Baroque", "facade_observation": "Independent observation", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        write_csv(image_output, image_columns, image_rows)
        structural_rows[0].update({"structural_observation": "Independent comparison", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        write_csv(structural_output, structural_columns, structural_rows)
        export(data)
        _, preserved_image = read_csv(image_output)
        _, preserved_structural = read_csv(structural_output)
        if preserved_image[0]["facade_observation"] != "Independent observation":
            raise AssertionError("regeneration discarded independent facade annotation")
        if preserved_structural[0]["structural_observation"] != "Independent comparison":
            raise AssertionError("regeneration discarded independent structural annotation")

        changed = dict(image)
        changed["preview_sha256"] = "changed"
        write_csv(data / "three-ages-image-review.csv", image_fields, [changed])
        try:
            export(data)
        except RuntimeError as error:
            if "after evidence changed" not in str(error):
                raise
        else:
            raise AssertionError("changed evidence did not refuse preserved independent annotation")

    print("blinded independent image/structural handoff and provenance refusal passed")


if __name__ == "__main__":
    main()
