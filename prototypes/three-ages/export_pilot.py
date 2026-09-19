#!/usr/bin/env python3
"""Export the source-linked Three Ages pilot as review worksheets.

Existing human-entered review columns are preserved when their evidence
provenance still matches the pilot. Use --reset-reviews only when those
annotations should deliberately be discarded.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

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
    "identity_note",
    "identity_evidence_count",
    "identity_evidence_ids",
    "identity_evidence_urls",
    "next_step",
    "image_evidence_count",
    "image_evidence_ids",
    "image_evidence_epochs",
    "image_evidence_urls",
]

IMAGE_FIELDS = [
    "source_id",
    "name",
    "address",
    "asset_id",
    "epoch",
    "source_url",
    "image_url",
    "preview",
    "preview_sha256",
    "licence",
    "credit",
    "source_observation",
    "annotation_status",
    "identity_note",
    "facade_observation",
    "structural_observation",
    "reviewer",
    "reviewed_at",
    "confidence",
]
REVIEW_FIELDS = [
    "facade_observation",
    "structural_observation",
    "reviewer",
    "reviewed_at",
    "confidence",
]
PROVENANCE_FIELDS = [field for field in IMAGE_FIELDS if field not in REVIEW_FIELDS and field != "annotation_status"]

STRUCTURAL_FIELDS = [
    "source_id",
    "name",
    "address",
    "comparison_id",
    "area_asset_ids",
    "area_epochs",
    "area_source_urls",
    "area_image_urls",
    "area_previews",
    "area_preview_sha256",
    "area_licences",
    "area_credits",
    "case_latitude",
    "case_longitude",
    "crop_source_center_pixels",
    "crop_box_pixels",
    "crop_size_pixels",
    "case_crop_previews",
    "case_crop_pixel_sha256",
    "source_observation",
    "annotation_status",
    "identity_note",
    "identity_evidence_ids",
    "identity_evidence_urls",
    "identity_evidence_observations",
    "structural_observation",
    "reviewer",
    "reviewed_at",
    "confidence",
]
STRUCTURAL_REVIEW_FIELDS = ["structural_observation", "reviewer", "reviewed_at", "confidence"]
STRUCTURAL_PROVENANCE_FIELDS = [
    field for field in STRUCTURAL_FIELDS
    if field not in STRUCTURAL_REVIEW_FIELDS and field != "annotation_status"
]

REGISTER_FIELDS = [
    "source_id",
    "name",
    "address",
    "claim_id",
    "reported_value",
    "claim_status",
    "date_semantics",
    "source_comparison",
    "source_kind",
    "source_record_id",
    "source_url",
    "source_note",
    "city_history",
    "identity_note",
    "annotation_status",
    "register_decision",
    "register_observation",
    "reviewer",
    "reviewed_at",
    "confidence",
]
REGISTER_REVIEW_FIELDS = ["register_decision", "register_observation", "reviewer", "reviewed_at", "confidence"]
REGISTER_PROVENANCE_FIELDS = [
    field for field in REGISTER_FIELDS
    if field not in REGISTER_REVIEW_FIELDS and field != "annotation_status"
]
REGISTER_DECISIONS = {
    "accept proxy for MVP",
    "retain as reconstruction evidence",
    "reject source mapping",
}


def text(value: object) -> str:
    return "" if value is None else str(value)


def review_key(row: dict[str, object]) -> tuple[str, str]:
    return text(row.get("source_id")), text(row.get("asset_id"))


def read_existing_reviews(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"source_id", "asset_id", *REVIEW_FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"existing image-review worksheet is missing required columns: {sorted(missing)}")
        rows: dict[tuple[str, str], dict[str, str]] = {}
        for row in reader:
            key = review_key(row)
            if key in rows:
                raise RuntimeError(f"duplicate image-review row for {key}")
            rows[key] = row
        return rows


def validate_review(row: dict[str, object]) -> None:
    values = {field: text(row.get(field)).strip() for field in REVIEW_FIELDS}
    if not any(values.values()):
        return
    source_id, asset_id = review_key(row)
    if not asset_id:
        raise RuntimeError(f"cannot review {source_id}: no historical image asset is attached")
    if not (values["facade_observation"] or values["structural_observation"]):
        raise RuntimeError(f"review {source_id}/{asset_id} needs a facade or structural observation")
    for field in ("reviewer", "reviewed_at", "confidence"):
        if not values[field]:
            raise RuntimeError(f"review {source_id}/{asset_id} is missing {field}")
    if values["confidence"] not in {"low", "medium", "high"}:
        raise RuntimeError(f"review {source_id}/{asset_id} confidence must be low, medium or high")
    try:
        datetime.fromisoformat(values["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"review {source_id}/{asset_id} reviewed_at must be ISO 8601") from error


def preserve_review(generated: dict[str, object], existing: dict[str, str] | None) -> dict[str, object]:
    if not existing or not any(existing.get(field, "").strip() for field in REVIEW_FIELDS):
        validate_review(generated)
        return generated
    mismatches = [field for field in PROVENANCE_FIELDS if text(generated.get(field)) != existing.get(field, "")]
    if mismatches:
        key = review_key(generated)
        raise RuntimeError(f"refusing to attach review {key} after provenance changed: {mismatches}")
    generated.update({field: existing.get(field, "") for field in REVIEW_FIELDS})
    generated["annotation_status"] = "reviewed image annotation"
    validate_review(generated)
    return generated


def structural_review_key(row: dict[str, object]) -> tuple[str, str]:
    return text(row.get("source_id")), text(row.get("comparison_id"))


def read_existing_structural_reviews(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"source_id", "comparison_id", *STRUCTURAL_REVIEW_FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"existing structural-review worksheet is missing required columns: {sorted(missing)}")
        rows: dict[tuple[str, str], dict[str, str]] = {}
        for row in reader:
            key = structural_review_key(row)
            if key in rows:
                raise RuntimeError(f"duplicate structural-review row for {key}")
            rows[key] = row
        return rows


def validate_structural_review(row: dict[str, object]) -> None:
    values = {field: text(row.get(field)).strip() for field in STRUCTURAL_REVIEW_FIELDS}
    if not any(values.values()):
        return
    source_id, comparison_id = structural_review_key(row)
    if not comparison_id:
        raise RuntimeError(f"cannot review {source_id}: no structural comparison is attached")
    for field in STRUCTURAL_REVIEW_FIELDS:
        if not values[field]:
            raise RuntimeError(f"structural review {source_id}/{comparison_id} is missing {field}")
    if values["confidence"] not in {"low", "medium", "high"}:
        raise RuntimeError(f"structural review {source_id}/{comparison_id} confidence must be low, medium or high")
    try:
        datetime.fromisoformat(values["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"structural review {source_id}/{comparison_id} reviewed_at must be ISO 8601") from error


def preserve_structural_review(generated: dict[str, object], existing: dict[str, str] | None) -> dict[str, object]:
    if not existing or not any(existing.get(field, "").strip() for field in STRUCTURAL_REVIEW_FIELDS):
        validate_structural_review(generated)
        return generated
    mismatches = [
        field for field in STRUCTURAL_PROVENANCE_FIELDS
        if text(generated.get(field)) != existing.get(field, "")
    ]
    if mismatches:
        key = structural_review_key(generated)
        raise RuntimeError(f"refusing to attach structural review {key} after provenance changed: {mismatches}")
    generated.update({field: existing.get(field, "") for field in STRUCTURAL_REVIEW_FIELDS})
    generated["annotation_status"] = "reviewed structural comparison"
    validate_structural_review(generated)
    return generated


def register_review_key(row: dict[str, object]) -> tuple[str, str]:
    return text(row.get("source_id")), text(row.get("claim_id"))


def read_existing_register_reviews(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"source_id", "claim_id", *REGISTER_REVIEW_FIELDS}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise RuntimeError(f"existing register-review worksheet is missing required columns: {sorted(missing)}")
        rows: dict[tuple[str, str], dict[str, str]] = {}
        for row in reader:
            key = register_review_key(row)
            if key in rows:
                raise RuntimeError(f"duplicate register-review row for {key}")
            rows[key] = row
        return rows


def validate_register_review(row: dict[str, object]) -> None:
    values = {field: text(row.get(field)).strip() for field in REGISTER_REVIEW_FIELDS}
    if not any(values.values()):
        return
    source_id, claim_id = register_review_key(row)
    if not claim_id:
        raise RuntimeError(f"cannot review {source_id}: no register claim is attached")
    for field in REGISTER_REVIEW_FIELDS:
        if not values[field]:
            raise RuntimeError(f"register review {source_id}/{claim_id} is missing {field}")
    if values["register_decision"] not in REGISTER_DECISIONS:
        raise RuntimeError(f"register review {source_id}/{claim_id} has an invalid decision")
    if values["confidence"] not in {"low", "medium", "high"}:
        raise RuntimeError(f"register review {source_id}/{claim_id} confidence must be low, medium or high")
    try:
        datetime.fromisoformat(values["reviewed_at"].replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"register review {source_id}/{claim_id} reviewed_at must be ISO 8601") from error


def preserve_register_review(generated: dict[str, object], existing: dict[str, str] | None) -> dict[str, object]:
    if not existing or not any(existing.get(field, "").strip() for field in REGISTER_REVIEW_FIELDS):
        validate_register_review(generated)
        return generated
    mismatches = [
        field for field in REGISTER_PROVENANCE_FIELDS
        if text(generated.get(field)) != existing.get(field, "")
    ]
    if mismatches:
        key = register_review_key(generated)
        raise RuntimeError(f"refusing to attach register review {key} after provenance changed: {mismatches}")
    generated.update({field: existing.get(field, "") for field in REGISTER_REVIEW_FIELDS})
    generated["annotation_status"] = "reviewed register semantics"
    validate_register_review(generated)
    return generated


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DATA, help="directory containing the pilot data and exports")
    parser.add_argument("--reset-reviews", action="store_true", help="deliberately clear human-entered facade, structural and register review fields")
    args = parser.parse_args()

    data = args.data_dir
    output = data / "three-ages-pilot-export.csv"
    image_output = data / "three-ages-image-review.csv"
    review_output = data / "three-ages-image-reviews.json"
    structural_output = data / "three-ages-structural-review.csv"
    structural_review_output = data / "three-ages-structural-reviews.json"
    register_output = data / "three-ages-register-review.csv"
    register_review_output = data / "three-ages-register-reviews.json"
    source = json.loads((data / "grand-place-buildings.json").read_text())
    pilot = json.loads((data / "three-ages-pilot.json").read_text())
    structural_crops = json.loads((data / "three-ages-structural-crops.json").read_text())
    sources = {str(record["id"]): record for record in source["records"]}
    crop_records = structural_crops.get("records", [])
    crops_by_source = {str(record["source_id"]): record for record in crop_records}
    if len(crops_by_source) != len(crop_records):
        raise RuntimeError("structural crop manifest contains duplicate source ids")

    pilot_rows = []
    for case in pilot["records"]:
        record = sources[case["source_id"]]
        identity_evidence = case.get("identity_evidence", [])
        image_evidence = case.get("image_evidence") or []
        pilot_rows.append({
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
            "identity_note": case.get("identity_note", ""),
            "identity_evidence_count": len(identity_evidence),
            "identity_evidence_ids": ";".join(f"{item.get('source_kind', '')}:{item.get('record_id', '')}" for item in identity_evidence),
            "identity_evidence_urls": ";".join(text(item.get("source_url")) for item in identity_evidence),
            "next_step": case["next_step"],
            "image_evidence_count": len(image_evidence),
            "image_evidence_ids": ";".join(str(asset.get("asset_id", "")) for asset in image_evidence),
            "image_evidence_epochs": ";".join(str(asset.get("epoch", "")) for asset in image_evidence),
            "image_evidence_urls": ";".join(asset.get("source_url", "") for asset in image_evidence),
        })

    register_existing = {} if args.reset_reviews else read_existing_register_reviews(register_output)
    register_rows = []
    register_keys = set()
    for case in pilot["records"]:
        record = sources[case["source_id"]]
        claim = case["register"]
        claim_source = claim.get("source", {})
        row = {
            "source_id": case["source_id"],
            "name": record.get("name", ""),
            "address": record.get("address", ""),
            "claim_id": f"register-{case['source_id']}",
            "reported_value": claim.get("value", ""),
            "claim_status": claim.get("status", ""),
            "date_semantics": claim.get("date_semantics", ""),
            "source_comparison": claim.get("source_comparison", ""),
            "source_kind": claim_source.get("kind", ""),
            "source_record_id": claim_source.get("qid") or claim_source.get("inventory_id", ""),
            "source_url": claim_source.get("url") or claim_source.get("claim_url", ""),
            "source_note": claim.get("note", ""),
            "city_history": record.get("history", ""),
            "identity_note": case.get("identity_note", ""),
            "annotation_status": "proxy semantics; no reviewer decision",
            "register_decision": "",
            "register_observation": "",
            "reviewer": "",
            "reviewed_at": "",
            "confidence": "",
        }
        key = register_review_key(row)
        register_keys.add(key)
        register_rows.append(preserve_register_review(row, register_existing.get(key)))

    removed_register_reviews = [
        key for key, row in register_existing.items()
        if key not in register_keys and any(row.get(field, "").strip() for field in REGISTER_REVIEW_FIELDS)
    ]
    if removed_register_reviews:
        raise RuntimeError(f"refusing to discard register reviews for removed claims: {removed_register_reviews}")

    existing_reviews = {} if args.reset_reviews else read_existing_reviews(image_output)
    image_rows = []
    generated_keys = set()
    for case in pilot["records"]:
        record = sources[case["source_id"]]
        assets = case.get("image_evidence") or [None]
        for asset in assets:
            asset = asset or {}
            row = {
                "source_id": case["source_id"],
                "name": record.get("name", ""),
                "address": record.get("address", ""),
                "asset_id": asset.get("asset_id", ""),
                "epoch": asset.get("epoch", ""),
                "source_url": asset.get("source_url", ""),
                "image_url": asset.get("image_url", ""),
                "preview": asset.get("preview", ""),
                "preview_sha256": asset.get("preview_sha256", ""),
                "licence": asset.get("licence", ""),
                "credit": asset.get("credit", ""),
                "source_observation": asset.get("observation", "No permitted historical preview is attached."),
                "annotation_status": asset.get("annotation_status", "pending historical source"),
                "identity_note": case.get("identity_note", ""),
                "facade_observation": "",
                "structural_observation": "",
                "reviewer": "",
                "reviewed_at": "",
                "confidence": "",
            }
            key = review_key(row)
            generated_keys.add(key)
            image_rows.append(preserve_review(row, existing_reviews.get(key)))

    removed_reviews = [
        key for key, row in existing_reviews.items()
        if key not in generated_keys and any(row.get(field, "").strip() for field in REVIEW_FIELDS)
    ]
    if removed_reviews:
        raise RuntimeError(f"refusing to discard reviews for removed evidence rows: {removed_reviews}")

    area_assets = pilot.get("area_image_evidence", [])
    if len(area_assets) < 2:
        raise RuntimeError("structural review requires at least two area image epochs")
    comparison_id = "grand-place-1930-1935-to-2022"
    structural_existing = {} if args.reset_reviews else read_existing_structural_reviews(structural_output)
    structural_rows = []
    structural_keys = set()
    for case in pilot["records"]:
        record = sources[case["source_id"]]
        identity_evidence = case.get("identity_evidence", [])
        crop_record = crops_by_source.get(case["source_id"])
        if not crop_record:
            raise RuntimeError(f"pilot case {case['source_id']} has no structural crop record")
        crop_assets = crop_record.get("assets", [])
        if [text(asset.get("asset_id")) for asset in crop_assets] != [text(asset.get("asset_id")) for asset in area_assets]:
            raise RuntimeError(f"structural crop epochs do not match area evidence for {case['source_id']}")
        center = crop_record["source_center_pixels"]
        box = crop_record["crop_box_pixels"]
        row = {
            "source_id": case["source_id"],
            "name": record.get("name", ""),
            "address": record.get("address", ""),
            "comparison_id": comparison_id,
            "area_asset_ids": ";".join(text(asset.get("asset_id")) for asset in area_assets),
            "area_epochs": ";".join(text(asset.get("epoch")) for asset in area_assets),
            "area_source_urls": ";".join(text(asset.get("source_url")) for asset in area_assets),
            "area_image_urls": ";".join(text(asset.get("image_url")) for asset in area_assets),
            "area_previews": ";".join(text(asset.get("preview")) for asset in area_assets),
            "area_preview_sha256": ";".join(text(asset.get("preview_sha256")) for asset in area_assets),
            "area_licences": ";".join(text(asset.get("licence")) for asset in area_assets),
            "area_credits": ";".join(text(asset.get("credit")) for asset in area_assets),
            "case_latitude": crop_record["latitude"],
            "case_longitude": crop_record["longitude"],
            "crop_source_center_pixels": f"{center['x']},{center['y']}",
            "crop_box_pixels": f"{box['left']},{box['top']},{box['right']},{box['bottom']}",
            "crop_size_pixels": structural_crops["crop_size_pixels"],
            "case_crop_previews": ";".join(text(asset.get("crop_preview")) for asset in crop_assets),
            "case_crop_pixel_sha256": ";".join(text(asset.get("pixel_sha256")) for asset in crop_assets),
            "source_observation": "Aligned building-centred crops from the 1930–1935, 1996 and 2022 pilot-area orthos provide structural context; no case-level change is assigned before review.",
            "annotation_status": "area comparison; no reviewer annotation",
            "identity_note": case.get("identity_note", ""),
            "identity_evidence_ids": ";".join(f"{item.get('source_kind', '')}:{item.get('record_id', '')}" for item in identity_evidence),
            "identity_evidence_urls": ";".join(text(item.get("source_url")) for item in identity_evidence),
            "identity_evidence_observations": ";".join(text(item.get("observation")) for item in identity_evidence),
            "structural_observation": "",
            "reviewer": "",
            "reviewed_at": "",
            "confidence": "",
        }
        key = structural_review_key(row)
        structural_keys.add(key)
        structural_rows.append(preserve_structural_review(row, structural_existing.get(key)))

    removed_structural_reviews = [
        key for key, row in structural_existing.items()
        if key not in structural_keys and any(row.get(field, "").strip() for field in STRUCTURAL_REVIEW_FIELDS)
    ]
    if removed_structural_reviews:
        raise RuntimeError(f"refusing to discard structural reviews for removed comparisons: {removed_structural_reviews}")

    write_csv(output, FIELDS, pilot_rows)
    write_csv(image_output, IMAGE_FIELDS, image_rows)
    write_csv(structural_output, STRUCTURAL_FIELDS, structural_rows)
    write_csv(register_output, REGISTER_FIELDS, register_rows)
    completed_reviews = [
        {field: text(row[field]) for field in IMAGE_FIELDS}
        for row in image_rows
        if any(text(row.get(field)).strip() for field in REVIEW_FIELDS)
    ]
    write_json(review_output, {
        "source": image_output.name,
        "status": "completed image reviews" if completed_reviews else "no completed image reviews",
        "record_count": len(completed_reviews),
        "records": completed_reviews,
    })
    completed_structural_reviews = [
        {field: text(row[field]) for field in STRUCTURAL_FIELDS}
        for row in structural_rows
        if any(text(row.get(field)).strip() for field in STRUCTURAL_REVIEW_FIELDS)
    ]
    write_json(structural_review_output, {
        "source": structural_output.name,
        "status": "completed structural reviews" if completed_structural_reviews else "no completed structural reviews",
        "record_count": len(completed_structural_reviews),
        "records": completed_structural_reviews,
    })
    completed_register_reviews = [
        {field: text(row[field]) for field in REGISTER_FIELDS}
        for row in register_rows
        if any(text(row.get(field)).strip() for field in REGISTER_REVIEW_FIELDS)
    ]
    write_json(register_review_output, {
        "source": register_output.name,
        "status": "completed register reviews" if completed_register_reviews else "no completed register reviews",
        "record_count": len(completed_register_reviews),
        "records": completed_register_reviews,
    })
    preserved = len(completed_reviews)
    structural_preserved = len(completed_structural_reviews)
    register_preserved = len(completed_register_reviews)

    def display_path(path: Path) -> Path:
        try:
            return path.relative_to(ROOT)
        except ValueError:
            return path

    print(
        "wrote " + ", ".join(str(display_path(path)) for path in (
            output, image_output, review_output, structural_output, structural_review_output,
            register_output, register_review_output,
        ))
    )
    if preserved:
        print(f"preserved {preserved} completed image review row(s)")
    if structural_preserved:
        print(f"preserved {structural_preserved} completed structural review row(s)")
    if register_preserved:
        print(f"preserved {register_preserved} completed register review row(s)")


if __name__ == "__main__":
    main()
