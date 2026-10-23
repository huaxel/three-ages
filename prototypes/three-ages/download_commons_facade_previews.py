#!/usr/bin/env python3
"""Download exact-case 2019 Grand-Place facade previews from Wikimedia Commons."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "data" / "historical"
API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "three-ages-facade-style-research/1.0"
MAX_RESPONSE_BYTES = 20 * 1024 * 1024
ALLOWED_HOSTS = {"commons.wikimedia.org", "upload.wikimedia.org", "thumb.wikimedia.org"}
ASSETS = {
    "commons-joseph-anne-2019": {
        "title": "File:Belgique - Bruxelles - Maison de Joseph et Anne - 04b.jpg",
        "monument_id": "2043-0065/021",
        "description": "Grand-Place n° 21-22 - Maison de Joseph et Anne",
        "output": "commons-joseph-anne-2019.jpg",
        "sha256": "ed5a9780fa329d30f65694b8166df287f0892f7e9f39bbd7bfef6861889e7d59",
    },
    "commons-angel-2019": {
        "title": "File:Belgique - Bruxelles - Maison de l'Ange - 00.jpg",
        "description": "Grand-Place n° 23 - Maison de l'Ange",
        "output": "commons-angel-2019.jpg",
        "sha256": "56778a89edcea59f6abe9e3478d8a9080ed823667ae0a3ec6b986cb6c5849668",
    },
    "commons-pigeon-2019": {
        "title": "File:Belgique - Bruxelles - Maison du Pigeon - 04.jpg",
        "monument_id": "2043-0065/026",
        "description": "Grand-Place n° 26-27 - Maison du Pigeon",
        "output": "commons-pigeon-2019.jpg",
        "sha256": "69356386f13668004a6898c1202e552d569e84b3c138d8b4336ea23dbad58a25",
    },
}


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise RuntimeError(f"refusing unexpected Wikimedia URL: {url}")


def request(url: str) -> bytes:
    validate_url(url)
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=60) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError(f"Wikimedia Commons response exceeds {MAX_RESPONSE_BYTES:,} bytes")
    return body


def fetch_preview(asset_id: str, expected: dict[str, str]) -> bytes:
    params = {
        "action": "query",
        "titles": expected["title"],
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
    if len(pages) != 1 or pages[0].get("title") != expected["title"]:
        raise RuntimeError(f"Commons returned an unexpected file record for {asset_id}")
    page = pages[0]
    info = page.get("imageinfo", [{}])[0]
    metadata = info.get("extmetadata", {})
    wikitext = page.get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
    monument_id = expected.get("monument_id")
    if monument_id and f"{{{{Monument Brussels|{monument_id}}}}}" not in wikitext:
        raise RuntimeError(f"{asset_id} is missing expected monument id {monument_id}")
    if expected["description"] not in wikitext:
        raise RuntimeError(f"{asset_id} is missing the exact building description")
    if metadata.get("LicenseShortName", {}).get("value") != "CC BY-SA 4.0":
        raise RuntimeError(f"{asset_id} does not have the expected CC BY-SA 4.0 licence")
    taken = metadata.get("DateTimeOriginal", {}).get("value", "")
    if not taken.startswith("2019-"):
        raise RuntimeError(f"{asset_id} has an unexpected capture date: {taken!r}")
    thumbnail_url = info.get("thumburl")
    if not thumbnail_url:
        raise RuntimeError(f"Commons did not provide a thumbnail URL for {asset_id}")
    body = request(thumbnail_url)
    if not body.startswith(b"\xff\xd8\xff"):
        raise RuntimeError(f"Commons preview for {asset_id} is not a JPEG")
    digest = hashlib.sha256(body).hexdigest()
    if digest != expected["sha256"]:
        raise RuntimeError(f"Commons preview checksum changed for {asset_id}: {digest}")
    return body


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for asset_id, expected in ASSETS.items():
        body = fetch_preview(asset_id, expected)
        destination = OUTPUT / expected["output"]
        destination.write_bytes(body)
        destination.chmod(0o644)
        print(f"wrote {destination.relative_to(ROOT)} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()
