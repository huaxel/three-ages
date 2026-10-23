#!/usr/bin/env python3
"""Ingest researcher-supplied facade images into a local, non-committed cache.

This script never downloads anything. It exists because some institutional
sources (the Brussels architectural-inventory illustrations, for example) do
not grant bulk image reuse, so those pixels must stay outside the repository.

The workflow is:

  1. You download images yourself, under whatever terms you have accepted or
     been granted, into ``local/facade-inbox/``.
  2. You fill in one row per image in ``local/facade-manifest.csv``.
  3. You run this script. It validates the rights basis, hashes the file,
     copies it to ``local/facade-cache/`` and appends a provenance record to
     ``local/facade-local-records.json``.

Everything this script writes lives under ``local/``, which is gitignored, so
local pixels and their provenance cannot be committed to tracked evidence by
accident. Tracked evidence continues to come only from openly licensed
sources (Wikimedia Commons, KIK-IRPA CC BY 4.0).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOCAL = ROOT / "local"

MANIFEST_COLUMNS = [
    "file",
    "house_name",
    "grand_place_number",
    "source_url",
    "rights_basis",
    "credit",
    "capture_date",
]

# A rights basis must be stated explicitly. Anything else, including an
# unelaborated claim of academic or fair use, is refused rather than recorded.
ALLOWED_RIGHTS_BASIS = {
    "cc-by-4.0",
    "cc-by-sa-4.0",
    "cc-by-sa-3.0",
    "cc0",
    "public-domain",
    "written-permission",
    "personal-capture",
}

REFUSED_RIGHTS_BASIS = {
    "fair-use",
    "fair use",
    "academic-fair-use",
    "academic",
    "research-exemption",
    "unknown",
    "",
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}

MAX_LOCAL_BYTES = 60 * 1024 * 1024

# A download that is silently an HTML error page or a PDF renamed to .jpg would
# otherwise enter the cache and be hashed as if it were usable evidence.
MAGIC_BYTES = {
    "jpeg": ((0, b"\xff\xd8\xff"),),
    "png": ((0, b"\x89PNG\r\n\x1a\n"),),
    "tiff": ((0, b"II*\x00"), (0, b"MM\x00*")),
    "webp": ((0, b"RIFF"), (8, b"WEBP")),
}
SUFFIX_FORMAT = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".tif": "tiff",
    ".tiff": "tiff",
    ".webp": "webp",
}


def sniff_format(head: bytes) -> str | None:
    for name, checks in MAGIC_BYTES.items():
        if all(head[offset : offset + len(sig)] == sig for offset, sig in checks):
            return name
    return None


def write_manifest_template(manifest: Path) -> None:
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "file": "example-house.jpg",
                "house_name": "The She-Wolf",
                "grand_place_number": "5",
                "source_url": "https://monument.heritage.brussels/fr/Bruxelles_Pentagone/Grand-Place/5/31122",
                "rights_basis": "written-permission",
                "credit": "urban.brussels - Inventaire du patrimoine architectural",
                "capture_date": "2026-01-01",
            }
        )


def read_manifest(manifest: Path) -> list[dict[str, str]]:
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in MANIFEST_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"{manifest} is missing column(s): {', '.join(missing)}")
        return [row for row in reader if any((value or "").strip() for value in row.values())]


def read_records(records: Path) -> dict:
    if not records.exists():
        return {"note": "local-only provenance records; never committed", "records": []}
    return json.loads(records.read_text(encoding="utf-8"))


def normalise(value: str | None) -> str:
    return (value or "").strip()


def ingest_row(row: dict[str, str], existing: dict[str, dict], inbox: Path, cache: Path) -> tuple[str, str]:
    name = normalise(row.get("file"))
    if not name:
        return "skip", "row has no file name"

    # Metadata is validated before the file is required, so an unusable rights
    # basis is reported before any download effort is spent on that image.
    rights = normalise(row.get("rights_basis")).lower()
    if rights in REFUSED_RIGHTS_BASIS or rights not in ALLOWED_RIGHTS_BASIS:
        allowed = ", ".join(sorted(ALLOWED_RIGHTS_BASIS))
        return "reject", f"{name}: rights_basis {rights or '(blank)'!r} is not an explicit reuse basis; use one of: {allowed}"

    for field in ("house_name", "source_url", "credit"):
        if not normalise(row.get(field)):
            return "reject", f"{name}: {field} is required to record provenance"

    source = inbox / name
    if not source.exists():
        return "pending", f"{name} not in {inbox}/ yet"
    if source.suffix.lower() not in IMAGE_SUFFIXES:
        return "reject", f"{name} is not a supported image type"

    size = source.stat().st_size
    if size > MAX_LOCAL_BYTES:
        return "reject", f"{name} is {size:,} bytes, above the {MAX_LOCAL_BYTES:,} local limit"

    with source.open("rb") as handle:
        head = handle.read(16)
    detected = sniff_format(head)
    expected = SUFFIX_FORMAT[source.suffix.lower()]
    if detected is None:
        return "reject", f"{name} does not look like an image (a saved HTML page or PDF is a common cause)"
    if detected != expected:
        return "reject", f"{name} is named {source.suffix.lower()} but its content is {detected}"

    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()

    previous = existing.get(name)
    if previous and previous.get("sha256") == digest:
        return "unchanged", f"{name} already ingested"

    cache.mkdir(parents=True, exist_ok=True)
    cached = cache / f"{Path(name).stem}-{digest[:12]}{source.suffix.lower()}"
    shutil.copy2(source, cached)

    existing[name] = {
        "file": name,
        "cached_as": str(cached),
        "sha256": digest,
        "bytes": size,
        "house_name": normalise(row.get("house_name")),
        "grand_place_number": normalise(row.get("grand_place_number")),
        "source_url": normalise(row.get("source_url")),
        "rights_basis": rights,
        "credit": normalise(row.get("credit")),
        "capture_date": normalise(row.get("capture_date")),
        "ingested_on": date.today().isoformat(),
        "committed": False,
    }
    return "ingested", f"{name} -> {cached.name} [{rights}]"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--init", action="store_true", help="create the local manifest template and inbox, then exit")
    parser.add_argument("--list", action="store_true", help="show manifest status without copying anything")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_LOCAL),
        help="local working tree for the inbox, cache and records (default: <repo>/local)",
    )
    args = parser.parse_args()

    local = Path(args.data_dir).expanduser().resolve()
    inbox = local / "facade-inbox"
    cache = local / "facade-cache"
    manifest = local / "facade-manifest.csv"
    records = local / "facade-local-records.json"

    if args.init:
        inbox.mkdir(parents=True, exist_ok=True)
        if not manifest.exists():
            write_manifest_template(manifest)
        print(f"inbox:    {inbox}/")
        print(f"manifest: {manifest}")
        print("Drop downloaded images into the inbox, fill in one manifest row each, then rerun without --init.")
        return 0

    if not manifest.exists():
        raise SystemExit(f"{manifest} not found; run this script with --init first")
    inbox.mkdir(parents=True, exist_ok=True)

    rows = read_manifest(manifest)
    state = read_records(records)
    existing = {record["file"]: record for record in state["records"]}
    state["records"] = list(existing.values())

    counts = {"ingested": 0, "unchanged": 0, "pending": 0, "reject": 0, "skip": 0}
    for row in rows:
        status, message = ingest_row(row, existing, inbox, cache)
        counts[status] += 1
        if status != "unchanged" or not args.list:
            prefix = {"ingested": "  ok", "unchanged": "   =", "pending": " ...", "reject": "  !!", "skip": "-  "}[status]
            print(f"{prefix} {message}")

    state["records"] = sorted(existing.values(), key=lambda record: record["file"])
    state["updated_on"] = date.today().isoformat()
    records.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"\ningested {counts['ingested']}, unchanged {counts['unchanged']}, "
        f"pending {counts['pending']}, rejected {counts['reject']}"
    )
    print(f"local records: {records}")
    if counts["reject"]:
        print("Rejected rows were not copied. Fix the manifest and rerun.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
