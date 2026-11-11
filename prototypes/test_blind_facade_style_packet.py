#!/usr/bin/env python3
"""Synthetic safety tests for the blind facade-style review packet."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / "three-ages"))
from build_blind_facade_style_packet import build


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        data = root / "data"
        images = data / "historical"
        images.mkdir(parents=True)
        rows = []
        originals = {}
        for index, (label, color) in enumerate((("baroque", "red"), ("classical french", "blue")), 1):
            image_path = images / f"secret-{index}.jpg"
            image = Image.new("RGB", (9, 7), color=color)
            exif = Image.Exif()
            exif[270] = "PRIMARY SECRET SOURCE STYLE"
            image.save(image_path, format="JPEG", exif=exif)
            originals[f"data/historical/secret-{index}.jpg"] = image_path.read_bytes()
            rows.append({
                "source_id": f"PRIVATE-SOURCE-{index}",
                "facade_unit_id": f"PRIVATE-UNIT-{index}",
                "name": f"PRIVATE BUILDING {index}",
                "address": f"PRIVATE ADDRESS {index}",
                "asset_id": f"PRIVATE-ASSET-{index}",
                "epoch": str(1900 + index),
                "source_url": f"https://example.invalid/PRIMARY-STYLE-{index}",
                "image_url": "https://example.invalid/private.jpg",
                "preview": f"data/historical/secret-{index}.jpg",
                "preview_sha256": sha(originals[f"data/historical/secret-{index}.jpg"]),
                "licence": "CC BY 4.0",
                "credit": f"Photographer {index}",
                "facade_style": label,
                "facade_observation": f"PRIMARY OBSERVATION {index}",
                "reviewer": "Primary reviewer",
                "reviewed_at": "2026-01-01",
                "confidence": "high",
            })
        fields = list(rows[0])
        with (data / "three-ages-image-review.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

        out = build(data, root / "packet")
        archive_path = out / "blind-facade-style-review.zip"
        key_path = out / "answer-key.json"
        key = json.loads(key_path.read_text(encoding="utf-8"))
        assert len(key["packet_rows"]) == 2
        assert key["packet_sha256"] == sha(archive_path.read_bytes())
        assert all(r["primary_facade_style"] for r in key["packet_rows"])
        assert not any("answer-key" in name for name in zipfile.ZipFile(archive_path).namelist())

        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            assert "review.csv" in names and "gallery.html" in names
            assert not any("secret-" in name or "PRIVATE" in name for name in names)
            review_text = archive.read("review.csv").decode("utf-8")
            reader = csv.DictReader(io.StringIO(review_text, newline=""))
            review_rows = list(reader)
            assert len(review_rows) == 2
            for row in review_rows:
                assert all(not row[field].strip() for field in (
                    "facade_label", "facade_observation", "confidence", "reviewer", "reviewed_at"))
                assert row["review_id"] not in ("PRIVATE-ASSET-1", "PRIVATE-ASSET-2")
            visible = b"\n".join(archive.read(name) for name in (
                "README-review.md", "review.csv", "gallery.html"))
            for secret in ("PRIVATE-SOURCE", "PRIVATE-UNIT", "PRIVATE BUILDING",
                           "PRIVATE ADDRESS", "PRIMARY OBSERVATION", "PRIMARY-STYLE",
                           "PRIMARY SECRET SOURCE STYLE", "PRIVATE-ASSET"):
                assert secret.encode() not in visible, secret
            attribution = archive.read("ATTRIBUTION_AFTER_REVIEW.md")
            assert b"CC BY 4.0" in attribution and b"Photographer" in attribution
            manifest = json.loads(archive.read("SHA256SUMS.json"))
            for name, checksum in manifest["files"].items():
                assert sha(archive.read(name)) == checksum, name
            for row in review_rows:
                with Image.open(io.BytesIO(archive.read(row["image_file"]))) as packaged:
                    packaged.load()
                    assert not packaged.info, "source metadata leaked into anonymized image"
                    image_id = row["review_id"]
                    match = next(r for r in key["packet_rows"] if r["review_id"] == image_id)
                    original_name = next(k for k in originals if sha(originals[k]) == match["source_image_sha256"])
                    with Image.open(io.BytesIO(originals[original_name])) as original:
                        original.load()
                        assert packaged.size == original.size
                        assert packaged.mode == original.mode
                        assert packaged.tobytes() == original.tobytes()

        # Refuse to replace a prior packet or its private key.
        marker = key_path.read_bytes()
        try:
            build(data, out)
        except FileExistsError:
            pass
        else:
            raise AssertionError("packet builder overwrote an existing packet")
        assert key_path.read_bytes() == marker
        for relative, body in originals.items():
            assert (root / relative).read_bytes() == body

    print("blind facade-style packet privacy, pixel, checksum, and overwrite contracts passed")


if __name__ == "__main__":
    main()
