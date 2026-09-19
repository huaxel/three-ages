#!/usr/bin/env python3
"""Download the British Library Flickr Commons extract for La Balance.

The image is the engraving on printed page 24 / scan page 36 of volume 1 of
*La Belgique illustrée* (1878). The exact Flickr record labels it
"No known copyright restrictions" and identifies British Library book
000266582, shelfmark Digital Store 10270.g.3.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "historical" / "british-library-maison-balance-1878.jpg"
SOURCE_URL = "https://www.flickr.com/photos/britishlibrary/11271682895/"
IMAGE_URL = "https://live.staticflickr.com/2815/11271682895_1aeeecbddd_o.jpg"
EXPECTED_SHA256 = "1ca88eca41411d38f722b176efedd991da9028feea02795ce6409113026927b8"
USER_AGENT = "final-work-three-ages/1.0"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def request(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"British Library response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return body


def main() -> None:
    source_page = request(SOURCE_URL)
    required_metadata = (
        b"No known copyright restrictions",
        b"British Library digitised image from page 36",
        b"sysnum000266582",
        b"date1878",
    )
    missing = [value.decode() for value in required_metadata if value not in source_page]
    if missing:
        raise RuntimeError(f"Flickr source metadata is missing: {missing}")

    image = request(IMAGE_URL)
    if not image.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Flickr response is not a JPEG")
    actual_hash = hashlib.sha256(image).hexdigest()
    if actual_hash != EXPECTED_SHA256:
        raise RuntimeError(f"unexpected British Library image SHA-256: {actual_hash}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(image)
    OUTPUT.chmod(0o644)
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(image):,} bytes)")
    print(f"source: {SOURCE_URL}; rights: No known copyright restrictions")


if __name__ == "__main__":
    main()
