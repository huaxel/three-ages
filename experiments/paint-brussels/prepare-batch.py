#!/usr/bin/env python3
"""Fetch pinned owner-linked photos locally. No model calls, uploads or training."""
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from prepare import ROOT, fetch_reference


def load_catalog(path):
    data = Path(path).read_bytes()
    if len(data) > 32768:
        raise ValueError('Catalog exceeds byte limit')
    catalog = json.loads(data)
    if not isinstance(catalog, dict) or set(catalog) != {'version', 'items'} or isinstance(catalog['version'], bool) or catalog['version'] != 1:
        raise ValueError('Invalid catalog version/fields')
    items = catalog['items']
    if not isinstance(items, list) or not 1 <= len(items) <= 24:
        raise ValueError('Expected 1..24 pilot sources')
    ids, filenames = set(), set()
    fields = {'id', 'title', 'place', 'post', 'image', 'sha256', 'file', 'scene'}
    for item in items:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError('Invalid source fields')
        if not isinstance(item['id'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,39}', item['id']) or item['id'] in ids:
            raise ValueError('Invalid/duplicate ID')
        ids.add(item['id'])
        for key in ('title', 'place'):
            if not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 160:
                raise ValueError('Invalid source text')
        filename = item['file']
        if not isinstance(filename, str) or not re.fullmatch(r'\d{9,16}\.jpg', filename) or filename in filenames:
            raise ValueError('Invalid/duplicate filename')
        filenames.add(filename)
        if item['scene'] != f"{item['id']}.json" or not isinstance(item['sha256'], str) or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']):
            raise ValueError('Invalid scene filename or checksum')
        for key, host in [('image', '64.media.tumblr.com'), ('post', 'buildingsofbrussels.tumblr.com')]:
            if not isinstance(item[key], str):
                raise ValueError('Source URL must be text')
            parsed = urlsplit(item[key])
            if parsed.scheme != 'https' or parsed.hostname != host or parsed.username or parsed.password or parsed.port:
                raise ValueError('Unapproved source URL')
    return items


def prepare():
    items = load_catalog(Path(__file__).with_name('batch-catalog.json'))
    for item in items:
        fetch_reference(ROOT / 'local/paint-brussels/batch' / item['file'], item['image'], item['sha256'])


if __name__ == '__main__':
    prepare()
