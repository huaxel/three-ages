#!/usr/bin/env python3
"""Refresh the City of Brussels Grand Place source snapshot."""
from __future__ import annotations

import gzip
import io
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
GRAND_PLACE_DATASET_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place/records"
GRAND_PLACE_METADATA_URL = "https://opendata.brussels.be/api/explore/v2.1/catalog/datasets/description-des-batiments-de-la-grand-place"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.chmod(0o644)
    os.replace(temporary, path)


def get_body(url: str) -> bytes:
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "three-ages-evidence-prototype/1.0"})
    with urlopen(request, timeout=30) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(body) <= MAX_RESPONSE_BYTES, f"response exceeds {MAX_RESPONSE_BYTES:,} bytes: {url}")
    if body[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as compressed:
            body = compressed.read(MAX_RESPONSE_BYTES + 1)
        require(len(body) <= MAX_RESPONSE_BYTES, f"decompressed response exceeds {MAX_RESPONSE_BYTES:,} bytes: {url}")
    return body


def get_json(base: str, **params):
    url = f"{base}?{urlencode(params)}"
    payload = json.loads(get_body(url))
    require(isinstance(payload, dict), f"expected JSON object from {url}")
    return payload


def fetch_grand_place() -> None:
    payload = get_json(
        GRAND_PLACE_DATASET_URL,
        limit=100,
    )
    metadata = get_json(GRAND_PLACE_METADATA_URL)
    metadata_default = metadata.get("metas", {}).get("default", {})
    require(metadata_default.get("license") == "CC BY 4.0", "Grand Place catalogue licence changed")
    require(metadata_default.get("publisher") == "Ville de Bruxelles/Data Management", "Grand Place catalogue publisher changed")
    attributions = metadata_default.get("attributions", [])
    require(attributions == ["Behind Brussels", "Google Maps"], "Grand Place catalogue attributions changed")
    require(payload.get("total_count", 0) >= 34 and len(payload.get("results", [])) == 34, "Grand Place API returned fewer than 34 records")
    rows = []
    for item in payload["results"]:
        maps_url = item.get("google_maps") or ""
        query = parse_qs(urlparse(maps_url).query).get("query", [""])[0]
        query = unquote(query)
        coords = query.split(",", 1) if "," in query else [None, None]
        history = item.get("history_and_successive_restorations") or ""
        history_years = [int(year) for year in re.findall(r"\b(1[5-9]\d{2}|20\d{2})\b", history)]
        rows.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "address": item.get("adresse"),
                "latitude": float(coords[0]) if coords[0] else None,
                "longitude": float(coords[1]) if coords[1] else None,
                "history": history,
                "history_years": sorted(set(history_years)),
                "facade": item.get("composition_of_the_facade_and_decorative_program"),
                "original_function": item.get("original_main_function"),
                "source_url": maps_url,
            }
        )
    identifiers = [row["id"] for row in rows]
    require(all(identifier not in (None, "") for identifier in identifiers), "Grand Place API returned a building without an ID")
    require(len(set(identifiers)) == len(identifiers), "Grand Place API returned duplicate building IDs")
    completeness = {
        field: sum(bool(row.get(field)) for row in rows)
        for field in ("history", "history_years", "facade", "original_function")
    }
    out = ROOT / "three-ages" / "data" / "grand-place-buildings.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {
        "source": payload["total_count"],
        "dataset_url": GRAND_PLACE_DATASET_URL,
        "dataset_metadata_url": GRAND_PLACE_METADATA_URL,
        "source_licence": metadata_default["license"],
        "source_credit": f"{metadata_default['publisher']}; catalogue attributions: {', '.join(attributions)}",
        "completeness": completeness,
        "records": rows,
    })



if __name__ == "__main__":
    fetch_grand_place()
    print("Fetched the Three Ages Grand Place source snapshot.")
