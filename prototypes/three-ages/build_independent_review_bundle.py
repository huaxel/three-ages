#!/usr/bin/env python3
"""Build a standalone ZIP for a blind independent reviewer.

The bundle contains only instructions, independent worksheets, and evidence
images referenced by those worksheets. Primary annotation artifacts are excluded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
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
  Open `gallery.html` for an offline visual index across all four worksheets.
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


def gallery_html(sections: list[tuple[str, list[dict[str, str]], str, str]]) -> bytes:
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>",
             "<title>Blind independent review gallery</title><style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem}section{margin:3rem 0}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1rem}.card{border:1px solid #bbb;border-radius:8px;padding:1rem}.images{display:flex;gap:.5rem;flex-wrap:wrap}.images img{max-width:100%;max-height:320px;object-fit:contain}.images figure{margin:.25rem;max-width:48%}dt{font-weight:600}dd{margin:0 0 .4rem}</style></head><body><h1>Blind independent review gallery</h1>",
             "<p>Images and captions use only the independent worksheets; primary annotations are excluded.</p>"]
    for title, rows, image_field, epoch_field in sections:
        parts.append(f"<section><h2>{html.escape(title)}</h2><div class='cards'>")
        for row in rows:
            key = row.get("photo_id") or row.get("asset_id") or row.get("source_id", "case")
            label = f"{row.get('name', '')} {row.get('address', '')}".strip()
            if row.get("photo_id"):
                label = f"{row.get('addresses', '')} — {row.get('photo_id')}".strip(" —")
            parts.append(f"<article class='card'><h3>{html.escape(label or key)}</h3><p>{html.escape(key)}</p><div class='images'>")
            paths = row.get(image_field, "").split(";")
            epochs = row.get(epoch_field, "").split(";") if epoch_field else []
            for index, path in enumerate(paths):
                caption = epochs[index] if index < len(epochs) else row.get("epoch", "") or row.get("photo_date_taken", "")
                parts.append(f"<figure><a href='{html.escape(path, quote=True)}'><img loading='lazy' src='{html.escape(path, quote=True)}' alt='{html.escape(label or key, quote=True)}'></a><figcaption>{html.escape(caption)}</figcaption></figure>")
            parts.append("</div><dl>")
            for field in ("photo_view_scope", "photo_represented_detail", "source_observation"):
                value = row.get(field, "").strip()
                if value:
                    parts.append(f"<dt>{html.escape(field.replace('_', ' ').title())}</dt><dd>{html.escape(value)}</dd>")
            parts.append("</dl></article>")
        parts.append("</div></section>")
    parts.append("</body></html>")
    return "\n".join(parts).encode("utf-8")


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
    gallery_sections = []
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
        gallery_sections.append((archive_csv.removesuffix(".csv").replace("-", " ").title(), outputs,
                                 preview_field, "area_epochs" if preview_field == "case_crop_previews" else ""))
    contents["gallery.html"] = gallery_html(gallery_sections)

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
