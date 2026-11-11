#!/usr/bin/env python3
"""Build a metadata-blind second-review packet for already annotated facade images.

The shareable ZIP contains only anonymous images, blank review fields, instructions,
and licensing attribution. The primary-answer key remains outside the ZIP.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import os
import random
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SOURCE = "three-ages-image-review.csv"
ALLOWED_LABELS = {
    "baroque", "classical french", "renaissance-inspired", "mixed",
    "other", "uncertain", "not assessable",
}
REVIEW_FIELDS = ("facade_label", "facade_observation", "confidence", "reviewer", "reviewed_at")
CSV_FIELDS = ("review_id", "image_file", *REVIEW_FIELDS)
README = """# Independent facade-style review

This is a blind re-review of 17 images previously annotated in the project. The
set is selected from existing reviewed rows; it is **not** a representative
sample or a model-accuracy test. Please assess each image independently before
consulting sources or the separate attribution sheet.

For every row in `review.csv`, inspect only the corresponding image in
`gallery.html`, then fill `facade_label`, `facade_observation`, `confidence`,
`reviewer`, and `reviewed_at` (ISO date). Use only these existing pilot codes:
`baroque`, `classical french`, `renaissance-inspired`, `mixed`, `other`,
`uncertain`, `not assessable`. The approved vocabulary crosswalk treats
`classical french` as Louis XIV (French classical), and `renaissance-inspired`
as Baroque with Renaissance elements. These are taxonomy aliases, not claims
about any particular image.

Describe visible architectural features, not a construction date. Choose
`not assessable` when framing or image quality does not support a facade-style
judgment; use `uncertain` when the facade is assessable but the style is unclear.
Do not infer building identity or search for the image online before submitting.

