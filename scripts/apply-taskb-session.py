#!/usr/bin/env python3
"""Apply a task-B workbench session to the review queue, never clobbering.

Usage: python3 scripts/apply-taskb-session.py taskb-session.json

For each record: the target row is found by building_id, its fingerprint
(djb2 of notice_excerpt + suggested_era, same as taskb_review.html) is
recomputed, and a mismatch refuses that record — the queue was regenerated
under the bundle. Rows that already carry a label or reviewer are skipped,
never overwritten. Only blank label fields are filled.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "local" / "training" / "taskb_queue.csv"


def djb2_utf16(text: str) -> str:
    """Match the workbench JS: djb2 over UTF-16 code units, hex."""
    h = 5381
    for i in range(0, len(text.encode("utf-16-le")), 2):
        unit = int.from_bytes(text.encode("utf-16-le")[i:i + 2], "little")
        h = ((h << 5) + h + unit) & 0xFFFFFFFF
    return format(h, "x")


def fingerprint(row: dict) -> str:
    return djb2_utf16((row.get("notice_excerpt") or "") + "|" + (row.get("suggested_era") or ""))


def main() -> None:
    session_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not session_path or not session_path.exists():
        raise SystemExit("usage: apply-taskb-session.py taskb-session.json")
    session = json.loads(session_path.read_text(encoding="utf-8"))
    if session.get("schema") != "taskb-session/1":
        raise SystemExit(f"unknown session schema: {session.get('schema')!r}")

    with open(QUEUE, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        fieldnames = reader.fieldnames or list(rows[0].keys())
    by_id = {r["building_id"]: r for r in rows}

    applied, skipped_labelled, stale = 0, [], []
    for rec in session["records"]:
        bid = rec["building_id"]
        row = by_id.get(bid)
        if row is None:
            stale.append((bid, "not in queue"))
            continue
        if fingerprint(row) != rec.get("fingerprint"):
            stale.append((bid, "queue regenerated under bundle"))
            continue
        if (row.get("construction_era") or "").strip() or (row.get("reviewer") or "").strip():
            skipped_labelled.append(bid)
            continue
        row["construction_era"] = rec["construction_era"]
        row["phase_years"] = rec.get("phase_years", "")
        row["evidence"] = rec.get("evidence", "")
        row["reviewer"] = rec.get("reviewer", "")
        row["reviewed_at"] = rec.get("reviewed_at", "")
        row["confidence"] = rec.get("confidence", "")
        if "depicts_building" in fieldnames:
            row["depicts_building"] = rec.get("depicts_building", "yes")
        applied += 1

    with open(QUEUE, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"applied {applied}; skipped already-labelled {len(skipped_labelled)} {skipped_labelled}; "
          f"refused stale {len(stale)} {stale}")


if __name__ == "__main__":
    main()
