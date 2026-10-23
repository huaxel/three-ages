#!/usr/bin/env python3
"""Tests for facade review dataset evaluation, leakage audit, and split feasibility."""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile

from audit_facade_dataset import (
    audit_facade_dataset,
    check_split_leakage,
    find_connected_groups,
    format_audit_report,
)

ROOT = Path(__file__).resolve().parent
COMMITTED_CSV = ROOT / "three-ages" / "data" / "three-ages-image-review.csv"

def _worksheet_header() -> list[str]:
    """Derive the header from the exporter so this test cannot drift from the real schema.

    A hand-kept copy of the column list silently fell behind when the worksheet gained
    source_label_kind, which made the synthetic rows in this file unrepresentative.
    """
    import runpy

    return list(runpy.run_path(str(ROOT / "three-ages" / "export_pilot.py"))["IMAGE_FIELDS"])


CSV_HEADER = _worksheet_header()


def write_test_csv(path: Path, rows: list[dict[str, str]]) -> None:
    """Helper to write synthetic rows with complete header fields."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADER, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            full_row = {col: r.get(col, "") for col in CSV_HEADER}
            writer.writerow(full_row)


def test_pending_rows_audit() -> None:
    """Pending rows must be recognized as unreviewed, blocking held-out evaluation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "pending.csv"
        rows = [
            {
                "source_id": f"00{i}",
                "facade_unit_id": f"gp-00{i}",
                "asset_id": f"asset-{i}",
                "preview_sha256": f"hash-{i}",
                "annotation_status": "source preview; no reviewer annotation",
                "source_style_text": "Baroque gable",
                "facade_style": "",
                "reviewer": "",
                "reviewed_at": "",
                "confidence": "",
            }
            for i in range(1, 6)
        ]
        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path)
        readiness = report["label_readiness"]
        split = report["split_feasibility"]

        assert readiness["total_rows"] == 5
        assert readiness["reviewed_rows_count"] == 0
        assert readiness["pending_rows_count"] == 5
        assert readiness["is_ready_for_evaluation"] is False
        assert split["is_feasible"] is False
        assert "INSUFFICIENT DATA FOR MEANINGFUL HELD-OUT RECOGNITION SCORE" in split["summary_verdict"]
        assert any("Zero reviewed rows" in r for r in split["inadequacy_reasons"])


def test_weak_label_kinds_are_separated() -> None:
    """Curated style labels and raw facade text must be summarised apart, not merged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "kinds.csv"
        rows = [
            {"source_id": "001", "facade_unit_id": "gp-001", "asset_id": "a1", "preview_sha256": "h1",
             "source_style_text": "Baroque", "source_label_kind": "curated source-described style"},
            {"source_id": "001", "facade_unit_id": "gp-001", "asset_id": "a2", "preview_sha256": "h2",
             "source_style_text": "Baroque", "source_label_kind": "curated source-described style"},
            {"source_id": "002", "facade_unit_id": "gp-002", "asset_id": "a3", "preview_sha256": "h3",
             "source_style_text": "A long municipal paragraph about registers and gables.",
             "source_label_kind": "raw city facade description"},
        ]
        write_test_csv(csv_path, rows)
        kinds = audit_facade_dataset(csv_path)["weak_label_audit"]["weak_label_kinds"]
        assert set(kinds) == {"curated source-described style", "raw city facade description"}, kinds
        assert kinds["curated source-described style"]["rows"] == 2
        assert kinds["curated source-described style"]["distinct_values"] == 1
        assert kinds["raw city facade description"]["rows"] == 1


def test_weak_label_isolation() -> None:
    """source_style_text must be treated as weak metadata and NEVER as ground truth."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "weak_labels.csv"
        rows = [
            {
                "source_id": "001",
                "facade_unit_id": "gp-001",
                "asset_id": "asset-1",
                "preview_sha256": "h1",
                "source_style_text": "Baroque",
                "facade_style": "",
            },
            {
                "source_id": "002",
                "facade_unit_id": "gp-002",
                "asset_id": "asset-2",
                "preview_sha256": "h2",
                "source_style_text": "Classical French style",
                "facade_style": "",
            },
            {
                "source_id": "003",
                "facade_unit_id": "gp-003",
                "asset_id": "asset-3",
                "preview_sha256": "h3",
                "source_style_text": "Renaissance-inspired",
                "facade_style": "",
            },
        ]
        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path)
        weak = report["weak_label_audit"]
        readiness = report["label_readiness"]

        assert weak["rows_with_weak_label"] == 3
        assert "NEVER be treated as ground truth" in weak["disclaimer"]

        # source_style_text carries a curated label for some rows and raw facade text for
        # others; aggregating them together compares a category against paragraphs.
        kinds = weak.get("weak_label_kinds")
        assert kinds is not None, "weak-label audit does not group values by source_label_kind"
        for kind, info in kinds.items():
            assert info["rows"] >= info["distinct_values"], f"{kind} counts are inconsistent"
        assert readiness["reviewed_rows_count"] == 0
        assert readiness["per_class_image_counts"] == {}
        assert report["split_feasibility"]["is_feasible"] is False


