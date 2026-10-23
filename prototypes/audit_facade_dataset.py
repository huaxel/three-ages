#!/usr/bin/env python3
"""Audit facade review dataset for label readiness, group leakage, and split feasibility.

This standalone audit treats source_style_text strictly as weak-label metadata
and never as ground truth. It audits reviewed labels against the controlled
vocabulary, checks for group leakage by facade_unit_id, building (source_id),
and image checksum (preview_sha256), and assesses whether held-out recognition
evaluation is statistically and methodologically feasible without training a model.
"""
from __future__ import annotations

import json

import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

CONTROLLED_STYLES = {
    "baroque",
    "classical french",
    "renaissance-inspired",
    "mixed",
    "other",
    "uncertain",
    "not assessable",
}

NON_TARGET_OR_AMBIGUOUS_STYLES = {
    "mixed",
    "other",
    "uncertain",
    "not assessable",
}

VALID_CONFIDENCES = {"low", "medium", "high"}

WEAK_LABEL_DISCLAIMER = (
    "EXPLICIT NOTICE: source_style_text / source_style_label is weak-label "
    "metadata derived from municipal descriptions or catalog notes. It must "
    "NEVER be treated as ground truth or used as an evaluation benchmark target."
)


def compute_file_sha256(path: Path) -> str:
    """Return SHA-256 hex digest of a file, or empty string if file missing."""
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_review_csv(path: Path) -> list[dict[str, str]]:
    """Read a facade review CSV, returning stripped string dictionaries."""
    if not path.is_file():
        raise FileNotFoundError(f"Review CSV not found: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"Review CSV has no header: {path}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def find_connected_groups(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Group rows into disjoint connected components by unit, building, and image hash.

    Any rows sharing a facade_unit_id, a source_id (building), or a preview_sha256
    must belong to the exact same group so that no split can separate them.
    """
    parent: dict[str, str] = {}

    def find(item: str) -> str:
        if item not in parent:
            parent[item] = item
        elif parent[item] != item:
            parent[item] = find(parent[item])
        return parent[item]

    def union(item1: str, item2: str) -> None:
        root1 = find(item1)
        root2 = find(item2)
        if root1 != root2:
            parent[root1] = root2

    for row in rows:
        unit = f"unit:{row.get('facade_unit_id') or row.get('source_id') or 'unknown'}"
        building = f"bldg:{row.get('source_id') or 'unknown'}"
        checksum = f"sha:{row.get('preview_sha256') or row.get('asset_id') or 'unknown'}"
        union(unit, building)
        union(unit, checksum)

    group_buckets: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        unit = f"unit:{row.get('facade_unit_id') or row.get('source_id') or 'unknown'}"
        root = find(unit)
        group_buckets.setdefault(root, []).append(row)

    groups: list[dict[str, Any]] = []
    for root, group_rows in group_buckets.items():
        units = sorted({r.get("facade_unit_id") or r.get("source_id") or "" for r in group_rows if r.get("facade_unit_id") or r.get("source_id")})
        buildings = sorted({r.get("source_id", "") for r in group_rows if r.get("source_id")})
        assets = sorted({r.get("asset_id", "") for r in group_rows if r.get("asset_id")})
        checksums = sorted({r.get("preview_sha256", "") for r in group_rows if r.get("preview_sha256")})
        # Determine group representative style if reviewed
        styles = sorted({r.get("facade_style", "").lower() for r in group_rows if r.get("facade_style", "").strip()})
        group_id = units[0] if units else root
        groups.append({
            "group_id": group_id,
            "units": units,
            "buildings": buildings,
            "assets": assets,
            "checksums": checksums,
            "rows": group_rows,
            "reviewed_styles": styles,
        })
    groups.sort(key=lambda g: g["group_id"])
    return groups


def check_split_leakage(train_rows: list[dict[str, str]], test_rows: list[dict[str, str]]) -> dict[str, list[str]]:
    """Verify that train and test splits share NO units, buildings, assets, or checksums."""
    train_units = {r.get("facade_unit_id") or r.get("source_id") for r in train_rows if r.get("facade_unit_id") or r.get("source_id")}
    test_units = {r.get("facade_unit_id") or r.get("source_id") for r in test_rows if r.get("facade_unit_id") or r.get("source_id")}
    leaked_units = sorted(train_units & test_units)

    train_buildings = {r.get("source_id") for r in train_rows if r.get("source_id")}
    test_buildings = {r.get("source_id") for r in test_rows if r.get("source_id")}
    leaked_buildings = sorted(train_buildings & test_buildings)

    train_assets = {r.get("asset_id") for r in train_rows if r.get("asset_id")}
    test_assets = {r.get("asset_id") for r in test_rows if r.get("asset_id")}
    leaked_assets = sorted(train_assets & test_assets)

    train_hashes = {r.get("preview_sha256") for r in train_rows if r.get("preview_sha256")}
    test_hashes = {r.get("preview_sha256") for r in test_rows if r.get("preview_sha256")}
    leaked_hashes = sorted(train_hashes & test_hashes)

    return {
        "leaked_facade_units": [u for u in leaked_units if u],
        "leaked_buildings": [b for b in leaked_buildings if b],
        "leaked_assets": [a for a in leaked_assets if a],
        "leaked_image_checksums": [h for h in leaked_hashes if h],
    }


def evaluate_group_split_feasibility(
    groups: list[dict[str, Any]],
    test_ratio: float = 0.2,
    seed: int = 42,
    min_units_per_class: int = 2,
    min_total_reviewed_units: int = 4,
) -> dict[str, Any]:
    """Assess whether a held-out group split is statistically feasible and construct it deterministically."""
    # Filter groups that contain at least one reviewed row with a target class
    reviewed_groups: list[dict[str, Any]] = []
    for g in groups:
        reviewed_in_group = [r for r in g["rows"] if r.get("facade_style", "").strip()]
        if reviewed_in_group:
            reviewed_groups.append(g)

    # Count reviewed units and per-class distribution across groups
    reviewed_units_count = sum(len(g["units"]) for g in reviewed_groups)
    class_to_groups: dict[str, list[dict[str, Any]]] = {}
    for g in reviewed_groups:
        for style in g["reviewed_styles"]:
            class_to_groups.setdefault(style, []).append(g)

    inadequacies: list[str] = []

    if not reviewed_groups:
        inadequacies.append("Zero reviewed rows or labels in dataset (all rows pending).")
    else:
        if reviewed_units_count < min_total_reviewed_units:
            inadequacies.append(
                f"Total reviewed facade units ({reviewed_units_count}) is below minimum "
                f"threshold ({min_total_reviewed_units}) required for held-out evaluation."
            )
        for style, g_list in class_to_groups.items():
            if style in NON_TARGET_OR_AMBIGUOUS_STYLES:
                continue
            unit_count = sum(len(g["units"]) for g in g_list)
            if unit_count < min_units_per_class:
                inadequacies.append(
                    f"Class '{style}' appears in only {unit_count} unique facade unit(s) "
                    f"(< {min_units_per_class}). A leak-free group split cannot represent "
                    f"this class in both training and held-out test sets without identity leakage."
                )

    is_feasible = (len(inadequacies) == 0)

    # Perform deterministic stratified group assignment
    train_groups: list[dict[str, Any]] = []
    test_groups: list[dict[str, Any]] = []
    assigned_group_ids: set[str] = set()

    if reviewed_groups and is_feasible:
        # Sort classes rarest first for balanced stratified allocation
        sorted_classes = sorted(
            [cls for cls in class_to_groups if cls not in NON_TARGET_OR_AMBIGUOUS_STYLES],
            key=lambda c: len(class_to_groups[c]),
        )
        for cls in sorted_classes:
            c_groups = class_to_groups[cls]
            # Order groups by deterministic hash
            c_groups_sorted = sorted(
                c_groups,
                key=lambda g: hashlib.sha256(f"{seed}:strat:{g['group_id']}".encode("utf-8")).hexdigest(),
            )
            # Count currently assigned to test for this class
            test_for_cls = [g for g in test_groups if cls in g["reviewed_styles"]]
            train_for_cls = [g for g in train_groups if cls in g["reviewed_styles"]]

            if not test_for_cls and len(c_groups) >= 2:
                # Need at least one group in test
                candidate = next((g for g in c_groups_sorted if g["group_id"] not in assigned_group_ids), None)
                if candidate:
                    test_groups.append(candidate)
                    assigned_group_ids.add(candidate["group_id"])

        # Assign remaining reviewed groups according to test_ratio
        for g in reviewed_groups:
            if g["group_id"] in assigned_group_ids:
                continue
            token = f"{seed}:{g['group_id']}:{','.join(g['units'])}"
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            normalized = (h % 10000) / 10000.0
            if normalized < test_ratio:
                test_groups.append(g)
            else:
                train_groups.append(g)
            assigned_group_ids.add(g["group_id"])
    else:
        # Fallback or unreviewed assignment
        for g in reviewed_groups if reviewed_groups else groups:
            token = f"{seed}:{g['group_id']}:{','.join(g['units'])}"
            h = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            normalized = (h % 10000) / 10000.0
            if normalized < test_ratio and (len(reviewed_groups) >= 2 or not reviewed_groups):
                test_groups.append(g)
            else:
                train_groups.append(g)

    # Fallback if all fell into one split
    if reviewed_groups and not test_groups and len(reviewed_groups) >= 2:
        test_groups.append(train_groups.pop())
    elif reviewed_groups and not train_groups and len(reviewed_groups) >= 2:
        train_groups.append(test_groups.pop())

    train_rows = [r for g in train_groups for r in g["rows"]]
    test_rows = [r for g in test_groups for r in g["rows"]]

    leakage = check_split_leakage(train_rows, test_rows)
    has_leakage = any(len(leaks) > 0 for leaks in leakage.values())

    # Count class representation in split
    def count_classes(rows: list[dict[str, str]]) -> dict[str, int]:
        c: dict[str, int] = {}
        for r in rows:
            st = r.get("facade_style", "").strip().lower()
            if st:
                c[st] = c.get(st, 0) + 1
        return c

    train_class_counts = count_classes(train_rows)
    test_class_counts = count_classes(test_rows)

    unrepresented_in_test = [cls for cls in train_class_counts if cls not in test_class_counts and cls not in NON_TARGET_OR_AMBIGUOUS_STYLES]
    unrepresented_in_train = [cls for cls in test_class_counts if cls not in train_class_counts and cls not in NON_TARGET_OR_AMBIGUOUS_STYLES]

    if unrepresented_in_test and is_feasible:
        is_feasible = False
        inadequacies.append(f"Classes unrepresented in held-out test split: {unrepresented_in_test}")
    if unrepresented_in_train and is_feasible:
        is_feasible = False
        inadequacies.append(f"Classes unrepresented in training split: {unrepresented_in_train}")

    if not is_feasible:
        summary_verdict = (
            "INSUFFICIENT DATA FOR MEANINGFUL HELD-OUT RECOGNITION SCORE: "
            + "; ".join(inadequacies)
        )
    else:
        summary_verdict = (
            "SUFFICIENT DATA FOR EVALUATION: Deterministic group split is leak-free "
            "and all target classes have held-out representation across independent facade units."
        )

    return {
        "is_feasible": is_feasible,
        "summary_verdict": summary_verdict,
        "inadequacy_reasons": inadequacies,
        "test_ratio_requested": test_ratio,
        "train_group_count": len(train_groups),
        "test_group_count": len(test_groups),
        "train_unit_count": sum(len(g["units"]) for g in train_groups),
        "test_unit_count": sum(len(g["units"]) for g in test_groups),
        "train_row_count": len(train_rows),
        "test_row_count": len(test_rows),
        "train_class_counts": train_class_counts,
        "test_class_counts": test_class_counts,
        "unrepresented_in_test": unrepresented_in_test,
        "unrepresented_in_train": unrepresented_in_train,
        "split_leakage_detected": has_leakage,
        "leakage_details": leakage,
    }


def audit_facade_dataset(
    csv_path: Path | str,
    rows: list[dict[str, str]] | None = None,
    test_ratio: float = 0.2,
    seed: int = 42,
    facade_units_path: Path | str | None = None,
) -> dict[str, Any]:
    """Execute complete dataset evaluation audit covering readiness, leakage, and split feasibility."""
    path = Path(csv_path)
    file_sha256 = compute_file_sha256(path) if rows is None and path.is_file() else "memory_or_synthetic"

    if rows is None:
        rows = load_review_csv(path)

    # A facade unit's record membership is declared in facade-units.json, not inferable from
    # the worksheet: a multi-record unit has rows under only one of its records, so deriving
    # membership from rows alone reports zero multi-record units and understates the grouping.
    declared_units_path = Path(facade_units_path) if facade_units_path else path.parent / "facade-units.json"
    declared_unit_records: dict[str, list[str]] = {}
    if declared_units_path.is_file():
        try:
            for unit in json.loads(declared_units_path.read_text(encoding="utf-8")).get("units", []):
                unit_id = str(unit.get("unit_id", ""))
                if unit_id:
                    declared_unit_records[unit_id] = [str(r) for r in unit.get("records", [])]
        except (ValueError, OSError):
            declared_unit_records = {}

    total_rows = len(rows)

    # 1. Identity and Group Structure
    all_units = sorted({r.get("facade_unit_id") or r.get("source_id") or "" for r in rows if r.get("facade_unit_id") or r.get("source_id")})
    all_buildings = sorted({r.get("source_id", "") for r in rows if r.get("source_id")})
    all_assets = sorted({r.get("asset_id", "") for r in rows if r.get("asset_id")})
    all_checksums = sorted({r.get("preview_sha256", "") for r in rows if r.get("preview_sha256")})

    # Group counts
    unit_to_assets: dict[str, list[str]] = {}
    unit_to_buildings: dict[str, list[str]] = {}
    checksum_to_rows: dict[str, list[int]] = {}
    asset_to_rows: dict[str, list[int]] = {}

    for idx, r in enumerate(rows):
        unit = r.get("facade_unit_id") or r.get("source_id") or ""
        bldg = r.get("source_id", "")
        asset = r.get("asset_id", "")
        csum = r.get("preview_sha256", "")

        if unit and asset:
            unit_to_assets.setdefault(unit, []).append(asset)
        if unit and bldg and bldg not in unit_to_buildings.get(unit, []):
            unit_to_buildings.setdefault(unit, []).append(bldg)
        if csum:
            checksum_to_rows.setdefault(csum, []).append(idx)
        if asset:
            asset_to_rows.setdefault(asset, []).append(idx)

    multi_image_units = {u: assets for u, assets in unit_to_assets.items() if len(assets) > 1}
    multi_record_units = {u: bldgs for u, bldgs in unit_to_buildings.items() if len(bldgs) > 1}
    declared_multi_record_units = {
        unit_id: records for unit_id, records in declared_unit_records.items() if len(records) > 1
    }
    duplicate_checksums = {c: idxs for c, idxs in checksum_to_rows.items() if len(idxs) > 1}
    duplicate_assets = {a: idxs for a, idxs in asset_to_rows.items() if len(idxs) > 1}

    # 2. Weak-Label Metadata Isolation
    # Check whether source_style_text or source_style_label is present
    weak_label_key = "source_style_text" if any("source_style_text" in r for r in rows) else "source_style_label"
    rows_with_weak_label = sum(1 for r in rows if r.get(weak_label_key, "").strip())
    weak_label_distribution: dict[str, int] = {}
    # source_style_text holds a curated style label for pilot rows and the City dataset's raw
    # facade description for supplemental rows. Aggregating them together compares a category
    # against paragraphs, so group by the recorded kind and summarise each population apart.
    weak_label_by_kind: dict[str, dict[str, int]] = {}
    weak_label_distinct_by_kind: dict[str, int] = {}
    for r in rows:
        val = r.get(weak_label_key, "").strip()
        if not val:
            continue
        kind = (r.get("source_label_kind") or "unrecorded").strip() or "unrecorded"
        weak_label_by_kind.setdefault(kind, {})
        weak_label_by_kind[kind][val] = weak_label_by_kind[kind].get(val, 0) + 1
        weak_label_distribution[val] = weak_label_distribution.get(val, 0) + 1
    for kind, counts in weak_label_by_kind.items():
        weak_label_distinct_by_kind[kind] = len(counts)

    # 3. Label Readiness & Verification
    reviewed_rows_list: list[dict[str, str]] = []
    incomplete_rows_list: list[tuple[int, str]] = []
    pending_rows_count = 0
    invalid_styles: list[tuple[int, str]] = []

    per_class_image_counts: dict[str, int] = {}
    per_class_units: dict[str, set[str]] = {}
    per_class_buildings: dict[str, set[str]] = {}

    for idx, r in enumerate(rows):
        style = r.get("facade_style", "").strip().lower()
        has_obs = bool(r.get("facade_observation", "").strip() or r.get("structural_observation", "").strip())
        has_meta = bool(r.get("reviewer", "").strip() and r.get("reviewed_at", "").strip() and r.get("confidence", "").strip())
        conf = r.get("confidence", "").strip().lower()

        # Check ISO 8601 date validity if set
        date_valid = True
        reviewed_at = r.get("reviewed_at", "").strip()
        if reviewed_at:
            try:
                datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            except ValueError:
                date_valid = False

        if style:
            if style not in CONTROLLED_STYLES:
                invalid_styles.append((idx, style))
            if not has_obs or not has_meta or conf not in VALID_CONFIDENCES or not date_valid:
                incomplete_rows_list.append((idx, f"style={style} but missing required observation/metadata/valid date"))
            else:
                reviewed_rows_list.append(r)
                per_class_image_counts[style] = per_class_image_counts.get(style, 0) + 1
                unit_id = r.get("facade_unit_id") or r.get("source_id") or ""
                bldg_id = r.get("source_id", "")
                if unit_id:
                    per_class_units.setdefault(style, set()).add(unit_id)
                if bldg_id:
                    per_class_buildings.setdefault(style, set()).add(bldg_id)
        else:
            pending_rows_count += 1

    reviewed_count = len(reviewed_rows_list)
    per_class_unique_units = {k: len(v) for k, v in per_class_units.items()}
    per_class_unique_buildings = {k: len(v) for k, v in per_class_buildings.items()}

    # 4. Group Structure & Split Feasibility
    groups = find_connected_groups(rows)
    split_report = evaluate_group_split_feasibility(
        groups,
        test_ratio=test_ratio,
        seed=seed,
    )

    is_ready_for_eval = (reviewed_count > 0 and len(incomplete_rows_list) == 0 and split_report["is_feasible"])

    return {
        "dataset_provenance": {
            "csv_path": str(path),
            "csv_sha256": file_sha256,
            "total_rows": total_rows,
            "unique_facade_units_count": len(all_units),
            "unique_buildings_count": len(all_buildings),
            "unique_image_assets_count": len(all_assets),
            "unique_image_checksums_count": len(all_checksums),
        },
        "weak_label_audit": {
            "weak_label_key": weak_label_key,
            "disclaimer": WEAK_LABEL_DISCLAIMER,
            "rows_with_weak_label": rows_with_weak_label,
            "weak_label_coverage_pct": round(rows_with_weak_label / total_rows * 100, 1) if total_rows else 0.0,
            "weak_label_distribution_top": sorted(weak_label_distribution.items(), key=lambda x: -x[1])[:10],
            "weak_label_kinds": {
                kind: {
                    "rows": sum(counts.values()),
                    "distinct_values": weak_label_distinct_by_kind.get(kind, 0),
                    "top": sorted(counts.items(), key=lambda x: -x[1])[:8],
                }
                for kind, counts in sorted(weak_label_by_kind.items())
            },
        },
        "label_readiness": {
            "is_ready_for_evaluation": is_ready_for_eval,
            "total_rows": total_rows,
            "reviewed_rows_count": reviewed_count,
            "pending_rows_count": pending_rows_count,
            "incomplete_review_rows_count": len(incomplete_rows_list),
            "invalid_styles_count": len(invalid_styles),
            "per_class_image_counts": per_class_image_counts,
            "per_class_unique_units": per_class_unique_units,
            "per_class_unique_buildings": per_class_unique_buildings,
        },
        "group_leakage_audit": {
            "multi_image_units_count": len(multi_image_units),
            "multi_image_units": {k: len(v) for k, v in multi_image_units.items()},
            "multi_record_units_count": len(multi_record_units),
            "multi_record_units": multi_record_units,
            "declared_multi_record_units_count": len(declared_multi_record_units),
            "declared_multi_record_units": declared_multi_record_units,
            "declared_unit_records_available": bool(declared_unit_records),
            "duplicate_checksums_count": len(duplicate_checksums),
            "duplicate_checksums": {k: len(v) for k, v in duplicate_checksums.items()},
            "duplicate_assets_count": len(duplicate_assets),
        },
        "split_feasibility": split_report,
    }


def format_audit_report(report: dict[str, Any]) -> str:
    """Format audit results as a human-readable text report."""
    prov = report["dataset_provenance"]
    weak = report["weak_label_audit"]
    readiness = report["label_readiness"]
    leakage = report["group_leakage_audit"]
    split = report["split_feasibility"]

    lines = [
        "=" * 78,
        "THREE AGES — AUDITABLE DATASET EVALUATION & READINESS REPORT",
        "=" * 78,
        f"CSV Path:                {prov['csv_path']}",
        f"CSV SHA-256:             {prov['csv_sha256']}",
        f"Total Records / Rows:    {prov['total_rows']}",
        f"Unique Facade Units:     {prov['unique_facade_units_count']}",
        f"Unique Buildings:        {prov['unique_buildings_count']}",
        f"Unique Image Assets:     {prov['unique_image_assets_count']}",
        f"Unique Image Hashes:     {prov['unique_image_checksums_count']}",
        "-" * 78,
        "WEAK-LABEL METADATA STATUS",
        f"Notice:                  {weak['disclaimer']}",
        f"Weak-label field:        {weak['weak_label_key']}",
        f"Weak-label coverage:     {weak['rows_with_weak_label']}/{prov['total_rows']} rows ({weak['weak_label_coverage_pct']}%)",
        *[
            f"  {kind}: {info['rows']} row(s), {info['distinct_values']} distinct value(s)"
            + (
                " — " + ", ".join(f"{value} x{count}" for value, count in info["top"])
                if info["distinct_values"] <= 8
                else ""
            )
            for kind, info in weak.get("weak_label_kinds", {}).items()
        ],
        "-" * 78,
        "LABEL READINESS AUDIT",
        f"Reviewed rows:           {readiness['reviewed_rows_count']}",
        f"Pending rows:            {readiness['pending_rows_count']}",
        f"Incomplete rows:         {readiness['incomplete_review_rows_count']}",
        f"Invalid styles:          {readiness['invalid_styles_count']}",
    ]

    if readiness["per_class_image_counts"]:
        lines.append("Per-class reviewed distribution:")
        for cls, count in readiness["per_class_image_counts"].items():
            units = readiness["per_class_unique_units"].get(cls, 0)
            bldgs = readiness["per_class_unique_buildings"].get(cls, 0)
            lines.append(f"  - {cls:<22}: {count:>2} images across {units:>2} unit(s), {bldgs:>2} building(s)")
    else:
        lines.append("Per-class reviewed distribution: None (0 reviewed visual labels)")

    lines.extend([
        "-" * 78,
        "GROUP LEAKAGE AUDIT",
        f"Multi-image facade units:   {leakage['multi_image_units_count']} unit(s) contain multiple images",
        f"Multi-record facade units:  {leakage['multi_record_units_count']} unit(s) span multiple building records (observed in worksheet)",
        f"Declared multi-record units: {leakage['declared_multi_record_units_count']} unit(s) span multiple City records (facade-units.json)"
        + ("" if leakage.get("declared_unit_records_available") else " — grouping not found, observed count is a lower bound"),
        f"Duplicate image checksums:  {leakage['duplicate_checksums_count']} duplicate hash(es)",
        f"Duplicate asset IDs:        {leakage['duplicate_assets_count']} duplicate asset(s)",
        "-" * 78,
        "DETERMINISTIC GROUP SPLIT FEASIBILITY & REPORTING",
        f"Feasible for held-out score: {'YES' if split['is_feasible'] else 'NO'}",
        f"Verdict: {split['summary_verdict']}",
    ])

    if split["inadequacy_reasons"]:
        lines.append("Specific Inadequacies:")
        for r in split["inadequacy_reasons"]:
            lines.append(f"  * {r}")

    lines.extend([
        f"Split Partitioning (test_ratio={split['test_ratio_requested']}):",
        f"  Train: {split['train_unit_count']} units, {split['train_row_count']} images, {split['train_group_count']} groups",
        f"  Test:  {split['test_unit_count']} units, {split['test_row_count']} images, {split['test_group_count']} groups",
        f"Cross-split leakage check:   {'FAIL (leakage detected)' if split['split_leakage_detected'] else 'PASS (zero leakage across units/bldgs/hashes)'}",
        "=" * 78,
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Three Ages prototype facade review dataset.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).resolve().parent / "three-ages" / "data" / "three-ages-image-review.csv",
        help="Path to facade image review CSV (default: prototypes/three-ages/data/three-ages-image-review.csv)",
    )
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Test ratio for group split (default: 0.2)")
    parser.add_argument("--seed", type=int, default=42, help="Seed for deterministic split (default: 42)")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    parser.add_argument("--check-readiness", action="store_true", help="Exit 1 if dataset is not ready for held-out evaluation")

    args = parser.parse_args()

    report = audit_facade_dataset(args.csv, test_ratio=args.test_ratio, seed=args.seed)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_audit_report(report))

    if args.check_readiness and not report["label_readiness"]["is_ready_for_evaluation"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
