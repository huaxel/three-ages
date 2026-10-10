#!/usr/bin/env python3
"""Tests for human adjudication worksheets after independent review."""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from compare_independent_reviews import compare


def write(path: Path, fields: tuple[str, ...], row: dict[str, str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerow(row)


def read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp)
        write(data / "three-ages-image-review.csv", (
            "asset_id", "facade_observation", "identity_note", "reviewer", "reviewed_at",
        ), {"asset_id": "photo-1", "facade_observation": "Baroque gable", "identity_note": "same facade", "reviewer": "Reviewer A", "reviewed_at": "2026-01-01"})
        write(data / "three-ages-independent-image-review.csv", (
            "asset_id", "identity_verdict", "facade_label", "facade_observation", "reviewer", "reviewed_at",
        ), {"asset_id": "photo-1", "identity_verdict": "confirmed", "facade_label": "Baroque", "facade_observation": "Baroque gable", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        output = compare(data, "image")
        fields, rows = read(output)
        if len(rows) != 1 or rows[0]["agreement"] or rows[0]["disposition"]:
            raise AssertionError("comparison must wait for human disposition")

        rows[0].update({
            "agreement": "agree", "rationale": "Both identify the gable as Baroque.",
            "disposition": "Retain label; note evidence limits.", "adjudicator": "Reviewer C",
            "adjudicated_at": "2026-01-03", "resolved_facade_label": "Baroque",
        })
        with output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader(); writer.writerows(rows)
        compare(data, "image")
        _, preserved = read(output)
        if preserved[0]["rationale"] != "Both identify the gable as Baroque.":
            raise AssertionError("regeneration discarded adjudication")

        second = {"asset_id": "photo-1", "identity_verdict": "confirmed", "facade_label": "Baroque", "facade_observation": "A different view", "reviewer": "Reviewer A", "reviewed_at": "2026-01-02"}
        write(data / "three-ages-independent-image-review.csv", tuple(second), second)
        try:
            compare(data, "image")
        except RuntimeError as error:
            if "not independent" not in str(error):
                raise
        else:
            raise AssertionError("same annotator was incorrectly accepted as independent")

        write(data / "three-ages-structural-review.csv", (
            "source_id", "comparison_id", "structural_observation", "reviewer", "reviewed_at",
        ), {"source_id": "case-1", "comparison_id": "epochs-1", "structural_observation": "stable volume", "reviewer": "Reviewer A", "reviewed_at": "2026-01-01"})
        write(data / "three-ages-independent-structural-review.csv", (
            "source_id", "comparison_id", "structural_observation", "reviewer", "reviewed_at",
        ), {"source_id": "case-1", "comparison_id": "epochs-1", "structural_observation": "volume changed", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
        structural_output = compare(data, "structural")
        _, structural_rows = read(structural_output)
        if structural_rows[0]["primary_annotation"] != "structural_observation: stable volume" or structural_rows[0]["independent_annotation"] != "structural_observation: volume changed":
            raise AssertionError("structural annotations were not paired in adjudication output")

        for channel in ("balat", "commons"):
            filename = "balat-photo" if channel == "balat" else "commons-photo"
            write(data / f"{filename}-review.csv", (
                "photo_id", "facade_label", "facade_observation", "reviewer", "reviewed_at",
            ), {"photo_id": f"{channel}-1", "facade_label": "Art Nouveau", "facade_observation": "Primary label", "reviewer": "Reviewer A", "reviewed_at": "2026-01-01"})
            write(data / f"{filename.replace('-photo', '-independent-photo')}-review.csv", (
                "photo_id", "identity_verdict", "facade_label", "facade_observation", "reviewer", "reviewed_at",
            ), {"photo_id": f"{channel}-1", "identity_verdict": "confirmed", "facade_label": "Eclecticism", "facade_observation": "Independent label", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"})
            paired = compare(data, channel)
            _, paired_rows = read(paired)
            if paired_rows[0]["independent_reviewer"] != "Reviewer B":
                raise AssertionError(f"{channel} annotations were not paired")

        # Every independent field must be supplied before pairing.
        incomplete = {"asset_id": "photo-1", "identity_verdict": "confirmed", "facade_label": "", "facade_observation": "A different view", "reviewer": "Reviewer B", "reviewed_at": "2026-01-02"}
        write(data / "three-ages-independent-image-review.csv", tuple(incomplete), incomplete)
        try:
            compare(data, "image")
        except RuntimeError as error:
            if "lacks a completed annotation" not in str(error):
                raise
        else:
            raise AssertionError("incomplete independent annotation was accepted")

    print("independent image/structural pairing and adjudication preservation passed")


if __name__ == "__main__":
    main()
