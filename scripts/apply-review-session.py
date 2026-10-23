#!/usr/bin/env python3
"""Apply one browser review-session export to a new CSV worksheet copy."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

EXPORT_PILOT = Path(__file__).resolve().parent.parent / "prototypes" / "three-ages" / "export_pilot.py"


def _canonical_fields() -> dict[str, list[str]]:
    """Read the fingerprint field lists from the exporter so the two can never drift.

    A copy kept here previously omitted source_style_text, so every image session the
    browser workbench exported failed this tool's provenance check.
    """
    import runpy

    return runpy.run_path(str(EXPORT_PILOT))["SESSION_FINGERPRINT_FIELDS"]


FIELDS = _canonical_fields()


def _writable_fields() -> dict[str, list[str]]:
    import runpy

    return runpy.run_path(str(EXPORT_PILOT))["SESSION_WRITABLE_FIELDS"]


WRITABLE = _writable_fields()


def fingerprint(kind: str, row: dict[str, str]) -> str:
    return "|".join(f"{field}={row.get(field, '')}" for field in FIELDS[kind])


def key(kind: str, row: dict[str, str]) -> str:
    suffix = row.get("asset_id") or row.get("comparison_id") or row.get("claim_id")
    return f"{kind}:{row.get('source_id', '')}:{suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("worksheet", type=Path)
    parser.add_argument("output", type=Path, help="new CSV path; the input worksheet is never changed")
    parser.add_argument("--type", choices=sorted(FIELDS), required=True, help="worksheet type to apply")
    args = parser.parse_args()
    session = json.loads(args.session.read_text(encoding="utf-8"))
    kind = args.type
    records = [record for record in session.get("records", []) if record.get("type") == kind]
    if not records:
        raise SystemExit(f"session contains no {kind} records")
    with args.worksheet.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    by_key = {key(kind, row): row for row in rows}
    if len(by_key) != len(rows):
        raise SystemExit("worksheet contains duplicate review keys")
    for record in records:
        record_key = record.get("key", "")
        row = by_key.get(record_key)
        if row is None:
            raise SystemExit(f"session row is not present in worksheet: {record_key}")
        if record.get("fingerprint") != fingerprint(kind, row):
            raise SystemExit(f"provenance mismatch; refusing to apply {record_key}")
        submitted = record.get("fields", {})
        # Only review fields may be written. A session must not be able to rewrite the
        # provenance the fingerprint was just checked against.
        forbidden = sorted(set(submitted) - set(WRITABLE[kind]))
        if forbidden:
            raise SystemExit(
                f"session record {record_key} attempts to write non-review field(s): {', '.join(forbidden)}"
            )
        row.update({field: str(value) for field, value in submitted.items() if field in fieldnames})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.output} without modifying {args.worksheet}")


if __name__ == "__main__":
    main()
