#!/usr/bin/env python3
"""Tests for blind pilot and scaled-corpus second-annotator handoffs."""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from export_independent_review import (
    BALAT_EVIDENCE, COMMONS_EVIDENCE, IMAGE_EVIDENCE, IMAGE_REVIEW,
    PHOTO_REVIEW, STRUCTURAL_EVIDENCE, STRUCTURAL_REVIEW, export,
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
        image.update({"asset_id": "photo-1", "annotation_status": "reviewed image annotation", "identity_note": "PRIMARY SECRET", "facade_observation": "PRIMARY SECRET", "structural_observation": "PRIMARY SECRET", "reviewer": "primary", "reviewed_at": "2026-01-01", "confidence": "high"})
        write_csv(data / "three-ages-image-review.csv", image_fields, [image])

        structural_fields = STRUCTURAL_EVIDENCE + (
            "annotation_status", "identity_note", "identity_evidence_ids",
            "identity_evidence_urls", "identity_evidence_observations",
            "structural_observation", "reviewer", "reviewed_at", "confidence",
        )
        structural = {field: f"evidence:{field}" for field in STRUCTURAL_EVIDENCE}
        structural.update({"comparison_id": "comparison-1", "annotation_status": "reviewed structural comparison", "identity_note": "PRIMARY SECRET", "structural_observation": "PRIMARY SECRET", "reviewer": "primary", "reviewed_at": "2026-01-01", "confidence": "high"})
        write_csv(data / "three-ages-structural-review.csv", structural_fields, [structural])

        scaled_paths = {}
        for stem, evidence_fields in (("balat", BALAT_EVIDENCE), ("commons", COMMONS_EVIDENCE)):
            source_fields = evidence_fields + ("facade_label", "facade_observation", "reviewer", "reviewed_at", "confidence", "annotation_status")
            source = {field: f"evidence:{field}" for field in evidence_fields}
            source.update({"photo_id": f"{stem}-photo", "facade_label": "PRIMARY SECRET", "facade_observation": "PRIMARY SECRET", "reviewer": "Primary", "reviewed_at": "2026-01-01", "confidence": "high", "annotation_status": "reviewed photo annotation"})
            write_csv(data / f"{stem}-photo-review.csv", source_fields, [source])
            scaled_paths[stem] = data / f"{stem}-independent-photo-review.csv"

        image_output, structural_output, balat_output, commons_output = export(data)
        image_columns, image_rows = read_csv(image_output)
        if image_columns != list(IMAGE_EVIDENCE + IMAGE_REVIEW) or any(image_rows[0][field] for field in IMAGE_REVIEW):
            raise AssertionError("independent image worksheet schema or blank fields are wrong")
        structural_columns, structural_rows = read_csv(structural_output)
        if structural_columns != list(STRUCTURAL_EVIDENCE + STRUCTURAL_REVIEW) or any(structural_rows[0][field] for field in STRUCTURAL_REVIEW):
            raise AssertionError("independent structural worksheet schema or blank fields are wrong")
        for path in (image_output, structural_output, balat_output, commons_output):
            _, rows = read_csv(path)
            if any("PRIMARY SECRET" in value for row in rows for value in row.values()):
                raise AssertionError(f"primary annotation leaked into {path.name}")

        for output, fields, rows, key in (
            (image_output, image_columns, image_rows, "facade_observation"),
            (structural_output, structural_columns, structural_rows, "structural_observation"),
        ):
            rows[0][key] = "Independent annotation"
            rows[0]["reviewer"] = "Reviewer B"
            rows[0]["reviewed_at"] = "2026-01-02"
            write_csv(output, fields, rows)
        scaled_row = read_csv(balat_output)[1][0]
        scaled_row.update({"identity_verdict": "confirmed", "facade_label": "Art Nouveau", "facade_observation": "Independent scaled review", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        write_csv(balat_output, list(read_csv(balat_output)[0]), [scaled_row])
        export(data)
        if read_csv(balat_output)[1][0]["facade_observation"] != "Independent scaled review":
            raise AssertionError("regeneration discarded scaled independent draft")

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

    print("blind pilot/scaled review handoffs and provenance refusal passed")


if __name__ == "__main__":
    main()
