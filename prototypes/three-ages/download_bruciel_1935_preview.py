#!/usr/bin/env python3
"""Download the CC0 BruCiel 1930–1935 Grand Place ortho preview.

The Brussels Mobility metadata page calls this dataset "Ortho 1935" and lists
CC0. GeoServer currently publishes the live layer in the URBAN_DCC_ER
workspace even though the metadata page still documents the retired BDU_DEP
workspace. WMS 1.1.1 with EPSG:4326 is required for a non-blank response.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "data" / "bruciel-1935-grand-place.png"
WMS_URL = "https://gis.urban.brussels/geoserver/wms"
LAYER = "URBAN_DCC_ER:Orthophotoplans_1935"
BBOX = "4.348,50.845,4.357,50.849"
WMS_VERSION = "1.1.1"
SRS = "EPSG:4326"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"
EXPECTED_SHA256 = "d77806ad41785dc7a823b5cf1065705655bdbae9318a1d41e5e3dbb793f756a3"
MAX_RESPONSE_BYTES = 10 * 1024 * 1024


def read_response(response) -> bytes:
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"WMS response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    params = {
        "service": "WMS",
        "version": WMS_VERSION,
        "request": "GetMap",
        "layers": LAYER,
        "styles": "",
        "format": "image/png",
        "transparent": "true",
        "width": 640,
        "height": 480,
        "srs": SRS,
        "bbox": BBOX,
    }
    url = f"{WMS_URL}?{urlencode(params)}"
    with urlopen(Request(url, headers={"User-Agent": "final-work-three-ages/1.0"}), timeout=60) as response:
        body = read_response(response)
    if not body.startswith(PNG_HEADER):
        raise RuntimeError(f"WMS returned a non-PNG response: {body[:120]!r}")
    if len(body) < 50_000:
        raise RuntimeError(f"WMS returned a suspiciously small, likely blank PNG ({len(body):,} bytes)")
    digest = hashlib.sha256(body).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"1930–1935 WMS preview checksum changed: {digest}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)
    args.output.chmod(0o644)
    try:
        display_output = args.output.relative_to(ROOT)
    except ValueError:
        display_output = args.output
    print(f"wrote {display_output}")
    print(f"source layer: {LAYER}; bbox: {BBOX}; wms {WMS_VERSION} {SRS}")


if __name__ == "__main__":
    main()
