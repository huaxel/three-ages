#!/usr/bin/env python3
"""Safely import reviewer-edited CSVs from the blind review ZIP.

Only independent-review fields are copied back. Evidence paths are translated
from archive-relative `evidence/...` paths and every other provenance field must
match the local template exactly. No ZIP member is extracted to disk.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

from export_independent_review import (
    BALAT_EVIDENCE, BALAT_OUTPUT, COMMONS_EVIDENCE, COMMONS_OUTPUT,
    IMAGE_EVIDENCE, IMAGE_OUTPUT, IMAGE_REVIEW, PHOTO_REVIEW,
    STRUCTURAL_EVIDENCE, STRUCTURAL_OUTPUT, STRUCTURAL_REVIEW,
)

DATA = Path(__file__).resolve().parent / "data"
SHEETS = {
    IMAGE_OUTPUT: ("three-ages-independent-image-review.csv", IMAGE_EVIDENCE, IMAGE_REVIEW, ("asset_id",), ("preview",)),
    STRUCTURAL_OUTPUT: ("three-ages-independent-structural-review.csv", STRUCTURAL_EVIDENCE, STRUCTURAL_REVIEW, ("source_id", "comparison_id"), ("case_crop_previews",)),
    BALAT_OUTPUT: ("balat-independent-photo-review.csv", BALAT_EVIDENCE, PHOTO_REVIEW, ("photo_id",), ("preview",)),
    COMMONS_OUTPUT: ("commons-independent-photo-review.csv", COMMONS_EVIDENCE, PHOTO_REVIEW, ("photo_id",), ("preview",)),
}


def rows_from_bytes(body: bytes, name: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        text = body.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise RuntimeError(f"{name} is not UTF-8 CSV") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        raise RuntimeError(f"{name} has no CSV header")
    return list(reader.fieldnames), list(reader)


def read_local(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"{path} has no CSV header")
        return list(reader.fieldnames), list(reader)


def write_csv_atomic(path: Path, fields: list[str], rows: list[dict[str, str]]) -> Path:
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=path.parent, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    result = Path(temporary.name)
    return result if result.is_absolute() else path.parent / result


def key_for(row: dict[str, str], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def localize_path(value: str) -> str:
    parts = value.split(";")
    localized = []
    for part in parts:
        prefix = "evidence/"
        if not part.startswith(prefix) or part.startswith("evidence/../"):
            raise RuntimeError(f"reviewer changed or malformed evidence path: {part}")
        localized.append(part[len(prefix):])
    return ";".join(localized)


def import_bundle(bundle: Path, data_dir: Path = DATA) -> list[Path]:
    with zipfile.ZipFile(bundle, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any(".." in Path(name).parts for name in names):
            raise RuntimeError("bundle contains duplicate or unsafe archive paths")
        manifest_name = "SHA256SUMS.json"
        if manifest_name not in names:
            raise RuntimeError("bundle is missing its SHA-256 manifest")
        try:
            checksums = json.loads(archive.read(manifest_name).decode("utf-8"))["files"]
        except (ValueError, KeyError, UnicodeDecodeError) as error:
            raise RuntimeError("bundle checksum manifest is malformed") from error
        editable_names = {config[0] for config in SHEETS.values()}
        for name in names:
            if name == manifest_name or name in editable_names:
                continue
            if name not in checksums:
                raise RuntimeError(f"bundle checksum manifest omits {name}")
            if hashlib.sha256(archive.read(name)).hexdigest() != checksums[name]:
                raise RuntimeError(f"bundle file checksum changed: {name}")

        pending_writes: list[tuple[Path, Path]] = []
        try:
            for local_name, (archive_name, evidence_fields, review_fields, key_fields, path_fields) in SHEETS.items():
                if archive_name not in names:
                    raise RuntimeError(f"bundle is missing worksheet {archive_name}")
                local_path = data_dir / local_name
                local_columns, local_rows = read_local(local_path)
                archive_columns, returned_rows = rows_from_bytes(archive.read(archive_name), archive_name)
                expected_columns = list(evidence_fields + review_fields)
                if local_columns != expected_columns or archive_columns != expected_columns:
                    raise RuntimeError(f"{archive_name} has unexpected columns")
                local_by_key = {}
                for row in local_rows:
                    key = key_for(row, key_fields)
                    if not all(key) or key in local_by_key:
                        raise RuntimeError(f"local worksheet {local_name} has missing or duplicate keys")
                    local_by_key[key] = row
                returned_by_key = {}
                for row in returned_rows:
                    key = key_for(row, key_fields)
                    if not all(key) or key in returned_by_key:
                        raise RuntimeError(f"returned worksheet {archive_name} has missing or duplicate keys")
                    returned_by_key[key] = row
                if local_by_key.keys() != returned_by_key.keys():
                    raise RuntimeError(f"returned worksheet {archive_name} does not cover the same evidence")

                merged = []
                for key, original in local_by_key.items():
                    returned = returned_by_key[key]
                    for field in evidence_fields:
                        candidate = returned.get(field, "")
                        if field in path_fields and candidate:
                            candidate = localize_path(candidate)
                        if candidate != original.get(field, ""):
                            raise RuntimeError(f"returned evidence changed for {key}: {field}")
                    merged.append({
                        **{field: original.get(field, "") for field in evidence_fields},
                        **{field: returned.get(field, "") for field in review_fields},
                    })
                temporary = write_csv_atomic(local_path, local_columns, merged)
                pending_writes.append((temporary, local_path))

            for temporary, destination in pending_writes:
                os.replace(temporary, destination)
        except Exception:
            for temporary, _ in pending_writes:
                temporary.unlink(missing_ok=True)
            raise
    return [destination for _, destination in pending_writes]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="reviewer-returned ZIP")
    parser.add_argument("--data-dir", type=Path, default=DATA)
    args = parser.parse_args()
    paths = import_bundle(args.bundle, args.data_dir)
    print(f"imported independent annotations into {len(paths)} worksheets")


if __name__ == "__main__":
    main()
