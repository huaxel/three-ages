#!/usr/bin/env python3
"""Download the licensed Wikimedia Commons preview for La Balance.

The 2011 facade view covers the pilot case that lacks a KIK-IRPA preview.
It is an earlier source epoch, not a substitute for 1940s-era evidence.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "historical" / "commons-maison-balance-2011.jpg"
API = "https://commons.wikimedia.org/w/api.php"
TITLE = "File:Belgique - Bruxelles - Maison de la Balance - 01.jpg"
EXPECTED_LICENSE = "CC BY-SA 3.0"
EXPECTED_MONUMENT_ID = "2043-0177/0"
EXPECTED_DESCRIPTION = "Grand-Place - Maison de la Balance"
EXPECTED_SHA256 = "8af4305c92db16d063ce19f901afc9841e1721e5be4c70d39b9cb3deed9bce03"
USER_AGENT = "final-work-three-ages/1.0"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024


def request(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"Wikimedia Commons response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return body


def main() -> None:
    params = {
        "action": "query",
        "titles": TITLE,
        "prop": "imageinfo|revisions",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 800,
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
        "formatversion": 2,
    }
    payload = json.loads(request(f"{API}?{urlencode(params)}"))
    pages = payload.get("query", {}).get("pages", [])
    if len(pages) != 1 or pages[0].get("title") != TITLE:
        raise RuntimeError("Wikimedia Commons returned an unexpected file record")
    page = pages[0]
    image_info = page.get("imageinfo", [{}])[0]
    metadata = image_info.get("extmetadata", {})
    revisions = page.get("revisions", [])
    wikitext = revisions[0].get("slots", {}).get("main", {}).get("content", "") if revisions else ""
    if f"{{{{Monument Brussels|{EXPECTED_MONUMENT_ID}}}}}" not in wikitext:
        raise RuntimeError(f"Commons record is missing monument id {EXPECTED_MONUMENT_ID}")
    if EXPECTED_DESCRIPTION not in wikitext:
        raise RuntimeError(f"Commons record is missing description {EXPECTED_DESCRIPTION!r}")
    licence = metadata.get("LicenseShortName", {}).get("value")
    taken = metadata.get("DateTimeOriginal", {}).get("value") or metadata.get("DateTime", {}).get("value", "")
    if licence != EXPECTED_LICENSE:
        raise RuntimeError(f"unexpected Commons licence: {licence!r}")
    if "2011" not in taken:
        raise RuntimeError(f"unexpected Commons image date: {taken!r}")
    thumbnail_url = image_info.get("thumburl")
    if not thumbnail_url:
        raise RuntimeError("Wikimedia Commons did not return a thumbnail URL")
    body = request(thumbnail_url)
    if not body.startswith(b"\xff\xd8\xff"):
        raise RuntimeError("Wikimedia Commons response is not a JPEG")
    digest = hashlib.sha256(body).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"Wikimedia Commons preview checksum changed: {digest}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(body)
    OUTPUT.chmod(0o644)
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({len(body):,} bytes)")
    print(f"source: {image_info.get('descriptionurl')}; licence: {licence}; date: {taken}")
    print(f"identity: {EXPECTED_DESCRIPTION}; monument id: {EXPECTED_MONUMENT_ID}")


if __name__ == "__main__":
    main()
