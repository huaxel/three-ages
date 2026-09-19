#!/usr/bin/env python3
"""Download a small, source-linked BruCiel 1996 preview for the pilot."""
from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "data" / "bruciel-1996-grand-place.png"
WMS_URL = "https://gis.urban.brussels/geoserver/wms"
LAYER = "URBAN_DCC_ER:Orthophotoplans_1996"
BBOX = "4.348,50.845,4.357,50.849"
PNG_HEADER = b"\x89PNG\r\n\x1a\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": LAYER,
        "styles": "",
        "format": "image/png",
        "transparent": "true",
        "width": 640,
        "height": 480,
        "crs": "CRS:84",
        "bbox": BBOX,
    }
    url = f"{WMS_URL}?{urlencode(params)}"
    response = urlopen(Request(url, headers={"User-Agent": "final-work-three-ages/1.0"}), timeout=60)
    body = response.read()
    if not body.startswith(PNG_HEADER):
        raise RuntimeError(f"WMS returned a non-PNG response: {body[:120]!r}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)
    print(f"wrote {args.output.relative_to(ROOT)}")
    print(f"source layer: {LAYER}; bbox: {BBOX}")


if __name__ == "__main__":
    main()
