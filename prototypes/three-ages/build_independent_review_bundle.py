#!/usr/bin/env python3
"""Build a standalone ZIP for a blind independent reviewer.

The bundle contains only instructions, independent worksheets, and evidence
images referenced by those worksheets. Primary annotation artifacts are excluded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from export_independent_review import (
    BALAT_EVIDENCE, COMMONS_EVIDENCE, IMAGE_EVIDENCE, IMAGE_REVIEW,
    PHOTO_REVIEW, STRUCTURAL_EVIDENCE, STRUCTURAL_REVIEW,
)

DATA = Path(__file__).resolve().parent / "data"
IMAGE_WORKSHEET = "three-ages-independent-image-review.csv"
STRUCTURAL_WORKSHEET = "three-ages-independent-structural-review.csv"
BALAT_WORKSHEET = "balat-independent-photo-review.csv"
COMMONS_WORKSHEET = "commons-independent-photo-review.csv"
IMAGE_ALLOWED_FIELDS = (
    "source_id", "name", "address", "asset_id", "epoch", "source_url", "image_url",
    "preview", "preview_sha256", "licence", "credit", "source_observation",
    "identity_verdict", "facade_label", "facade_observation", "reviewer", "reviewed_at",
)
STRUCTURAL_ALLOWED_FIELDS = (
    "source_id", "name", "address", "comparison_id", "area_asset_ids", "area_epochs",
    "area_source_urls", "area_image_urls", "area_previews", "area_preview_sha256",
    "area_licences", "area_credits", "case_latitude", "case_longitude",
    "crop_source_center_pixels", "crop_box_pixels", "crop_size_pixels",
    "case_crop_previews", "case_crop_pixel_sha256", "source_observation",
    "structural_observation", "reviewer", "reviewed_at",
)
BALAT_ALLOWED_FIELDS = BALAT_EVIDENCE + PHOTO_REVIEW
COMMONS_ALLOWED_FIELDS = COMMONS_EVIDENCE + PHOTO_REVIEW

README = """# Independent annotation review bundle

This archive is a blind second-annotator packet. It excludes primary annotations,
confidence ratings, and adjudication decisions. Do not consult the primary review
worksheets until both independent worksheets are complete.

## Worksheets

- `three-ages-independent-image-review.csv`: one row per historical facade image.
  Fill identity_verdict, facade_label, facade_observation, reviewer, reviewed_at.
- `three-ages-independent-structural-review.csv`: one row per pilot building comparison.
  Fill structural_observation, reviewer, reviewed_at.
- `balat-independent-photo-review.csv` and `commons-independent-photo-review.csv`:
  one row per scaled-corpus photo. Fill identity_verdict, facade_label,
  facade_observation, reviewer, reviewed_at.
- Positive facade labels use the agreed vocabulary: Baroque; Baroque with classical
  features; Neoclassical; Second Empire; Eclecticism; Historicist neo-styles;
  Beaux-Arts; Art Nouveau; Art Deco; Paquebot style; Functionalism; Modernism
  (interwar, post-war, Expo 58, late, period undetermined); Brutalism;
  Postmodernism; Contemporary; Louis XIV; Antique classical orders; Mixed
  Antique+Baroque; Baroque with Renaissance elements. Record uncertainty explicitly.
- Evidence images are under `evidence/`; CSV preview paths point into this folder.
  Source URLs, epochs, checksums, licence and credit remain in the worksheets.

Use explicit uncertainty where the evidence is insufficient. Similar facade
appearance is not proof of structural continuity. Return both edited CSV files
without changing evidence or provenance columns. After the independent pass, the
project owner can import the sheets, generate paired adjudication worksheets,
and record agreement, rationale, disposition, adjudicator and date.
"""


def rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def csv_bytes(fields: list[str], values: list[dict[str, str]]) -> bytes:
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(values)
    return handle.getvalue().encode("utf-8")


def evidence_path(data_dir: Path, relative: str) -> Path:
    project_root = data_dir.resolve().parent
    candidate = (project_root / relative).resolve()
    if not candidate.is_relative_to(project_root) or not candidate.is_file():
        raise RuntimeError(f"evidence path is missing or outside the data directory: {relative}")
    return candidate


def build(data_dir: Path = DATA, output: Path = Path("/tmp/three-ages-independent-review.zip")) -> Path:
    channels = (
        (IMAGE_WORKSHEET, IMAGE_ALLOWED_FIELDS, "three-ages-independent-image-review.csv", "preview", "asset_id"),
        (STRUCTURAL_WORKSHEET, STRUCTURAL_ALLOWED_FIELDS, "three-ages-independent-structural-review.csv", "case_crop_previews", "source_id"),
        (BALAT_WORKSHEET, BALAT_ALLOWED_FIELDS, BALAT_WORKSHEET, "preview", "photo_id"),
        (COMMONS_WORKSHEET, COMMONS_ALLOWED_FIELDS, COMMONS_WORKSHEET, "preview", "photo_id"),
    )
    contents = {"README-review.md": README.encode("utf-8")}
    image_files: dict[str, Path] = {}
    for source_name, allowed_fields, archive_csv, preview_field, key in channels:
        fields, source_rows = rows(data_dir / source_name)
        if fields != list(allowed_fields):
            raise RuntimeError(f"{source_name} has unexpected columns; refusing to bundle possibly non-blind data")
        outputs = []
        for row in source_rows:
            relative_paths = row.get(preview_field, "").split(";") if preview_field == "case_crop_previews" else [row.get(preview_field, "")]
            if not relative_paths or any(not value for value in relative_paths):
                raise RuntimeError(f"review row {row.get(key)} has incomplete evidence paths")
            archive_paths = []
            for relative in relative_paths:
                image_files[relative] = evidence_path(data_dir, relative)
                archive_paths.append(f"evidence/{relative}")
            outputs.append({**row, preview_field: ";".join(archive_paths)})
        contents[archive_csv] = csv_bytes(fields, outputs)

    output.parent.mkdir(parents=True, exist_ok=True)
    contents.update({f"evidence/{relative}": source.read_bytes() for relative, source in image_files.items()})
    manifest = {
        "purpose": "blind independent annotation only; not training data",
        "files": {name: hashlib.sha256(body).hexdigest() for name, body in sorted(contents.items())},
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, body in contents.items():
            archive.writestr(name, body)
        archive.writestr("SHA256SUMS.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output", type=Path, default=Path("/tmp/three-ages-independent-review.zip"))
    args = parser.parse_args()
    result = build(args.data_dir, args.output)
    print(f"blind review bundle: {result} ({result.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
