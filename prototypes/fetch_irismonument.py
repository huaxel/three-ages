#!/usr/bin/env python3
"""Fetch the Brussels Irismonument (architectural heritage inventory) WFS layer into a committed snapshot.

The public OGC service at gis.urban.brussels exposes URBAN_DCH_IBH:Irismonument_inventory
(one point per inventoried building). Each feature carries the inventory's own style,
build-year, typology, architect, location and first-image URL fields — the label pool
for the multi-era training corpus (see docs/facade-style-vocabulary.md).

The metadata/licence header mirrors prototypes/fetch_open_data.py; the record shape
mirrors grand-place-buildings.json. Images (FIRSTIMAGE) are NOT downloaded here: their
licence is under verification (TODO-6a4d9c5c) before any training use.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent
WFS_URL = "https://gis.urban.brussels/geoserver/wfs"
TYPENAME = "URBAN_DCH_IBH:Irismonument_inventory"
PROPERTY_NAMES = [
    "NOM_FR", "NOM_NL", "ID_BATI_DMS", "FIRSTIMAGE", "CITY", "URL_FR", "URL_NL",
    "STREET_FR", "STREET_NL", "NUMBER", "CITIES_FR", "CITIES_NL",
    "TYPO_FR", "TYPO_NL", "TYPO", "STYLE_FR", "STYLE_NL", "BULT", "INTERVENANTS",
    "LISTED", "UNESCO", "LEGAL", "GEOMETRY",
]
PAGE_SIZE = 1000
MAX_RESPONSE_BYTES = 100 * 1024 * 1024
EXPECTED_TOTAL = 40919  # numberMatched observed 2026-10-09; treated as a floor via require

USER_AGENT = "three-ages-evidence-prototype/1.0"


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
    request = Request(url, headers={"Accept-Encoding": "identity", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=120) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(body) <= MAX_RESPONSE_BYTES, f"response exceeds {MAX_RESPONSE_BYTES:,} bytes: {url}")
    return body


def fetch_page(start_index: int) -> tuple[list[dict], int]:
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": TYPENAME, "count": PAGE_SIZE, "startIndex": start_index,
        "propertyName": ",".join(PROPERTY_NAMES),
    }
    url = f"{WFS_URL}?{urlencode(params)}"
    body = get_body(url)
    root = ET.fromstring(body)
    ns = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml/3.2"}
    # The root element IS the wfs:FeatureCollection; numberMatched is its attribute.
    matched = int(root.attrib.get("numberMatched", "0"))
    members = root.findall(".//wfs:member", ns)
    rows = []
    for member in members:
        feature = member[0]
        record = {}
        for field in feature:
            tag = field.tag.split("}")[-1]
            if tag == "GEOMETRY":
                # gml:Point with gml:pos "x y" in EPSG:31370 (Lambert 72)
                point = field.find(".//gml:Point", ns)
                pos = point.find("gml:pos", ns) if point is not None else None
                if pos is not None and (pos.text or "").strip():
                    coords = pos.text.strip().split()
                    record["x"], record["y"] = coords[0], coords[1]
                    record["crs"] = point.attrib.get("srsName", "urn:ogc:def:crs:EPSG::31370")
                continue
            text = (field.text or "").strip()
            record[tag] = text or None
        rows.append(record)
    return rows, (matched or 0)


def fetch_all() -> list[dict]:
    all_rows: list[dict] = []
    start = 0
    matched = 0
    while True:
        page, matched = fetch_page(start)
        all_rows.extend(page)
        start += len(page)
        if len(page) < PAGE_SIZE or start >= matched:
            break
    require(matched >= EXPECTED_TOTAL, f"Irismonument total below expected floor: {matched} < {EXPECTED_TOTAL}")
    return all_rows


def completeness(rows: list[dict], fields) -> dict:
    return {field: sum(bool(row.get(field)) for row in rows) for field in fields}


def fetch_irismonument() -> None:
    rows = fetch_all()
    require(len(rows) >= EXPECTED_TOTAL, f"Irismonument returned fewer records than expected: {len(rows)} < {EXPECTED_TOTAL}")
    require(all(row.get("ID_BATI_DMS") for row in rows), "Irismonument returned a record without ID_BATI_DMS")
    # The layer is fiche-centric: one ID_BATI_DMS (building/fiche) can span several
    # street numbers (e.g. Rue des Chandeliers 4-6-8 share fiche 30037). The composite
    # (ID, number, street) is the address-level key.
    keys = [(row["ID_BATI_DMS"], row.get("NUMBER"), row.get("STREET_FR")) for row in rows]
    require(len(set(keys)) == len(keys), "Irismonument returned duplicate (ID, number, street) keys")

    # Licence/publisher: metadata lives on the BruGIS/data.mobility pages (CC0); the
    # WFS layer itself does not carry a licence field, so record the observed source.
    out = ROOT / "three-ages" / "data" / "irismonument-inventory.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_json(out, {
        "source": "urban.brussels Irismonument (architectural heritage inventory) WFS layer",
        "wfs_url": f"{WFS_URL}?service=WFS&version=2.0.0&request=GetCapabilities",
        "typename": TYPENAME,
        "metadata_url": "https://data.mobility.brussels/nl/info/979a37d4-f855-4081-b7a0-b1c02c0fe334/",
        "source_licence": "CC0 (metadata; see BruGIS layer page)",
        "source_credit": "urban.brussels — Inventaire du patrimoine architectural (Irismonument)",
        "image_licence_status": "VERIFIED 2026-10-09: metadata CC0; photos NOT blanket-licensed for training - site terms allow non-commercial publication reproduction only; use KIK/BALaT CC BY 4.0 or explicit urban.brussels permission per case (see docs/irismonument-image-licence.md)",
        "fetched_at": "2026-10-09",
        "completeness": completeness(rows, ["STYLE_FR", "STYLE_NL", "BULT", "NOM_FR", "FIRSTIMAGE", "x"]),
        "records": rows,
    })


if __name__ == "__main__":
    fetch_irismonument()
    print("Fetched the Irismonument WFS inventory snapshot.")