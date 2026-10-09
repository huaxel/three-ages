#!/usr/bin/env python3
"""Validate the small committed snapshots used by both prototypes."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import runpy
import statistics
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent


def read_json(relative: str) -> dict:
    path = ROOT / relative

    def reject_nonstandard_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant {value} in {path}")

    return json.loads(path.read_text(), parse_constant=reject_nonstandard_constant)


def _decode_png(path: Path) -> tuple[int, int, str, bytes] | None:
    """Decode the small non-interlaced 8-bit PNG variants used by previews."""
    import struct
    import zlib

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    pos, idat, header = 8, bytearray(), None
    while pos < len(data):
        length, typ = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        if typ == b"IHDR":
            header = struct.unpack(">IIBBBBB", chunk[:13])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + length
    if not header or not idat:
        return None
    width, height, depth, colour_type, compression, filtering, interlace = header
    modes = {0: ("L", 1), 2: ("RGB", 3), 4: ("LA", 2), 6: ("RGBA", 4)}
    if depth != 8 or colour_type not in modes or compression or filtering or interlace:
        return None
    mode, channels = modes[colour_type]
    try:
        raw = zlib.decompress(bytes(idat))
    except zlib.error:
        return None
    stride = width * channels
    if len(raw) != height * (stride + 1):
        return None

    def paeth(left: int, up: int, upper_left: int) -> int:
        estimate = left + up - upper_left
        distances = (abs(estimate - left), abs(estimate - up), abs(estimate - upper_left))
        return (left, up, upper_left)[distances.index(min(distances))]

    pixels = bytearray()
    previous = bytearray(stride)
    off = 0
    for _ in range(height):
        filter_type = raw[off]
        off += 1
        encoded = raw[off:off + stride]
        off += stride
        decoded = bytearray(stride)
        for index, value in enumerate(encoded):
            left = decoded[index - channels] if index >= channels else 0
            up = previous[index]
            upper_left = previous[index - channels] if index >= channels else 0
            predictor = {0: 0, 1: left, 2: up, 3: (left + up) // 2, 4: paeth(left, up, upper_left)}.get(filter_type)
            if predictor is None:
                return None
            decoded[index] = (value + predictor) & 0xFF
        pixels += decoded
        previous = decoded
    return width, height, mode, bytes(pixels)


def _png_pixel_sha256(path: Path) -> str:
    import hashlib

    decoded = _decode_png(path)
    if not decoded:
        return ""
    width, height, mode, pixels = decoded
    return hashlib.sha256(f"{mode}:{width}x{height}:".encode("ascii") + pixels).hexdigest()


def _png_has_content(path: Path) -> bool:
    """Return True when the PNG carries non-trivial visible imagery."""
    decoded = _decode_png(path)
    if not decoded:
        return False
    _width, _height, mode, pixels = decoded
    channels = len(mode)
    intensities = bytearray()
    for index in range(0, len(pixels), channels):
        values = pixels[index:index + channels]
        alpha = values[-1] if mode.endswith("A") else 255
        colour = values[:-1] if mode.endswith("A") else values
        if alpha:
            intensities.append(sum(colour) // len(colour))
    if not intensities:
        return False
    seen = set(intensities)
    return len(seen) > 50 and (max(seen) - min(seen)) > 40


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"validation failed: {message}")


def require_unique_ids(records: list[dict], label: str, field: str = "id") -> set[object]:
    identifiers = [record.get(field) for record in records]
    require(all(identifier not in (None, "") for identifier in identifiers), f"{label} contains a missing {field}")
    require(len(set(identifiers)) == len(identifiers), f"{label} contains duplicate {field} values")
    return set(identifiers)


def read_csv(relative: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse a worksheet with the csv module so quoted multiline fields stay intact."""
    path = ROOT / relative
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def main() -> None:
    buildings = read_json("three-ages/data/grand-place-buildings.json")
    irismonument = read_json("three-ages/data/irismonument-inventory.json")
    irismonument_mapping = read_json("three-ages/data/irismonument-style-mapping.json")
    pilot = read_json("three-ages/data/three-ages-pilot.json")
    structural_crops = read_json("three-ages/data/three-ages-structural-crops.json")
    three_ages_inventory = read_json("three-ages/data/source-inventory.json")
    preview_1935_path = ROOT / "three-ages/data/bruciel-1935-grand-place.png"
    preview_1971_path = ROOT / "three-ages/data/bruciel-1971-grand-place.png"
    preview_path = ROOT / "three-ages/data/bruciel-1996-grand-place.png"
    preview_2022_path = ROOT / "three-ages/data/urbisgrid-2022-grand-place.png"
    pilot_fields, pilot_rows = read_csv("three-ages/data/three-ages-pilot-export.csv")
    image_review_fields, image_review_rows = read_csv("three-ages/data/three-ages-image-review.csv")
    compiled_reviews = read_json("three-ages/data/three-ages-image-reviews.json")
    structural_review_fields, structural_review_rows = read_csv("three-ages/data/three-ages-structural-review.csv")
    compiled_structural_reviews = read_json("three-ages/data/three-ages-structural-reviews.json")
    register_review_fields, register_review_rows = read_csv("three-ages/data/three-ages-register-review.csv")
    compiled_register_reviews = read_json("three-ages/data/three-ages-register-reviews.json")


    building_ids = require_unique_ids(buildings["records"], "Grand Place building snapshot")
    irismonument_rows = irismonument.get("records", [])
    require(len(irismonument_rows) >= 40000, "Irismonument snapshot is missing records")
    irismonument_keys = {(r.get("ID_BATI_DMS"), r.get("NUMBER"), r.get("STREET_FR")) for r in irismonument_rows}
    require(all(k[0] for k in irismonument_keys), "Irismonument snapshot contains a record without ID_BATI_DMS")
    require(len(irismonument_keys) == len(irismonument_rows), "Irismonument snapshot contains duplicate (ID, number, street) keys")
    require(irismonument.get("source_licence", "").startswith("CC0"), "Irismonument snapshot licence is missing or stale")
    require(all("monument.heritage.brussels" in (r.get("URL_FR") or "") for r in irismonument_rows[:50]), "Irismonument snapshot lacks expected fiche URLs")
    require(all(r.get("crs") == "urn:ogc:def:crs:EPSG::31370" for r in irismonument_rows if r.get("crs")), "Irismonument snapshot CRS is unexpected")

    style_map = irismonument_mapping.get("mapping", {})
    snapshot_terms = {(r.get("STYLE_FR") or "").strip() for r in irismonument_rows}
    snapshot_terms.discard("")
    require(style_map.keys() == snapshot_terms, "Irismonument style mapping does not cover every snapshot term")
    require(all(not any(c.startswith("UNMAPPED:") for c in entry["classes"]) for entry in style_map.values()), "Irismonument style mapping still contains unmapped terms")

    selection = read_json("three-ages/data/irismonument-case-selection.json")
    require(len(selection["classes"]) >= 15, "Irismonument case selection is missing classes")
    require(all(isinstance(info["count"], int) and info["count"] >= 0 for info in selection["classes"].values()), "Irismonument case selection counts are malformed")

    balat = read_json("three-ages/data/balat-photo-provenance.json")
    balat_records = balat.get("records", [])
    require(len({r.get("case_id") for r in balat_records}) == len(balat_records), "BALaT provenance contains duplicate case IDs")
    balat_matched = [r for r in balat_records if r.get("matched")]
    require(all(r.get("licence") == "CC BY 4.0" and r.get("preview_sha256") and r.get("source_url", "").startswith("https://balat.kikirpa.be/en/photo/") for r in balat_matched), "BALaT provenance contains an unverified match")
    for record in balat_matched:
        preview = ROOT / "three-ages" / record["preview"]
        body = preview.read_bytes()
        require(body.startswith(b"\xff\xd8\xff"), f"BALaT preview is not a JPEG: {record['photo_id']}")
        require(hashlib.sha256(body).hexdigest() == record["preview_sha256"], f"BALaT preview checksum is stale: {record['photo_id']}")
    balat_photos = {r["photo_id"] for r in balat_matched}
    coverage = balat.get("coverage", {})
    require(coverage.get("total_cases") == len(balat_records) and coverage.get("unique_photos") == len(balat_photos), "BALaT coverage report disagrees with provenance")
    balat_worksheet_fields, balat_worksheet_rows = read_csv("three-ages/data/balat-photo-review.csv")
    require({r["photo_id"] for r in balat_worksheet_rows} == balat_photos, "BALaT review worksheet does not cover every verified photo")
    require(all(r["annotation_status"] in ("pending reviewer annotation", "reviewed photo annotation") for r in balat_worksheet_rows), "BALaT worksheet contains an unknown annotation status")
    balat_compiled = read_json("three-ages/data/balat-photo-reviews.json")
    require(balat_compiled.get("record_count") == len(balat_compiled.get("records", [])), "BALaT compiled review count is stale")
    require(all(r["facade_label"].strip() for r in balat_compiled.get("records", [])), "BALaT compiled reviews contain a blank label")
    balat_manifest = read_json("three-ages/data/balat-training-manifest.json")
    require(balat_manifest.get("record_count") == len(balat_manifest.get("records", [])), "BALaT training manifest count is stale")
    manifest_groups: dict[str, set[str]] = {}
    commons_licences = {"CC BY 4.0", "CC BY 3.0", "CC BY 2.0", "CC BY-SA 4.0", "CC BY-SA 3.0", "CC0", "Public domain"}
    for entry in balat_manifest.get("records", []):
        photo_licence = entry.get("licence", {}).get("photo")
        if (entry.get("photo_id") or "").startswith("commons-"):
            require(photo_licence in commons_licences, f"training manifest contains a non-open Commons photo: {entry.get('photo_id')}")
        else:
            require(photo_licence == "CC BY 4.0", f"training manifest contains a non-CC-BY photo: {entry.get('photo_id')}")
        manifest_groups.setdefault(entry["split_group"], set()).add(entry["split"])
    require(all(len(splits) == 1 for splits in manifest_groups.values()), "training manifest building group straddles splits")
    commons = read_json("three-ages/data/commons-photo-provenance.json")
    commons_records = commons.get("records", [])
    require(len({r.get("case_id") for r in commons_records}) == len(commons_records), "Commons provenance contains duplicate case IDs")
    require(all(r.get("licence") in commons_licences and r.get("preview_sha256") and r.get("source_url", "").startswith("https://commons.wikimedia.org/wiki/File:") for r in commons_records), "Commons provenance contains an unverified match")
    for record in commons_records:
        preview = ROOT / "three-ages" / record["preview"]
        body = preview.read_bytes()
        require(body.startswith(b"\xff\xd8\xff"), f"Commons preview is not a JPEG: {record['photo_id']}")
        require(hashlib.sha256(body).hexdigest() == record["preview_sha256"], f"Commons preview checksum is stale: {record['photo_id']}")
    commons_photos = {r["photo_id"] for r in commons_records}
    commons_worksheet_fields, commons_worksheet_rows = read_csv("three-ages/data/commons-photo-review.csv")
    require({r["photo_id"] for r in commons_worksheet_rows} == commons_photos, "Commons review worksheet does not cover every staged photo")
    require(all(r["annotation_status"] in ("pending reviewer annotation", "reviewed photo annotation") for r in commons_worksheet_rows), "Commons worksheet contains an unknown annotation status")
    commons_compiled = read_json("three-ages/data/commons-photo-reviews.json")
    require(commons_compiled.get("record_count") == len(commons_compiled.get("records", [])), "Commons compiled review count is stale")
    require(all(r["facade_label"].strip() for r in commons_compiled.get("records", [])), "Commons compiled reviews contain a blank label")
    pilot_ids = require_unique_ids(pilot["records"], "Three Ages pilot", "source_id")
    buildings_by_id = {str(record["id"]): record for record in buildings["records"]}
    require(len(buildings["records"]) == 34, "expected 34 Grand Place records")
    require(all(isinstance(record.get("latitude"), (int, float)) and isinstance(record.get("longitude"), (int, float)) for record in buildings["records"]), "Grand Place building snapshot contains missing coordinates")
    require(buildings.get("dataset_url", "").startswith("https://"), "building snapshot is missing dataset URL")
    require(buildings.get("dataset_metadata_url") == "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place", "building snapshot metadata URL is missing or stale")
    require(buildings.get("source_licence") == "CC BY 4.0", "building snapshot licence is missing or stale")
    require(buildings.get("source_credit") == "Ville de Bruxelles/Data Management; catalogue attributions: Behind Brussels, Google Maps", "building snapshot attribution is missing or stale")
    require(len(pilot["records"]) == 6, "expected six curated pilot records")
    require(pilot.get("review_status") == "source-grounded pilot", "pilot review status is missing")
    require({"bruciel_app", "grand_place_dataset", "brussels_heritage_inventory", "wikidata_register_proxies", "heritage_collection_1749", "kik_irpa_historical", "wikimedia_commons_balance", "balance_engraving_1878", "bruciel_1935", "bruciel_1971", "bruciel_1996", "bruciel_1944", "brussels_archives", "urbisgrid_2022"} <= set(three_ages_inventory), "Three Ages source inventory is incomplete")
    area_images = pilot.get("area_image_evidence", [])
    require(
        [(asset.get("asset_id"), asset.get("epoch"), asset.get("preview")) for asset in area_images] == [
            ("bruciel-grand-place-1935", "1930–1935", "data/bruciel-1935-grand-place.png"),
            ("bruciel-grand-place-1971", 1971, "data/bruciel-1971-grand-place.png"),
            ("bruciel-grand-place-1996", 1996, "data/bruciel-1996-grand-place.png"),
            ("urbisgrid-grand-place-2022", 2022, "data/urbisgrid-2022-grand-place.png"),
        ],
        "area-level structural evidence is incomplete or out of order",
    )
    area_required = {"asset_id", "epoch", "scope", "source_url", "image_url", "preview", "preview_sha256", "licence", "credit", "observation", "annotation_status"}
    require(all(area_required <= set(asset) for asset in area_images), "area-level structural evidence schema is incomplete")
    require(all(asset["scope"] == "Grand Place pilot area" and asset["annotation_status"].startswith("area source preview") for asset in area_images), "area-level structural evidence scope or review status is stale")
    require(all("bbox=4.348%2C50.845%2C4.357%2C50.849" in asset["image_url"] for asset in area_images), "area-level structural evidence bounds are not aligned")
    require(all(hashlib.sha256((ROOT / "three-ages" / asset["preview"]).read_bytes()).hexdigest() == asset["preview_sha256"] for asset in area_images), "area-level source preview checksum is stale")

    require(structural_crops.get("review_status") == "derived review aids; no structural observations", "structural crop review boundary is missing")
    require(structural_crops.get("crs") == "EPSG:4326", "structural crop CRS is stale")
    require(structural_crops.get("bounds") == {"west": 4.348, "south": 50.845, "east": 4.357, "north": 50.849}, "structural crop bounds are stale")
    require(structural_crops.get("source_size_pixels") == {"width": 640, "height": 480}, "structural crop source dimensions are stale")
    crop_size = structural_crops.get("crop_size_pixels")
    require(crop_size == 160 and structural_crops.get("record_count") == 6, "structural crop size or record count is stale")
    crop_records = structural_crops.get("records", [])
    require_unique_ids(crop_records, "structural crop manifest", "source_id")
    require([record.get("source_id") for record in crop_records] == [record["source_id"] for record in pilot["records"]], "structural crops do not follow the pilot case order")
    area_by_id = {asset["asset_id"]: asset for asset in area_images}
    crop_paths = set()
    for crop_record in crop_records:
        source_id = crop_record["source_id"]
        building = buildings_by_id[source_id]
        require(crop_record["latitude"] == building["latitude"] and crop_record["longitude"] == building["longitude"], f"structural crop coordinate is stale for {source_id}")
        expected_x = round((building["longitude"] - 4.348) / (4.357 - 4.348) * 640)
        expected_y = round((50.849 - building["latitude"]) / (50.849 - 50.845) * 480)
        require(crop_record["source_center_pixels"] == {"x": expected_x, "y": expected_y}, f"structural crop centre is stale for {source_id}")
        half = crop_size // 2
        require(crop_record["crop_box_pixels"] == {"left": expected_x - half, "top": expected_y - half, "right": expected_x + half, "bottom": expected_y + half}, f"structural crop box is stale for {source_id}")
        crop_assets = crop_record.get("assets", [])
        require([asset.get("asset_id") for asset in crop_assets] == list(area_by_id), f"structural crop epochs are stale for {source_id}")
        for crop_asset in crop_assets:
            source_asset = area_by_id[crop_asset["asset_id"]]
            require(crop_asset["epoch"] == source_asset["epoch"] and crop_asset["source_preview"] == source_asset["preview"] and crop_asset["source_preview_sha256"] == source_asset["preview_sha256"], f"structural crop source metadata is stale for {source_id}/{crop_asset['asset_id']}")
            crop_path = ROOT / "three-ages" / crop_asset["crop_preview"]
            crop_paths.add(crop_path.resolve())
            decoded = _decode_png(crop_path) if crop_path.is_file() else None
            require(decoded is not None and decoded[:2] == (crop_size, crop_size), f"structural crop is missing or has wrong dimensions for {source_id}/{crop_asset['asset_id']}")
            require(_png_has_content(crop_path), f"structural crop is blank for {source_id}/{crop_asset['asset_id']}")
            require(_png_pixel_sha256(crop_path) == crop_asset["pixel_sha256"], f"structural crop pixel hash is stale for {source_id}/{crop_asset['asset_id']}")
    actual_crop_paths = {path.resolve() for path in (ROOT / "three-ages/data/structural").glob("*.png")}
    require(actual_crop_paths == crop_paths, "structural crop directory contains missing or stale files")

    require(all(entry.get("url", "").startswith("https://") for entry in three_ages_inventory.values()), "Three Ages source inventory has an invalid URL")
    require(all(entry.get("licence") and entry.get("credit") for entry in three_ages_inventory.values()), "Three Ages source inventory contains an unresolved licence or credit field")
    require(three_ages_inventory["urbis_buildings"].get("licence", "").startswith("Open Data licence stated by provider") and three_ages_inventory["urbis_buildings"].get("credit") == "Paradigm", "UrbIS source-lead reuse status is missing")
    require(three_ages_inventory["planning_permits"].get("licence") == "CC0 1.0" and "Ville de Bruxelles" in three_ages_inventory["planning_permits"].get("credit", ""), "planning-permit source-lead provenance is missing")
    require(three_ages_inventory["grand_place_dataset"].get("metadata") == buildings["dataset_metadata_url"] and three_ages_inventory["grand_place_dataset"].get("licence") == buildings["source_licence"] and three_ages_inventory["grand_place_dataset"].get("credit") == buildings["source_credit"], "Grand Place inventory provenance disagrees with the snapshot")
    require(three_ages_inventory["brussels_heritage_inventory"].get("terms") == "https://monument.heritage.brussels/fr/legal/", "architectural-inventory terms URL is missing")
    require(three_ages_inventory["brussels_heritage_inventory"].get("licence") == "text quotations and reused information permitted with explicit source attribution" and "urban.brussels" in three_ages_inventory["brussels_heritage_inventory"].get("credit", ""), "architectural-inventory text reuse terms or credit are missing")
    require(three_ages_inventory["wikidata_register_proxies"].get("licence") == "CC0 1.0 for structured data" and three_ages_inventory["wikidata_register_proxies"].get("credit", "").startswith("Wikidata contributors"), "Wikidata register-proxy licence or credit is missing")
    require(three_ages_inventory["kik_irpa_historical"].get("licence", "").startswith("CC BY 4.0") and three_ages_inventory["kik_irpa_historical"].get("credit", "").startswith("KIK-IRPA"), "KIK-IRPA licence or credit metadata is missing")
    require(three_ages_inventory["kik_irpa_historical"].get("status", "").startswith("twelve pilot previews verified"), "KIK-IRPA verification status is missing")
    require(three_ages_inventory["wikimedia_commons_balance"].get("licence") == "CC BY-SA 3.0" and three_ages_inventory["wikimedia_commons_balance"].get("credit") == "EmDee, via Wikimedia Commons", "Wikimedia Commons licence or credit metadata is missing")
    require(three_ages_inventory["wikimedia_commons_balance"].get("status", "").startswith("exact-case 2011"), "Wikimedia Commons verification status is missing")
    require("2043-0177/0" in three_ages_inventory["wikimedia_commons_balance"].get("note", "") and "does not state Rue de la Colline 24" in three_ages_inventory["wikimedia_commons_balance"]["note"], "Wikimedia Commons identity metadata is inaccurate")
    require(three_ages_inventory["balance_engraving_1878"].get("licence") == "No known copyright restrictions" and "British Library" in three_ages_inventory["balance_engraving_1878"].get("credit", "") and "Victor Dedoncker" in three_ages_inventory["balance_engraving_1878"]["credit"], "1878 engraving rights or credit metadata is missing")
    require(three_ages_inventory["balance_engraving_1878"].get("status", "").startswith("exact-case 1878 institutional scan verified"), "1878 engraving verification status is missing")
    require(three_ages_inventory["balance_engraving_1878"].get("preview") == "data/historical/british-library-maison-balance-1878.jpg", "1878 engraving preview metadata is missing")
    require(three_ages_inventory["bruciel_1935"].get("licence", "").startswith("CC0") and three_ages_inventory["bruciel_1935"].get("credit") == area_by_id["bruciel-grand-place-1935"]["credit"], "1930–1935 BruCiel licence or credit metadata is missing")
    require(three_ages_inventory["bruciel_1935"].get("status", "").startswith("historical WMS extract verified"), "1930–1935 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1935"].get("layer") == "URBAN_DCC_ER:Orthophotoplans_1935", "1930–1935 BruCiel layer metadata is stale")
    require(three_ages_inventory["bruciel_1935"].get("preview") == "data/bruciel-1935-grand-place.png", "1930–1935 BruCiel preview metadata is missing")
    require(preview_1935_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1930–1935 BruCiel preview is not a PNG")
    require(_png_has_content(preview_1935_path), "1930–1935 BruCiel preview is blank")
    require(three_ages_inventory["bruciel_1971"].get("licence", "").startswith("CC0") and three_ages_inventory["bruciel_1971"].get("credit") == area_by_id["bruciel-grand-place-1971"]["credit"], "1971 BruCiel licence or credit metadata is missing")
    require(three_ages_inventory["bruciel_1971"].get("status", "").startswith("intermediate WMS extract verified"), "1971 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1971"].get("layer") == "URBAN_DCC_ER:Orthophotoplans_1971", "1971 BruCiel layer metadata is stale")
    require(three_ages_inventory["bruciel_1971"].get("preview") == "data/bruciel-1971-grand-place.png", "1971 BruCiel preview metadata is missing")
    require(preview_1971_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1971 BruCiel preview is not a PNG")
    require(_png_has_content(preview_1971_path), "1971 BruCiel preview is blank")
    require(three_ages_inventory["bruciel_1996"].get("licence", "").startswith("CC0") and three_ages_inventory["bruciel_1996"].get("credit") == area_by_id["bruciel-grand-place-1996"]["credit"], "1996 BruCiel licence or credit metadata is missing")
    require(three_ages_inventory["bruciel_1996"].get("status", "").startswith("WMS extract verified"), "1996 BruCiel test status is missing")
    require(three_ages_inventory["bruciel_1996"].get("preview") == "data/bruciel-1996-grand-place.png", "1996 BruCiel preview metadata is missing")
    require(preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "1996 BruCiel preview is not a PNG")
    require(_png_has_content(preview_path), "1996 BruCiel preview is blank")
    require(three_ages_inventory["urbisgrid_2022"].get("licence", "").startswith("open data") and three_ages_inventory["urbisgrid_2022"].get("credit") == area_by_id["urbisgrid-grand-place-2022"]["credit"], "2022 urbisgrid licence or credit metadata is missing")
    require(three_ages_inventory["urbisgrid_2022"].get("preview") == "data/urbisgrid-2022-grand-place.png", "2022 urbisgrid preview metadata is missing")
    require(preview_2022_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "2022 urbisgrid preview is not a PNG")
    require(_png_has_content(preview_2022_path), "2022 urbisgrid preview is blank")
    require(three_ages_inventory["bruciel_1944"].get("licence", "").startswith("CC0"), "1944 BruCiel licence metadata is missing")
    require(three_ages_inventory["bruciel_1944"].get("status", "").startswith("WMS layer unavailable"), "1944 BruCiel failure status is missing")
    require(pilot_ids <= building_ids, "pilot contains an unknown building source ID")
    required_pilot_fields = {"source_id", "selection_reason", "register", "facade", "structure", "image_evidence", "next_step"}
    require(all(required_pilot_fields <= set(record) for record in pilot["records"]), "pilot record schema is incomplete")
    require(all(all(field in record[claim] for field in ("status", "value", "note")) for record in pilot["records"] for claim in ("register", "facade", "structure")), "pilot claim schema is incomplete")
    require(all(all(field in record["register"] for field in ("date_semantics", "source_comparison")) for record in pilot["records"]), "pilot register semantics are not explicit")
    require(all(record["register"]["status"] in ("pending", "proxy", "reviewed") for record in pilot["records"]), "pilot register status is not in the agreed vocabulary")
    register_sources = {record["source_id"]: record["register"].get("source") for record in pilot["records"]}
    wikidata_sources = [source for source in register_sources.values() if source and source.get("kind") == "wikidata-inception"]
    inventory_sources = [source for source in register_sources.values() if source and source.get("kind") == "brussels-architectural-inventory"]
    require({source.get("qid") for source in wikidata_sources} == {"Q3279995", "Q3279408", "Q3279633"}, "Wikidata register proxy claim set is incomplete or stale")
    require(all(source.get("qid", "").startswith("Q") and source.get("claim_url", "").startswith("https://www.wikidata.org/") and source.get("heritage_id") and source.get("heritage_url", "").startswith("https://heritage.toolforge.org/") for source in wikidata_sources), "Wikidata register proxy source chain is incomplete")
    require(all(source.get("inventory_id", "").isdigit() and source.get("url", "").startswith("https://monument.heritage.brussels/") for source in inventory_sources), "official heritage inventory source chain is incomplete")
    expected_inventory_proxies = {"005": 1697, "024": 1704, "026": 1697}
    require(all(pilot_record["register"]["value"] == value and register_sources[source_id]["kind"] == "brussels-architectural-inventory" for source_id, value in expected_inventory_proxies.items() for pilot_record in pilot["records"] if pilot_record["source_id"] == source_id), "official inventory proxy values are stale")
    require(all((record["register"]["status"] == "proxy") == (record["register"].get("source") is not None) for record in pilot["records"]), "register proxy status and source do not match")
    require(all(record["register"]["date_semantics"] == ("Wikidata inception claim referenced to heritage register" if record["register"]["source"]["kind"] == "wikidata-inception" else "heritage-inventory reconstruction date") for record in pilot["records"]), "register date semantics do not match source kinds")
    comparison_by_id = {record["source_id"]: record["register"]["source_comparison"] for record in pilot["records"]}
    require(comparison_by_id["023"].startswith("disagrees") and comparison_by_id["022"].startswith("compatible") and all(comparison_by_id[source_id].startswith("agrees") for source_id in {"005", "009", "024", "026"}), "register source comparisons are stale")
    balance_case = next(record for record in pilot["records"] if record["source_id"] == "024")
    require("Rue de la Colline 24" in balance_case.get("identity_note", "") and "street-address mapping" in balance_case["identity_note"], "La Balance identity discrepancy is not explicit")
    identity_evidence = balance_case.get("identity_evidence", [])
    require(
        [(item.get("source_kind"), item.get("record_id")) for item in identity_evidence] == [
            ("city-open-data", "024"),
            ("brussels-architectural-inventory", "30991"),
            ("wikimedia-commons", "2043-0177/0"),
            ("british-library-flickr-commons", "11271682895"),
        ],
        "La Balance identity crosswalk identifiers are incomplete",
    )
    require(all(all(item.get(field) for field in ("label", "address", "source_url", "observation")) for item in identity_evidence), "La Balance identity crosswalk schema is incomplete")
    commons_identity = next(item for item in identity_evidence if item["source_kind"] == "wikimedia-commons")
    require(commons_identity["address"].startswith("Grand-Place") and "Rue de la Colline" not in commons_identity["address"], "Commons identity evidence overstates its street address")
    heritage_identity = next(item for item in identity_evidence if item["source_kind"] == "brussels-architectural-inventory")
    require(heritage_identity["address"] == "Rue de la Colline 24" and "Grand-Place ensemble" in heritage_identity["observation"], "heritage identity evidence is incomplete")
    require(all("identity_evidence" not in record for record in pilot["records"] if record["source_id"] != "024"), "identity crosswalk is attached to an unrelated pilot case")
    expected_images = {
        "005": [("E049753", 1890), ("T084580", 1942), ("T001817", 1969)],
        "009": [("B031587", 1942), ("T001820", 1969)],
        "022": [("A102887", 1941), ("T001802", 1969), ("A133254", 1984)],
        "023": [("B024641", 1941), ("T001803", 1969)],
        "024": [("british-library-balance-1878", 1878), ("commons-balance-2011-01", 2011)],
        "026": [("B031502", 1942), ("T001805", 1969)],
    }
    for record in pilot["records"]:
        evidence = record["image_evidence"]
        require([(asset.get("asset_id"), asset.get("epoch")) for asset in evidence] == expected_images[record["source_id"]], f"historical image evidence is unexpected for {record['source_id']}")
        for asset in evidence:
            require(all(asset.get(field) for field in ("asset_id", "epoch", "source_url", "image_url", "preview", "preview_sha256", "licence", "credit", "observation", "annotation_status")), f"historical image evidence schema is incomplete for {record['source_id']}")
            if asset["asset_id"].startswith("commons-"):
                require(asset["source_url"].startswith("https://commons.wikimedia.org/wiki/File:"), f"Commons source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"].startswith("https://upload.wikimedia.org/wikipedia/commons/"), f"Commons image URL is invalid for {asset['asset_id']}")
                require(asset["licence"] == "CC BY-SA 3.0" and "EmDee" in asset["credit"], f"Commons image rights or credit is missing for {asset['asset_id']}")
            elif asset["asset_id"].startswith("british-library-"):
                require(asset["source_url"] == "https://www.flickr.com/photos/britishlibrary/11271682895/", f"British Library source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"] == "https://live.staticflickr.com/2815/11271682895_1aeeecbddd_o.jpg", f"British Library image URL is stale for {asset['asset_id']}")
                require(asset["licence"] == "No known copyright restrictions" and "British Library" in asset["credit"], f"British Library image rights or credit is missing for {asset['asset_id']}")
            else:
                require(asset["source_url"].startswith("https://balat.kikirpa.be/en/photo/"), f"historical image source URL is invalid for {asset['asset_id']}")
                require(asset["image_url"].startswith("https://iiif.kikirpa.be/iiif/2/"), f"historical image IIIF URL is invalid for {asset['asset_id']}")
                require(asset["licence"] == "CC BY 4.0", f"historical image rights are missing for {asset['asset_id']}")
            require(asset["annotation_status"].startswith("source preview"), f"historical image review status is missing for {asset['asset_id']}")
            preview = ROOT / "three-ages" / asset["preview"]
            preview_bytes = preview.read_bytes() if preview.is_file() else b""
            require(preview_bytes.startswith(b"\xff\xd8\xff"), f"historical image preview is missing for {asset['asset_id']}")
            require(hashlib.sha256(preview_bytes).hexdigest() == asset["preview_sha256"], f"historical image preview checksum is stale for {asset['asset_id']}")
    evidence_by_asset = {
        asset["asset_id"]: asset
        for case in pilot["records"]
        for asset in case["image_evidence"]
    }
    kik_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_kik_previews.py"))
    require(all(evidence_by_asset[asset_id]["preview_sha256"] == digest for asset_id, digest in kik_downloader["EXPECTED_SHA256"].items()), "KIK downloader checksums disagree with pilot provenance")
    commons_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_commons_previews.py"))
    require(evidence_by_asset["commons-balance-2011-01"]["preview_sha256"] == commons_downloader["EXPECTED_SHA256"], "Commons downloader checksum disagrees with pilot provenance")
    british_downloader = runpy.run_path(str(ROOT / "three-ages" / "download_british_library_preview.py"))
    require(evidence_by_asset["british-library-balance-1878"]["preview_sha256"] == british_downloader["EXPECTED_SHA256"], "British Library downloader checksum disagrees with pilot provenance")
    area_checksum_scripts = {
        "bruciel-grand-place-1935": "download_bruciel_1935_preview.py",
        "bruciel-grand-place-1971": "download_bruciel_1971_preview.py",
        "bruciel-grand-place-1996": "download_bruciel_preview.py",
        "urbisgrid-grand-place-2022": "download_urbisgrid_preview.py",
    }
    for asset_id, script in area_checksum_scripts.items():
        downloader = runpy.run_path(str(ROOT / "three-ages" / script))
        require(area_by_id[asset_id]["preview_sha256"] == downloader["EXPECTED_SHA256"], f"{asset_id} downloader checksum disagrees with pilot provenance")

    require(len(pilot_rows) == 6 and pilot_fields[:3] == ["source_id", "name", "address"], "Three Ages pilot CSV export is incomplete")
    require(all(field in pilot_fields for field in ("register_source_kind", "register_source_url", "identity_note", "identity_evidence_count", "identity_evidence_ids", "identity_evidence_urls", "image_evidence_ids", "image_evidence_epochs", "image_evidence_urls")), "Three Ages pilot CSV is missing provenance columns")
    require(len(image_review_rows) == 14 and image_review_fields[:5] == ["source_id", "name", "address", "asset_id", "epoch"], "historical-image review worksheet is incomplete")
    require(all(field in image_review_fields for field in ("source_observation", "annotation_status", "identity_note", "facade_observation", "structural_observation", "reviewer", "reviewed_at", "confidence")), "historical-image review worksheet is missing review columns")
    require({row["source_id"] for row in image_review_rows} == set(expected_images), "historical-image review worksheet does not cover every pilot case")
    require({"T084580", "B031587", "A102887", "B024641", "british-library-balance-1878", "commons-balance-2011-01", "B031502", "T001802", "A133254", "E049753", "T001803", "T001805", "T001820", "T001817"} <= {row["asset_id"] for row in image_review_rows}, "historical-image review worksheet is missing an asset")
    expected_review_rows = {}
    for case in pilot["records"]:
        assets = case["image_evidence"] or [None]
        for asset in assets:
            asset = asset or {}
            key = (case["source_id"], asset.get("asset_id", ""))
            expected_review_rows[key] = {
                "epoch": str(asset.get("epoch", "")),
                "source_url": asset.get("source_url", ""),
                "image_url": asset.get("image_url", ""),
                "preview": asset.get("preview", ""),
                "preview_sha256": asset.get("preview_sha256", ""),
                "licence": asset.get("licence", ""),
                "credit": asset.get("credit", ""),
                "source_observation": asset.get("observation", "No permitted historical preview is attached."),
                "identity_note": case.get("identity_note", ""),
                "_source_annotation_status": asset.get("annotation_status", "pending historical source"),
            }
    require(len(image_review_rows) == len(expected_review_rows), "historical-image review worksheet has unexpected rows")
    review_fields = ("facade_observation", "structural_observation", "reviewer", "reviewed_at", "confidence")
    for row in image_review_rows:
        key = (row["source_id"], row["asset_id"])
        require(key in expected_review_rows, f"historical-image review worksheet has an unexpected case or asset: {key}")
        expected = expected_review_rows[key]
        require(all(row[field] == value for field, value in expected.items() if field != "_source_annotation_status"), f"historical-image review worksheet is stale for {key}")
        has_review = any(row[field].strip() for field in review_fields)
        if has_review:
            require(bool(row["asset_id"]), f"historical-image review cannot annotate missing evidence for {key}")
            require(bool(row["facade_observation"].strip() or row["structural_observation"].strip()), f"historical-image review needs an observation for {key}")
            require(bool(row["reviewer"].strip() and row["reviewed_at"].strip() and row["confidence"].strip()), f"historical-image review metadata is incomplete for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"historical-image review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"historical-image review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed image annotation", f"historical-image review status is stale for {key}")
        else:
            require(row["annotation_status"] == expected["_source_annotation_status"], f"unreviewed historical-image status is stale for {key}")
    completed_review_rows = [row for row in image_review_rows if any(row[field].strip() for field in review_fields)]
    require(compiled_reviews.get("source") == "three-ages-image-review.csv", "compiled image-review source metadata is missing")
    require(compiled_reviews.get("record_count") == len(completed_review_rows), "compiled image-review count is stale")
    require(compiled_reviews.get("records") == completed_review_rows, "compiled image reviews do not match the completed worksheet rows")
    balance_image_rows = [row for row in image_review_rows if row["source_id"] == "024"]
    require({(row["asset_id"], row["epoch"]) for row in balance_image_rows} == {("british-library-balance-1878", "1878"), ("commons-balance-2011-01", "2011")}, "La Balance comparison epochs are missing from the review worksheet")

    structural_fields = ("structural_observation", "reviewer", "reviewed_at", "confidence")
    require(len(structural_review_rows) == 6 and structural_review_fields[:4] == ["source_id", "name", "address", "comparison_id"], "structural review worksheet is incomplete")
    require({row["source_id"] for row in structural_review_rows} == pilot_ids, "structural review worksheet does not cover every pilot case")
    area_joined = {
        "area_asset_ids": ";".join(str(asset["asset_id"]) for asset in area_images),
        "area_epochs": ";".join(str(asset["epoch"]) for asset in area_images),
        "area_source_urls": ";".join(asset["source_url"] for asset in area_images),
        "area_image_urls": ";".join(asset["image_url"] for asset in area_images),
        "area_previews": ";".join(asset["preview"] for asset in area_images),
        "area_preview_sha256": ";".join(asset["preview_sha256"] for asset in area_images),
        "area_licences": ";".join(asset["licence"] for asset in area_images),
        "area_credits": ";".join(asset["credit"] for asset in area_images),
    }
    case_by_id = {case["source_id"]: case for case in pilot["records"]}
    crop_by_id = {record["source_id"]: record for record in crop_records}
    for row in structural_review_rows:
        key = (row["source_id"], row["comparison_id"])
        require(row["comparison_id"] == "grand-place-1935-1971-1996-2022", f"structural comparison id is stale for {key}")
        require(all(row[field] == value for field, value in area_joined.items()), f"structural comparison provenance is stale for {key}")
        crop_record = crop_by_id[row["source_id"]]
        center, box, assets = crop_record["source_center_pixels"], crop_record["crop_box_pixels"], crop_record["assets"]
        crop_joined = {
            "case_latitude": str(crop_record["latitude"]),
            "case_longitude": str(crop_record["longitude"]),
            "crop_source_center_pixels": f"{center['x']},{center['y']}",
            "crop_box_pixels": f"{box['left']},{box['top']},{box['right']},{box['bottom']}",
            "crop_size_pixels": str(crop_size),
            "case_crop_previews": ";".join(asset["crop_preview"] for asset in assets),
            "case_crop_pixel_sha256": ";".join(asset["pixel_sha256"] for asset in assets),
        }
        require(all(row[field] == value for field, value in crop_joined.items()), f"structural crop provenance is stale for {key}")
        identity_items = case_by_id[row["source_id"]].get("identity_evidence", [])
        identity_joined = {
            "identity_evidence_ids": ";".join(f"{item.get('source_kind', '')}:{item.get('record_id', '')}" for item in identity_items),
            "identity_evidence_urls": ";".join(item.get("source_url", "") for item in identity_items),
            "identity_evidence_observations": ";".join(item.get("observation", "") for item in identity_items),
        }
        require(all(row[field] == value for field, value in identity_joined.items()), f"structural identity provenance is stale for {key}")
        require(row["identity_note"] == case_by_id[row["source_id"]].get("identity_note", ""), f"structural comparison identity note is stale for {key}")
        has_review = any(row[field].strip() for field in structural_fields)
        if has_review:
            require(all(row[field].strip() for field in structural_fields), f"structural review metadata is incomplete for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"structural review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"structural review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed structural comparison", f"completed structural review status is stale for {key}")
        else:
            require(row["annotation_status"] == "area comparison; no reviewer annotation", f"pending structural review status is stale for {key}")
    completed_structural_rows = [row for row in structural_review_rows if any(row[field].strip() for field in structural_fields)]
    require(compiled_structural_reviews.get("source") == "three-ages-structural-review.csv", "compiled structural-review source metadata is missing")
    require(compiled_structural_reviews.get("record_count") == len(completed_structural_rows), "compiled structural-review count is stale")
    require(compiled_structural_reviews.get("records") == completed_structural_rows, "compiled structural reviews do not match the completed worksheet rows")

    register_fields = ("register_decision", "register_observation", "reviewer", "reviewed_at", "confidence")
    register_decisions = {"accept proxy for MVP", "retain as reconstruction evidence", "reject source mapping"}
    require(len(register_review_rows) == 6 and register_review_fields[:4] == ["source_id", "name", "address", "claim_id"], "register review worksheet is incomplete")
    require({row["source_id"] for row in register_review_rows} == pilot_ids, "register review worksheet does not cover every pilot case")
    for row in register_review_rows:
        source_id = row["source_id"]
        case = case_by_id[source_id]
        claim = case["register"]
        claim_source = claim["source"]
        key = (source_id, row["claim_id"])
        expected_register = {
            "claim_id": f"register-{source_id}",
            "reported_value": str(claim["value"]),
            "claim_status": claim["status"],
            "date_semantics": claim["date_semantics"],
            "source_comparison": claim["source_comparison"],
            "source_kind": claim_source["kind"],
            "source_record_id": claim_source.get("qid") or claim_source.get("inventory_id", ""),
            "source_url": claim_source.get("url") or claim_source.get("claim_url", ""),
            "source_note": claim["note"],
            "city_history": buildings_by_id[source_id]["history"],
            "identity_note": case.get("identity_note", ""),
        }
        require(all(row[field] == value for field, value in expected_register.items()), f"register review provenance is stale for {key}")
        has_review = any(row[field].strip() for field in register_fields)
        if has_review:
            require(all(row[field].strip() for field in register_fields), f"register review metadata is incomplete for {key}")
            require(row["register_decision"] in register_decisions, f"register review decision is invalid for {key}")
            require(row["confidence"] in {"low", "medium", "high"}, f"register review confidence is invalid for {key}")
            try:
                datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            except ValueError:
                require(False, f"register review date is not ISO 8601 for {key}")
            require(row["annotation_status"] == "reviewed register semantics", f"completed register review status is stale for {key}")
        else:
            require(row["annotation_status"] == "proxy semantics; no reviewer decision", f"pending register review status is stale for {key}")
    completed_register_rows = [row for row in register_review_rows if any(row[field].strip() for field in register_fields)]
    require(compiled_register_reviews.get("source") == "three-ages-register-review.csv", "compiled register-review source metadata is missing")
    require(compiled_register_reviews.get("record_count") == len(completed_register_rows), "compiled register-review count is stale")
    require(compiled_register_reviews.get("records") == completed_register_rows, "compiled register reviews do not match the completed worksheet rows")

    review_export = runpy.run_path(str(ROOT / "three-ages" / "export_pilot.py"))
    generated_review = {field: "" for field in review_export["IMAGE_FIELDS"]}
    generated_review.update({"source_id": "test-case", "asset_id": "test-asset", "source_url": "https://example.test/evidence", "annotation_status": "source preview; no reviewer annotation"})
    existing_review = {field: str(generated_review[field]) for field in review_export["IMAGE_FIELDS"]}
    existing_review.update({"facade_observation": "Test observation", "reviewer": "Test reviewer", "reviewed_at": "2026-09-20", "confidence": "medium"})
    preserved_review = review_export["preserve_review"](dict(generated_review), existing_review)
    require(preserved_review["facade_observation"] == "Test observation" and preserved_review["annotation_status"] == "reviewed image annotation", "completed historical-image reviews are not preserved")
    changed_review = dict(generated_review)
    changed_review["source_url"] = "https://example.test/changed"
    try:
        review_export["preserve_review"](changed_review, existing_review)
    except RuntimeError:
        pass
    else:
        require(False, "historical-image reviews can drift onto changed provenance")

    generated_structural = {field: "" for field in review_export["STRUCTURAL_FIELDS"]}
    generated_structural.update({
        "source_id": "test-case",
        "comparison_id": "test-comparison",
        "area_asset_ids": "historical;modern",
        "case_crop_pixel_sha256": "historical-hash;modern-hash",
        "annotation_status": "area comparison; no reviewer annotation",
    })
    existing_structural = {field: str(generated_structural[field]) for field in review_export["STRUCTURAL_FIELDS"]}
    existing_structural.update({
        "structural_observation": "Test structural observation",
        "reviewer": "Test reviewer",
        "reviewed_at": "2026-09-20",
        "confidence": "medium",
    })
    preserved_structural = review_export["preserve_structural_review"](dict(generated_structural), existing_structural)
    require(preserved_structural["structural_observation"] == "Test structural observation" and preserved_structural["annotation_status"] == "reviewed structural comparison", "completed structural reviews are not preserved")
    changed_structural = dict(generated_structural)
    changed_structural["case_crop_pixel_sha256"] = "changed-hash;modern-hash"
    try:
        review_export["preserve_structural_review"](changed_structural, existing_structural)
    except RuntimeError:
        pass
    else:
        require(False, "structural reviews can drift onto changed crop pixels")

    generated_register = {field: "" for field in review_export["REGISTER_FIELDS"]}
    generated_register.update({
        "source_id": "test-case",
        "claim_id": "register-test-case",
        "reported_value": "1700",
        "date_semantics": "test semantics",
        "source_comparison": "test comparison",
        "annotation_status": "proxy semantics; no reviewer decision",
    })
    existing_register = {field: str(generated_register[field]) for field in review_export["REGISTER_FIELDS"]}
    existing_register.update({
        "register_decision": "retain as reconstruction evidence",
        "register_observation": "Test semantics observation",
        "reviewer": "Test reviewer",
        "reviewed_at": "2026-09-20",
        "confidence": "medium",
    })
    preserved_register = review_export["preserve_register_review"](dict(generated_register), existing_register)
    require(preserved_register["register_decision"] == "retain as reconstruction evidence" and preserved_register["annotation_status"] == "reviewed register semantics", "completed register reviews are not preserved")
    changed_register = dict(generated_register)
    changed_register["source_comparison"] = "changed comparison"
    try:
        review_export["preserve_register_review"](changed_register, existing_register)
    except RuntimeError:
        pass
    else:
        require(False, "register reviews can drift onto changed source semantics")

    print("snapshot validation passed")
    print(f"building records: {len(building_ids)}; pilot cases: {len(pilot_ids)}")


if __name__ == "__main__":
    main()