def test_repeated_building_leakage() -> None:
    """Multi-image buildings and multi-record units must be detected and preserved as atomic groups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "leakage.csv"
        rows = [
            # gp-005 has 2 images for building 005
            {
                "source_id": "005",
                "facade_unit_id": "gp-005",
                "asset_id": "asset-5a",
                "preview_sha256": "h5a",
                "facade_style": "baroque",
                "facade_observation": "Gable carving",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
            {
                "source_id": "005",
                "facade_unit_id": "gp-005",
                "asset_id": "asset-5b",
                "preview_sha256": "h5b",
                "facade_style": "baroque",
                "facade_observation": "Full facade",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
            # gp-13-19 covers two buildings: 014 and 015
            {
                "source_id": "014",
                "facade_unit_id": "gp-13-19",
                "asset_id": "asset-14",
                "preview_sha256": "h14",
                "facade_style": "baroque",
                "facade_observation": "Colonnade",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
            {
                "source_id": "015",
                "facade_unit_id": "gp-13-19",
                "asset_id": "asset-15",
                "preview_sha256": "h15",
                "facade_style": "baroque",
                "facade_observation": "Central pediment",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
        ]
        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path)
        leakage = report["group_leakage_audit"]
        assert "gp-005" in leakage["multi_image_units"]
        assert "gp-13-19" in leakage["multi_record_units"]
        assert set(leakage["multi_record_units"]["gp-13-19"]) == {"014", "015"}

        # Simulate naive split leakage test: put asset-5a in train, asset-5b in test
        naive_train = [rows[0]]
        naive_test = [rows[1]]
        naive_leak = check_split_leakage(naive_train, naive_test)
        assert naive_leak["leaked_facade_units"] == ["gp-005"]
        assert naive_leak["leaked_buildings"] == ["005"]

        # Simulate naive split leakage across multi-record unit: 014 in train, 015 in test
        unit_leak = check_split_leakage([rows[2]], [rows[3]])
        assert unit_leak["leaked_facade_units"] == ["gp-13-19"]

        # In deterministic connected group split, zero leakage occurs
        split = report["split_feasibility"]
        assert split["split_leakage_detected"] is False
        assert split["leakage_details"]["leaked_facade_units"] == []
        assert split["leakage_details"]["leaked_buildings"] == []


def test_repeated_image_checksum_leakage() -> None:
    """Identical image checksums across records must be flagged and never split across folds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "dup_hashes.csv"
        rows = [
            {
                "source_id": "001",
                "facade_unit_id": "gp-001",
                "asset_id": "asset-1",
                "preview_sha256": "duplicate_sha256_abcdef",
                "facade_style": "baroque",
                "facade_observation": "Obs 1",
                "reviewer": "Bob",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
            {
                "source_id": "002",
                "facade_unit_id": "gp-002",
                "asset_id": "asset-2",
                "preview_sha256": "duplicate_sha256_abcdef",
                "facade_style": "baroque",
                "facade_observation": "Obs 2",
                "reviewer": "Bob",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            },
        ]
        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path)
        leakage = report["group_leakage_audit"]
        assert leakage["duplicate_checksums_count"] == 1
        assert "duplicate_sha256_abcdef" in leakage["duplicate_checksums"]

        # Direct check_split_leakage flags cross-fold identical hashes
        split_leak = check_split_leakage([rows[0]], [rows[1]])
        assert split_leak["leaked_image_checksums"] == ["duplicate_sha256_abcdef"]

        # Connected group definition binds them into a single connected group
        groups = find_connected_groups(rows)
        assert len(groups) == 1
        assert set(groups[0]["units"]) == {"gp-001", "gp-002"}


