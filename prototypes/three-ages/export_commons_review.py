#!/usr/bin/env python3
"""Build the human-review worksheet for staged Commons facade photos.

Reads the agent-accepted matches in data/commons-photo-provenance.json (one
row per unique photo; photos covering several addresses list every case) and
writes:

1. data/commons-photo-review.csv — worksheet with provenance columns plus
   blank review fields (facade_label, facade_observation, reviewer,
   reviewed_at, confidence). Existing review entries are preserved, never
   overwritten.
2. data/commons-photo-reviews.json — compiled completed reviews (rows with a
   facade_label). Refuses to compile a review whose photo provenance
   (source_url, image_url, preview_sha256, title) changed since review.

ShareAlike status rides along per row; the training manifest decides
eligibility (weights-publication caveat recorded in the licence doc).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PROVENANCE = DATA / "commons-photo-provenance.json"
WORKSHEET = DATA / "commons-photo-review.csv"
COMPILED = DATA / "commons-photo-reviews.json"

PROVENANCE_COLUMNS = (
    "photo_id", "commons_file", "case_ids", "class_suggestions", "source_styles",
    "built_years", "fiche_urls", "addresses", "photo_view_scope", "photo_page_title",
    "source_url", "image_url", "preview", "preview_sha256",
    "licence", "sharealike", "credit", "attribution",
    "agent_verdict", "agent_verdict_reason",
)
REVIEW_COLUMNS = (
    "facade_label", "facade_observation", "reviewer", "reviewed_at", "confidence",
)
STATUS_COLUMN = "annotation_status"
PENDING_STATUS = "pending reviewer annotation"
REVIEWED_STATUS = "reviewed photo annotation"
ALL_COLUMNS = PROVENANCE_COLUMNS + REVIEW_COLUMNS + (STATUS_COLUMN,)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def unique_photo_rows(records: list[dict]) -> list[dict]:
    """Collapse match records to one row per staged photo."""
    photos: dict[str, dict] = {}
    for record in records:
        photo_id = record.get("photo_id")
        require(bool(photo_id), "commons provenance record without photo_id")
        row = photos.setdefault(photo_id, {
            "photo_id": photo_id,
            "commons_file": record.get("commons_file") or "",
            "case_ids": [], "class_suggestions": [], "source_styles": [], "built_years": [],
            "fiche_urls": [], "addresses": [],
            "photo_view_scope": record.get("photo_view_scope") or "",
            "photo_page_title": record.get("title") or "",
            "source_url": record.get("source_url") or "",
            "image_url": record.get("image_url") or "",
            "preview": record.get("preview") or "",
            "preview_sha256": record.get("preview_sha256") or "",
            "licence": record.get("licence") or "",
            "sharealike": record.get("sharealike") or "",
            "credit": record.get("credit") or "",
            "attribution": record.get("attribution") or "",
            "agent_verdict": record.get("agent_verdict") or "",
            "agent_verdict_reason": record.get("agent_verdict_reason") or "",
        })
        for key, value in (
            ("case_ids", record.get("case_id")),
            ("class_suggestions", record.get("class_suggestion")),
            ("source_styles", record.get("source_style")),
            ("built_years", record.get("built")),
            ("fiche_urls", record.get("fiche")),
        ):
            if value and value not in row[key]:
                row[key].append(value)
        address = f"{record.get('street') or ''} {record.get('number') or ''}".strip()
        if address and address not in row["addresses"]:
            row["addresses"].append(address)
        for key in ("source_url", "image_url", "preview_sha256", "licence"):
            require(row[key] == (record.get(key) or ""),
                    f"photo {photo_id} disagrees on {key} between cases")
    rows = []
    for row in photos.values():
        rows.append({**row,
                     **{k: "; ".join(row[k]) for k in
                        ("case_ids", "class_suggestions", "source_styles", "built_years",
                         "fiche_urls", "addresses")}})
    return sorted(rows, key=lambda r: r["photo_id"])


def read_worksheet(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8",
                                     dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ALL_COLUMNS), lineterminator="\n")
        writer.writeheader()
        writer.writerows([{column: row.get(column, "") for column in ALL_COLUMNS} for row in rows])
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def write_json(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def main(data_dir: Path = DATA) -> None:
    provenance_path = data_dir / "commons-photo-provenance.json"
    worksheet_path = data_dir / "commons-photo-review.csv"
    compiled_path = data_dir / "commons-photo-reviews.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    fresh = {row["photo_id"]: row for row in unique_photo_rows(provenance["records"])}

    existing = {}
    if worksheet_path.exists():
        for row in read_worksheet(worksheet_path):
            unknown = set(row.keys()) - set(ALL_COLUMNS)
            require(not unknown, f"worksheet has unknown columns in {worksheet_path}: {sorted(unknown)}")
            existing[row["photo_id"]] = {c: row.get(c, "") for c in ALL_COLUMNS}

    merged = []
    for photo_id, row in fresh.items():
        prior = existing.get(photo_id, {})
        merged_row = {column: row.get(column, "") for column in PROVENANCE_COLUMNS}
        for column in REVIEW_COLUMNS:
            merged_row[column] = prior.get(column, "")
        completed = bool(merged_row["facade_label"].strip())
        if prior and completed:
            mismatches = [c for c in PROVENANCE_COLUMNS if prior.get(c, "") != merged_row[c]]
            if mismatches:
                raise RuntimeError(
                    f"refusing to attach review {photo_id} after provenance changed: {mismatches}")
            merged_row[STATUS_COLUMN] = prior.get(STATUS_COLUMN, "") or REVIEWED_STATUS
        else:
            merged_row[STATUS_COLUMN] = REVIEWED_STATUS if completed else PENDING_STATUS
        merged.append(merged_row)

    removed = sorted(set(existing) - set(fresh))
    if removed and any(existing[pid]["facade_label"].strip() for pid in removed):
        raise RuntimeError(f"refusing to discard reviews for removed photos: {removed}")

    write_csv(worksheet_path, merged)
    completed_rows = [r for r in merged if r["facade_label"].strip()]
    write_json(compiled_path, {
        "source": "reviewer-completed rows of commons-photo-review.csv; provenance pinned per row",
        "record_count": len(completed_rows),
        "records": completed_rows,
    })
    print(f"worksheet: {len(merged)} photos ({len(completed_rows)} reviewed) -> {worksheet_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    sys.exit(main(args.data_dir))
