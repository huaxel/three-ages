#!/usr/bin/env python3
"""Generate aligned, building-centred crops from the Three Ages area orthos.

The area previews use the same WMS 1.1.1 EPSG:4326 bounds and dimensions. This
script projects each pilot building coordinate into source-image pixels, crops
the same square from every epoch, and records pixel hashes in a manifest. The
crops are review aids; they do not create structural-change observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
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

    crop_dir = data / "structural"
    crop_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.chmod(0o755)
    records = []
    half = args.crop_size // 2
    expected_outputs = set()
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

        crop_assets = []
        for asset in assets:
            asset_id = str(asset["asset_id"])
            crop = opened[asset_id].crop((left, top, right, bottom))
            relative = Path("data") / "structural" / f"{source_id}-{asset_id}.png"
            output = data_asset_path(data, relative.as_posix())
            output.parent.mkdir(parents=True, exist_ok=True)
            crop.save(output, format="PNG", optimize=True)
            output.chmod(0o644)
            expected_outputs.add(output.resolve())
            crop_assets.append({
                "asset_id": asset_id,
                "epoch": asset["epoch"],
                "source_preview": asset["preview"],
                "source_preview_sha256": asset["preview_sha256"],
                "crop_preview": relative.as_posix(),
                "pixel_sha256": pixel_hash(crop),
            })
        records.append({
            "source_id": source_id,
            "name": building.get("name", ""),
            "address": building.get("address", ""),
            "latitude": latitude,
            "longitude": longitude,
            "source_center_pixels": {"x": center_x, "y": center_y},
            "crop_box_pixels": {"left": left, "top": top, "right": right, "bottom": bottom},
            "assets": crop_assets,
        })

    stale = [path for path in crop_dir.glob("*.png") if path.resolve() not in expected_outputs]
    if stale:
        raise RuntimeError(f"refusing to leave stale structural crops: {[path.name for path in stale]}")

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
    for image in opened.values():
        image.close()
    try:
        display_path = manifest_path.relative_to(ROOT)
    except ValueError:
        display_path = manifest_path
    print(f"wrote {len(records) * len(assets)} crops for {len(records)} cases")
    print(f"wrote {display_path}")


if __name__ == "__main__":
    main()
