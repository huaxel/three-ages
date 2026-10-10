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

DATA = Path(__file__).resolve().parent / "data"
ROOT = Path(__file__).resolve().parents[2]
IMAGE_WORKSHEET = "three-ages-independent-image-review.csv"
STRUCTURAL_WORKSHEET = "three-ages-independent-structural-review.csv"
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

README = """# Independent annotation review bundle

This archive is a blind second-annotator packet. It excludes primary annotations,
confidence ratings, and adjudication decisions. Do not consult the primary review
worksheets until both independent worksheets are complete.

## Worksheets

- `three-ages-independent-image-review.csv`: one row per historical facade image.
  Fill identity_verdict, facade_label, facade_observation, reviewer, reviewed_at.
- `three-ages-independent-structural-review.csv`: one row per building comparison.
  Fill structural_observation, reviewer, reviewed_at.
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


def add_evidence(archive: zipfile.ZipFile, data_dir: Path, relative: str) -> str:
    source = evidence_path(data_dir, relative)
    archive_name = f"evidence/{relative}"
    archive.write(source, archive_name)
    return archive_name


def build(data_dir: Path = DATA, output: Path = Path("/tmp/three-ages-independent-review.zip")) -> Path:
    image_path = data_dir / IMAGE_WORKSHEET
    structural_path = data_dir / STRUCTURAL_WORKSHEET
    image_fields, image_rows = rows(image_path)
    structural_fields, structural_rows = rows(structural_path)
    if image_fields != list(IMAGE_ALLOWED_FIELDS) or structural_fields != list(STRUCTURAL_ALLOWED_FIELDS):
        raise RuntimeError("independent worksheets have unexpected columns; refusing to bundle possibly non-blind data")

    image_outputs = []
    image_files = {}
    for row in image_rows:
        relative = row.get("preview", "")
        if not relative:
            raise RuntimeError(f"image review row {row.get('asset_id')} has no preview")
        arc = f"evidence/{relative}"
        image_files[relative] = evidence_path(data_dir, relative)
        image_outputs.append({**row, "preview": arc})

    structural_outputs = []
    for row in structural_rows:
        relative_paths = row.get("case_crop_previews", "").split(";")
        if not relative_paths or any(not value for value in relative_paths):
            raise RuntimeError(f"structural review row {row.get('source_id')} has incomplete crop paths")
        arcs = []
        for relative in relative_paths:
            image_files[relative] = evidence_path(data_dir, relative)
            arcs.append(f"evidence/{relative}")
        structural_outputs.append({**row, "case_crop_previews": ";".join(arcs)})

    output.parent.mkdir(parents=True, exist_ok=True)
    contents = {
        "README-review.md": README.encode("utf-8"),
        "three-ages-independent-image-review.csv": csv_bytes(image_fields, image_outputs),
        "three-ages-independent-structural-review.csv": csv_bytes(structural_fields, structural_outputs),
    }
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