The images are metadata-stripped PNG copies; their decoded pixels are preserved.
Per-image licences and required credits/links are in
`ATTRIBUTION_AFTER_REVIEW.md`. Consult that file only after recording the blind
judgments; source pages may contain descriptions. The review ZIP contains no
primary labels, observations, names, dates, asset identifiers, or source URLs.
"""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_source(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"missing CSV header: {path}")
        return list(reader.fieldnames), list(reader)


def png_pixels(source: Path) -> bytes:
    with Image.open(source) as original:
        original.load()
        image = original.copy()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", compress_level=6)
        body = buffer.getvalue()
    with Image.open(io.BytesIO(body)) as check:
        check.load()
        if check.size != image.size or check.mode != image.mode or check.tobytes() != image.tobytes():
            raise RuntimeError(f"lossless image conversion changed decoded pixels: {source}")
        if check.info:
            raise RuntimeError(f"image metadata was not stripped: {source}")
    return body


def gallery(rows: list[dict[str, str]]) -> bytes:
    cards = []
    for row in rows:
        key = html.escape(row["review_id"], quote=True)
        image = html.escape(row["image_file"], quote=True)
        cards.append(
            f"<article><h2>{key}</h2><img src='{image}' alt='Facade image {key}'></article>"
        )
    body = "\n".join(cards)
    page = ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width'>"
            "<title>Blind facade review</title>"
            "<style>body{font:16px system-ui;max-width:1100px;margin:2rem auto}"
            "article{border-top:1px solid #aaa;padding:1rem 0}"
            "img{max-width:100%;max-height:850px;object-fit:contain}</style>"
            f"<body><h1>Independent facade-style review</h1>{body}</body></html>")
    return page.encode("utf-8")


def build(data_dir: Path = DATA,
          output_dir: Path = ROOT.parent.parent / "local/training/blind-style-review-20261026") -> Path:
    source_path = data_dir / SOURCE
    source_fields, source_rows = read_source(source_path)
    required = {"asset_id", "facade_style", "facade_observation", "reviewer", "reviewed_at",
                "confidence", "facade_unit_id", "source_id", "preview", "preview_sha256",
                "licence", "credit", "source_url"}
    missing = required - set(source_fields)
    if missing:
        raise RuntimeError(f"primary worksheet missing required fields: {sorted(missing)}")
    selected = [row for row in source_rows if row.get("facade_style", "").strip()]
    if not selected:
        raise RuntimeError("no populated facade-style rows to re-review")
    if any(row["facade_style"] not in ALLOWED_LABELS for row in selected):
        raise RuntimeError("source worksheet contains a facade label outside the review vocabulary")
    asset_ids = [row["asset_id"] for row in selected]
    if any(not value for value in asset_ids) or len(set(asset_ids)) != len(asset_ids):
        raise RuntimeError("selected rows need unique, nonempty asset IDs")

    source_root = data_dir.resolve().parent
    prepared = []
    source_sha = digest(source_path.read_bytes())
    seed = int(source_sha[:16], 16)
    random.Random(seed).shuffle(selected)
    for index, primary in enumerate(selected, start=1):
        relative = primary["preview"]
        image_path = (source_root / relative).resolve()
        if not image_path.is_relative_to(source_root) or not image_path.is_file():
            raise RuntimeError(f"image is missing or outside the project: {relative}")
        original_bytes = image_path.read_bytes()
        if digest(original_bytes) != primary["preview_sha256"]:
            raise RuntimeError(f"image bytes do not match the primary worksheet: {primary['asset_id']}")
        image_body = png_pixels(image_path)
        review_id = f"R{index:02d}"
        image_file = f"images/{review_id}.png"
        prepared.append({
            "review_id": review_id,
            "image_file": image_file,
            "image_bytes": image_body,
            "primary": primary,
        })

    output_dir = output_dir.resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing packet directory: {output_dir}")
    staging = Path(tempfile.mkdtemp(prefix=".blind-style-review-", dir=output_dir.parent))
    try:
        review_rows = [{"review_id": item["review_id"], "image_file": item["image_file"],
                        **{field: "" for field in REVIEW_FIELDS}} for item in prepared]
        csv_buffer = io.StringIO(newline="")
        writer = csv.DictWriter(csv_buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(review_rows)
        contents = {
            "README-review.md": README.encode("utf-8"),
            "review.csv": csv_buffer.getvalue().encode("utf-8"),
            "gallery.html": gallery(review_rows),
        }
        attribution = [
            "# Per-image attribution — consult after submitting blind judgments",
            "",
            "Do not use these source links or credits during the blind review.",
            "",
        ]
        answer_key = {
            "purpose": "private mapping for returned anonymous style reviews; do not share with reviewer",
            "source_csv_sha256": source_sha,
            "packet_rows": [],
        }
        for item in prepared:
            primary = item["primary"]
            review_id = item["review_id"]
            attribution.append(
                f"- {review_id}: {primary['licence']}; {primary['credit']}; {primary['source_url']}"
            )
            answer_key["packet_rows"].append({
                "review_id": review_id,
                "asset_id": primary["asset_id"],
                "source_id": primary["source_id"],
                "facade_unit_id": primary["facade_unit_id"],
                "primary_facade_style": primary["facade_style"],
                "primary_facade_observation": primary["facade_observation"],
                "primary_reviewer": primary["reviewer"],
                "primary_reviewed_at": primary["reviewed_at"],
                "primary_confidence": primary["confidence"],
                "source_image_sha256": primary["preview_sha256"],
                "anonymized_png_sha256": digest(item["image_bytes"]),
            })
            contents[item["image_file"]] = item["image_bytes"]
        contents["ATTRIBUTION_AFTER_REVIEW.md"] = ("\n".join(attribution) + "\n").encode("utf-8")
        manifest = {"purpose": "blind facade-style re-review only",
                    "files": {name: digest(body) for name, body in sorted(contents.items())}}
        contents["SHA256SUMS.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        archive_path = staging / "blind-facade-style-review.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, body in contents.items():
                archive.writestr(name, body)
        answer_key["packet_sha256"] = digest(archive_path.read_bytes())
        (staging / "answer-key.json").write_text(
            json.dumps(answer_key, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, output_dir)
    except Exception:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA)
    parser.add_argument("--output-dir", type=Path,
                        default=ROOT.parent.parent / "local/training/blind-style-review-20261026")
    args = parser.parse_args()
    output = build(args.data_dir, args.output_dir)
    print(f"blind reviewer packet: {output / 'blind-facade-style-review.zip'}")
    print(f"private answer key (do not share): {output / 'answer-key.json'}")


if __name__ == "__main__":
    main()
