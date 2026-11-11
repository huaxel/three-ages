#!/usr/bin/env python3
"""Fetch only the eight byte-pinned owner-portfolio transfer references; no inference."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from prepare import ROOT, fetch_reference


def prepare(plan_path=None):
    plan = json.loads((Path(plan_path) if plan_path else Path(__file__).with_name('pool').joinpath('transfer-plan.json')).read_text())
    for source in plan['subjects']:
        if not re.fullmatch(r's-\d{9,16}', source['id']) or not re.fullmatch(r'[a-f0-9]{64}', source['sha256']):
            raise ValueError('Invalid source identity')
        url = urlsplit(source['image'])
        if url.scheme != 'https' or url.hostname != '64.media.tumblr.com' or url.username or url.password or url.port:
            raise ValueError('Unapproved source URL')
        fetch_reference(ROOT / 'local/paint-brussels/batch/detail-references' / (source['id'] + '.jpg'), source['image'], source['sha256'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', help='Pinned data-only source plan; defaults to the first transfer round')
    prepare(parser.parse_args().plan)
