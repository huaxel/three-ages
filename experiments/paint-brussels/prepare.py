#!/usr/bin/env python3
"""Fetch the one owner-supplied reference into ignored local storage; no uploads."""
import hashlib
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
URL = 'https://64.media.tumblr.com/073de691721dce57c05ba309feb16415/tumblr_os5s6i5A771vensaeo1_500.jpg'
SHA256 = '7e09f6e22ba769ad95d89c1719f7b41fcc2bcdd23b427b22d542773f6829b3cd'


def fetch_reference(destination, url, expected_sha256):
    destination = Path(destination)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != expected_sha256:
            raise SystemExit('Existing reference differs; preserved it without overwriting.')
        print(f'Reference already verified: {destination}')
        return
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(5_000_001)
    if len(data) > 5_000_000 or hashlib.sha256(data).hexdigest() != expected_sha256:
        raise SystemExit('Reference bytes differ from the pinned photograph; nothing saved.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves a file that appeared while the request was running.
    with destination.open('xb') as handle:
        handle.write(data)
    print(f'Verified reference: {destination}')


def prepare():
    fetch_reference(ROOT / 'local/paint-brussels/source.jpg', URL, SHA256)


if __name__ == '__main__':
    prepare()
