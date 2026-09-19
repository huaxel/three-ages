#!/usr/bin/env python3
"""Download the small KIK-IRPA historical previews used by the pilot.

The catalogue pages identify these five facade photographs as CC BY 4.0.
The committed previews are deliberately limited to 800px and are source
previews only; annotation decisions remain in three-ages-pilot.json.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "historical"
ASSETS = {
    "A102887": "a102887",
    "B024641": "b024641",
    "B031502": "b031502",
    "B031587": "b031587",
    "T084580": "t084580",
}
EXPECTED_SHA256 = {
    "A102887": "522ca72791cf0cf91d0699d44142a58497653f811e0379e31ad91506b9256404",
    "B024641": "1cb4b385605d6935e709bf2b4556dde169125c62a4177ae4e2ce1fb73d3b1e30",
    "B031502": "fe085935651ab77bf403c68f43cb537d60d1d4090dd97360e7a8beb1dc28b475",
    "B031587": "6283f8fbcc7d5bbf5b2d840892a8185bd305f24c2aa8618bcada8e24220a36cf",
    "T084580": "9b55192144b537a50e4584c4b81c0616b850574bd8ae6db798b023157cab1b2d",
}
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def read_response(response, asset_id: str) -> bytes:
    data = response.read(MAX_RESPONSE_BYTES + 1)
    if len(data) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"KIK-IRPA response for {asset_id} exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return data


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for asset_id, iiif_id in ASSETS.items():
        url = f"https://iiif.kikirpa.be/iiif/2/{iiif_id}/full/!800,800/0/default.jpg"
        request = Request(url, headers={"User-Agent": "final-work-feasibility-spike/1.0"})
        with urlopen(request, timeout=30) as response:
            data = read_response(response, asset_id)
        if not data.startswith(b"\xff\xd8\xff"):
            raise RuntimeError(f"KIK-IRPA response for {asset_id} is not a JPEG")
        digest = hashlib.sha256(data).hexdigest()
        if digest != EXPECTED_SHA256[asset_id]:
            raise RuntimeError(f"KIK-IRPA checksum changed for {asset_id}: {digest}")
        destination = OUTPUT / f"kik-irpa-{asset_id}.jpg"
        destination.write_bytes(data)
        destination.chmod(0o644)
        print(f"wrote {destination.relative_to(ROOT)} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
