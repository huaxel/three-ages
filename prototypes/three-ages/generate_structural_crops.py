#!/usr/bin/env python3
"""Generate aligned, building-centred crops from the Three Ages area orthos.

The area previews use the same WMS 1.1.1 EPSG:4326 bounds and dimensions. This
script projects each pilot building coordinate into source-image pixels, crops
the same square from every epoch, and records pixel hashes in a manifest. The
crops are review aids; they do not create structural-change observations.

Crops are staged in a temporary directory and published only after every case
validates, so a failed run never leaves new images beside a stale manifest.
Regeneration that would invalidate a completed structural review is refused
before anything is published; clear those reviews explicitly first.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from PIL import Image
except ImportError as error:  # pragma: no cover - depends on local tooling
    raise SystemExit("Pillow is required: python3 -m pip install Pillow") from error

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data"
DEFAULT_CROP_SIZE = 160
STRUCTURAL_REVIEW_FIELDS = ("structural_observation", "reviewer", "reviewed_at", "confidence")


def scalar_query(url: str, name: str) -> str:
    values = parse_qs(urlparse(url).query).get(name)
    if not values or len(values) != 1:
        raise RuntimeError(f"area image URL needs exactly one {name} value: {url}")
    return values[0]


def area_geometry(assets: list[dict[str, object]]) -> tuple[tuple[float, float, float, float], int, int, str]:
    geometries = set()
    for asset in assets:
        url = str(asset["image_url"])
        bbox = tuple(float(value) for value in scalar_query(url, "bbox").split(","))
        if len(bbox) != 4:
            raise RuntimeError(f"invalid bbox for {asset['asset_id']}: {bbox}")
        geometries.add((bbox, int(scalar_query(url, "width")), int(scalar_query(url, "height")), scalar_query(url, "srs")))
    if len(geometries) != 1:
        raise RuntimeError(f"area epochs are not aligned: {sorted(geometries)!r}")
    return geometries.pop()


def pixel_hash(image: Image.Image) -> str:
    header = f"{image.mode}:{image.width}x{image.height}:".encode("ascii")
    return hashlib.sha256(header + image.tobytes()).hexdigest()


def data_asset_path(data: Path, relative: str) -> Path:
    parts = Path(relative).parts
    if not parts or parts[0] != "data" or ".." in parts:
        raise RuntimeError(f"preview path must be relative to the prototype data directory: {relative}")
    return data.joinpath(*parts[1:])


def crop_provenance_key(record: dict[str, object], crop_size: int) -> tuple[object, ...]:
    center = record["source_center_pixels"]
    box = record["crop_box_pixels"]
    return (
        record.get("latitude"),
        record.get("longitude"),
        center["x"],
        center["y"],
        (box["left"], box["top"], box["right"], box["bottom"]),
        crop_size,
        tuple(
            (
                asset.get("asset_id"),
                asset.get("epoch"),
                asset.get("source_preview"),
                asset.get("source_preview_sha256"),
                asset.get("crop_preview"),
                asset.get("pixel_sha256"),
            )
            for asset in record.get("assets", [])
        ),
    )


def refuse_if_completed_reviews_invalidated(
    data: Path, new_records: list[dict[str, object]], crop_size: int
) -> None:
    """Refuse to publish crops that would silently invalidate completed reviews."""
    review_path = data / "three-ages-structural-review.csv"
    manifest_path = data / "three-ages-structural-crops.json"
    if not review_path.is_file() or not manifest_path.is_file():
        return
    with review_path.open(newline="", encoding="utf-8") as handle:
        completed = [
            row
            for row in csv.DictReader(handle)
            if any((row.get(field) or "").strip() for field in STRUCTURAL_REVIEW_FIELDS)
        ]
    if not completed:
        return
    old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_by_id = {str(record["source_id"]): record for record in old_manifest.get("records", [])}
    new_by_id = {str(record["source_id"]): record for record in new_records}
    old_size = old_manifest.get("crop_size_pixels")
    for row in completed:
        source_id = str(row.get("source_id"))
        old_record = old_by_id.get(source_id)
        new_record = new_by_id.get(source_id)
        if old_record is None or new_record is None:
            raise RuntimeError(
                f"refusing to regenerate structural crops after provenance changed: "
                f"case {source_id} has a completed review"
            )
        if crop_provenance_key(old_record, old_size) != crop_provenance_key(new_record, crop_size):
            raise RuntimeError(
                f"refusing to regenerate structural crops after provenance changed: "
                f"case {source_id} has a completed review"
            )


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--crop-size", type=int, default=DEFAULT_CROP_SIZE)
    args = parser.parse_args()
    if args.crop_size <= 0 or args.crop_size % 2:
        raise RuntimeError("crop size must be a positive even integer")

    data = args.data_dir
    pilot = json.loads((data / "three-ages-pilot.json").read_text(encoding="utf-8"))
    buildings_payload = json.loads((data / "grand-place-buildings.json").read_text(encoding="utf-8"))
    buildings = {str(record["id"]): record for record in buildings_payload["records"]}
    assets = pilot.get("area_image_evidence", [])
    if len(assets) < 2:
        raise RuntimeError("at least two aligned area-image epochs are required")
    bbox, width, height, crs = area_geometry(assets)
    west, south, east, north = bbox
    if not west < east or not south < north:
        raise RuntimeError(f"invalid area bounds: {bbox}")

    opened: dict[str, Image.Image] = {}
    try:
        for asset in assets:
            preview = str(asset["preview"])
            preview_path = data_asset_path(data, preview)
            actual_sha256 = hashlib.sha256(preview_path.read_bytes()).hexdigest()
            if actual_sha256 != asset.get("preview_sha256"):
                raise RuntimeError(f"source preview checksum mismatch for {asset['asset_id']}: {actual_sha256}")
            image = Image.open(preview_path)
            image.load()
            if image.size != (width, height):
                raise RuntimeError(f"{preview} is {image.size}, expected {(width, height)}")
            opened[str(asset["asset_id"])] = image

        # Validate every case geometry before writing anything, so one bad
        # coordinate cannot leave earlier crops beside a stale manifest.
        half = args.crop_size // 2
        geometries = []
        for case in pilot["records"]:
            source_id = str(case["source_id"])
            building = buildings.get(source_id)
            if not building:
                raise RuntimeError(f"pilot case {source_id} has no building source record")
            latitude = float(building["latitude"])
            longitude = float(building["longitude"])
            center_x = round((longitude - west) / (east - west) * width)
            center_y = round((north - latitude) / (north - south) * height)
            left, top = center_x - half, center_y - half
            right, bottom = left + args.crop_size, top + args.crop_size
            if left < 0 or top < 0 or right > width or bottom > height:
                raise RuntimeError(f"crop for {source_id} falls outside the aligned area image: {(left, top, right, bottom)}")
            geometries.append({
                "source_id": source_id,
                "name": building.get("name", ""),
                "address": building.get("address", ""),
                "latitude": latitude,
                "longitude": longitude,
                "center_x": center_x,
                "center_y": center_y,
                "box": (left, top, right, bottom),
            })

        # Stage crops outside the published directory, then publish atomically.
        records = []
        with tempfile.TemporaryDirectory(dir=data, prefix=".structural-staging-") as staging:
            staging_dir = Path(staging) / "structural"
            staging_dir.mkdir(parents=True, exist_ok=True)
            staged: dict[str, Path] = {}
            for geometry in geometries:
                source_id = geometry["source_id"]
                left, top, right, bottom = geometry["box"]
                crop_assets = []
                for asset in assets:
                    asset_id = str(asset["asset_id"])
                    crop = opened[asset_id].crop((left, top, right, bottom))
                    filename = f"{source_id}-{asset_id}.png"
                    staged_path = staging_dir / filename
                    crop.save(staged_path, format="PNG", optimize=True)
                    staged[filename] = staged_path
                    crop_assets.append({
                        "asset_id": asset_id,
                        "epoch": asset["epoch"],
                        "source_preview": asset["preview"],
                        "source_preview_sha256": asset["preview_sha256"],
                        "crop_preview": (Path("data") / "structural" / filename).as_posix(),
                        "pixel_sha256": pixel_hash(crop),
                    })
                records.append({
                    "source_id": source_id,
                    "name": geometry["name"],
                    "address": geometry["address"],
                    "latitude": geometry["latitude"],
                    "longitude": geometry["longitude"],
                    "source_center_pixels": {"x": geometry["center_x"], "y": geometry["center_y"]},
                    "crop_box_pixels": {"left": left, "top": top, "right": right, "bottom": bottom},
                    "assets": crop_assets,
                })

            crop_dir = data / "structural"
            expected_names = set(staged)
            existing_names = {path.name for path in crop_dir.glob("*.png")} if crop_dir.is_dir() else set()
            stale = sorted(existing_names - expected_names)
            if stale:
                raise RuntimeError(f"refusing to leave stale structural crops: {stale}")
            refuse_if_completed_reviews_invalidated(data, records, args.crop_size)

            crop_dir.mkdir(parents=True, exist_ok=True)
            crop_dir.chmod(0o755)
            for filename, staged_path in staged.items():
                final = crop_dir / filename
                shutil.copyfile(staged_path, final)
                final.chmod(0o644)
    finally:
        for image in opened.values():
            image.close()

    manifest = {
        "sources": ["three-ages-pilot.json", "grand-place-buildings.json"],
        "method": "Building coordinates projected linearly into aligned WMS 1.1.1 EPSG:4326 previews; identical pixel boxes cropped from every epoch.",
        "review_status": "derived review aids; no structural observations",
        "crs": crs,
        "bounds": {"west": west, "south": south, "east": east, "north": north},
        "source_size_pixels": {"width": width, "height": height},
        "crop_size_pixels": args.crop_size,
        "record_count": len(records),
        "records": records,
    }
    manifest_path = data / "three-ages-structural-crops.json"
    write_json(manifest_path, manifest)
    try:
        display_path = manifest_path.relative_to(ROOT)
    except ValueError:
        display_path = manifest_path
    print(f"wrote {len(records) * len(assets)} crops for {len(records)} cases")
    print(f"wrote {display_path}")


if __name__ == "__main__":
    main()
