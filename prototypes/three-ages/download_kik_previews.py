#!/usr/bin/env python3
"""Download the small KIK-IRPA historical previews used by the pilot.

The catalogue pages identify these five facade photographs as CC BY 4.0.
The committed previews are deliberately limited to 800px and are source
previews only; annotation decisions remain in three-ages-pilot.json.
"""
from __future__ import annotations

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


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for asset_id, iiif_id in ASSETS.items():
        url = f"https://iiif.kikirpa.be/iiif/2/{iiif_id}/full/!800,800/0/default.jpg"
        request = Request(url, headers={"User-Agent": "final-work-feasibility-spike/1.0"})
        with urlopen(request, timeout=30) as response:
            data = response.read()
        if not data.startswith(b"\xff\xd8\xff"):
            raise RuntimeError(f"KIK-IRPA response for {asset_id} is not a JPEG")
        destination = OUTPUT / f"kik-irpa-{asset_id}.jpg"
        destination.write_bytes(data)
        print(f"wrote {destination.relative_to(ROOT)} ({len(data):,} bytes)")


if __name__ == "__main__":
    main()