def test_inadequate_split_class_coverage() -> None:
    """Singleton units for a style class must trigger explicit inadequacy statements."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "inadequate_coverage.csv"
        # 3 units of baroque, but only 1 unit of renaissance-inspired
        rows = [
            {
                "source_id": f"00{i}",
                "facade_unit_id": f"gp-00{i}",
                "asset_id": f"asset-b-{i}",
                "preview_sha256": f"hb{i}",
                "facade_style": "baroque",
                "facade_observation": f"Baroque gable {i}",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            }
            for i in range(1, 4)
        ] + [
            {
                "source_id": "026",
                "facade_unit_id": "gp-026",
                "asset_id": "asset-r-26",
                "preview_sha256": "hr26",
                "facade_style": "renaissance-inspired",
                "facade_observation": "Dormer windows",
                "reviewer": "Alice",
                "reviewed_at": "2026-09-20T10:00:00Z",
                "confidence": "high",
            }
        ]
        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path)
        readiness = report["label_readiness"]
        split = report["split_feasibility"]

        assert readiness["per_class_unique_units"]["renaissance-inspired"] == 1
        assert readiness["per_class_unique_units"]["baroque"] == 3
        assert split["is_feasible"] is False
        assert "INSUFFICIENT DATA FOR MEANINGFUL HELD-OUT RECOGNITION SCORE" in split["summary_verdict"]
        assert any("renaissance-inspired" in r and "< 2" in r for r in split["inadequacy_reasons"])


def test_feasible_split_scenario() -> None:
    """A dataset with sufficient units per class should produce a valid leak-free group split."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "feasible.csv"
        rows: list[dict[str, str]] = []
        # 4 units of baroque (8 images)
        for i in range(1, 5):
            for sub in ("a", "b"):
                rows.append({
                    "source_id": f"10{i}",
                    "facade_unit_id": f"gp-baroque-{i}",
                    "asset_id": f"asset-b-{i}-{sub}",
                    "preview_sha256": f"hash-b-{i}-{sub}",
                    "facade_style": "baroque",
                    "facade_observation": "Baroque features",
                    "reviewer": "Carol",
                    "reviewed_at": "2026-09-20T10:00:00Z",
                    "confidence": "high",
                })
        # 4 units of classical french (8 images)
        for i in range(1, 5):
            for sub in ("a", "b"):
                rows.append({
                    "source_id": f"20{i}",
                    "facade_unit_id": f"gp-classical-{i}",
                    "asset_id": f"asset-c-{i}-{sub}",
                    "preview_sha256": f"hash-c-{i}-{sub}",
                    "facade_style": "classical french",
                    "facade_observation": "Classical pediment",
                    "reviewer": "Carol",
                    "reviewed_at": "2026-09-20T10:00:00Z",
                    "confidence": "high",
                })

        write_test_csv(csv_path, rows)

        report = audit_facade_dataset(csv_path, test_ratio=0.25, seed=7)
        readiness = report["label_readiness"]
        split = report["split_feasibility"]

        assert readiness["reviewed_rows_count"] == 16
        assert readiness["per_class_unique_units"] == {"baroque": 4, "classical french": 4}
        assert split["is_feasible"] is True
        assert split["split_leakage_detected"] is False
        assert split["train_row_count"] > 0
        assert split["test_row_count"] > 0
        assert "baroque" in split["train_class_counts"]
        assert "classical french" in split["train_class_counts"]
        assert "baroque" in split["test_class_counts"]
        assert "classical french" in split["test_class_counts"]


def test_prototype_committed_dataset_audit() -> None:
    """The committed dataset must be audited for provenance, pending state, and lack of leakage."""
    assert COMMITTED_CSV.is_file(), f"Committed CSV not found at {COMMITTED_CSV}"
    report = audit_facade_dataset(COMMITTED_CSV)
    prov = report["dataset_provenance"]
    weak = report["weak_label_audit"]
    readiness = report["label_readiness"]
    split = report["split_feasibility"]

    assert prov["total_rows"] == 72
    assert prov["unique_facade_units_count"] == 27
    assert prov["unique_buildings_count"] == 27
    assert prov["unique_image_assets_count"] == 72
    assert prov["unique_image_checksums_count"] == 72
    assert len(prov["csv_sha256"]) == 64

    assert weak["rows_with_weak_label"] == 67
    assert readiness["reviewed_rows_count"] == 0
    assert readiness["pending_rows_count"] == 72
    assert readiness["incomplete_review_rows_count"] == 0
    assert readiness["invalid_styles_count"] == 0

    assert split["is_feasible"] is False
    assert "INSUFFICIENT DATA FOR MEANINGFUL HELD-OUT RECOGNITION SCORE" in split["summary_verdict"]
    assert split["split_leakage_detected"] is False

    # Formatted report generates cleanly
    text = format_audit_report(report)
    assert "THREE AGES — AUDITABLE DATASET EVALUATION & READINESS REPORT" in text
    assert "INSUFFICIENT DATA" in text


if __name__ == "__main__":
    test_pending_rows_audit()
    test_weak_label_kinds_are_separated()
    test_weak_label_isolation()
    test_repeated_building_leakage()
    test_repeated_image_checksum_leakage()
    test_inadequate_split_class_coverage()
    test_feasible_split_scenario()
    test_prototype_committed_dataset_audit()
    print("All facade dataset audit tests passed.")
