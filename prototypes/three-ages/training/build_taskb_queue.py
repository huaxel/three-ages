#!/usr/bin/env python3
"""Build the task-B review queue: buildings whose construction era a human must decide.

The queue is stratifiable only by PROXIES (architect/catalogue years, styles), and
proxies are not labels — that is the whole reason task B is blocked. Proxies are
used here for one purpose: make the 60-building first batch cover the space
instead of whatever the file order happens to give.

Output columns match the label contract in
docs/three-ages-task-b-label-campaign.md, with the label fields blank.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from epoch_data import CONSTRUCTION_ERAS  # noqa: E402

REPO = HERE.parents[2]
DATA = REPO / 'local' / 'training'
PER_BIN = 10


def bin_of(year: int) -> str:
    # Keep in sync with extract_notice_evidence.bin_of: wartime gap years
    # (1915-1917, 1941-1944) belong to no named era, so proxies from those
    # years stratify as '' rather than silently joining a neighbouring bin.
    if 1915 <= year <= 1917 or 1941 <= year <= 1944:
        return ''
    if year < 1850: return 'pre-1850'
    if year < 1893: return '1850-1892'
    if year < 1915: return '1893-1914'
    if year < 1941: return '1918-1940'
    if year < 1976: return '1945-1975'
    return 'post-1975'


def scraped_records(root: Path) -> dict[str, dict]:
    out = {}
    for path in sorted(root.glob('*.fr.json')):
        try:
            d = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(d, list):
            continue  # index-style payload, not a record
        bid = str(d.get('building_id') or '') if isinstance(d, dict) else ''
        if bid:
            out[bid] = d
    return out


def years_of(record: dict) -> list[int]:
    years = []
    for c in record.get('contributors') or []:
        for value in c.get('years') or []:
            try:
                years.append(int(str(value)[:4]))
            except ValueError:
                continue
    return sorted({y for y in years if 1200 < y < 2030})


def image_stats(manifest: Path) -> dict[str, dict]:
    stats = defaultdict(lambda: {'images': 0, 'eras': set(), 'mapillary': 0})
    for row in csv.DictReader(manifest.open(encoding='utf-8')):
        bid = row['building_id']
        entry = stats[bid]
        entry['images'] += 1
        if row.get('capture_era'):
            entry['eras'].add(row['capture_era'])
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--scraped', default=str(REPO / 'local' / 'scraped'))
    ap.add_argument('--manifest', default=str(DATA / 'manifest.csv'))
    ap.add_argument('--mapillary-manifest', default=str(DATA / 'mapillary_manifest.csv'))
    ap.add_argument('--out', default=str(DATA / 'taskb_queue.csv'))
    ap.add_argument('--force', action='store_true',
                    help='overwrite a queue with no reviewer edits in it')
    args = ap.parse_args()

    records = scraped_records(Path(args.scraped))
    stats = image_stats(Path(args.manifest))
    map_counts = defaultdict(int)
    for row in csv.DictReader(Path(args.mapillary_manifest).open(encoding='utf-8')):
        map_counts[row['building_id']] += 1

    candidates = []
    for bid, rec in records.items():
        years = years_of(rec)
        if not years:
            continue
        st = stats.get(bid)
        if not st or st['images'] == 0:
            continue
        identity = rec.get('identity') or {}
        street = str(identity.get('street') or '').strip()
        number = str(identity.get('house_number') or '').strip()
        name = str(identity.get('name') or '').strip()
        # Some records are named complexes with no street number; a blank
        # address is useless to a reviewer, so fall back to the name.
        address = f'{street} {number}'.strip() if street else name
        candidates.append({
            'building_id': bid,
            'address': address,
            'notice_url': rec.get('url') or identity.get('address_url') or '',
            'proxy_years': ';'.join(str(y) for y in years),
            'proxy_bin': bin_of(years[0]),
            'styles': ';'.join(rec.get('styles') or []),
            'typologies': ';'.join(rec.get('typologies') or []),
            'publisher_images': st['images'],
            'publisher_eras': len(st['eras']),
            'mapillary_frames': map_counts.get(bid, 0),
        })

    # Prefer buildings with several eras (they anchor the disentanglement slices),
    # then by image count, then deterministically by id.
    for c in candidates:
        c['_multi'] = c['publisher_eras'] >= 2 and c['mapillary_frames'] > 0
    candidates.sort(key=lambda c: (not c['_multi'], -c['publisher_eras'],
                                   -c['publisher_images'], c['building_id']))

    chosen, per_bin = [], defaultdict(int)
    for c in candidates:
        if per_bin[c['proxy_bin']] >= PER_BIN:
            continue
        chosen.append(c)
        per_bin[c['proxy_bin']] += 1
    # Fill any shortfall from the remaining pool, still one per building.
    if len(chosen) < PER_BIN * len(CONSTRUCTION_ERAS):
        for c in candidates:
            if c not in chosen:
                chosen.append(c)
            if len(chosen) >= PER_BIN * len(CONSTRUCTION_ERAS):
                break

    fields = ['building_id', 'address', 'notice_url', 'proxy_years', 'proxy_bin',
              'styles', 'typologies', 'publisher_images', 'publisher_eras',
              'mapillary_frames', 'construction_era', 'evidence', 'reviewer',
              'reviewed_at', 'confidence']
    out = Path(args.out)
    if out.exists() and not args.force:
        raise SystemExit(f'{out} exists; refusing to overwrite a queue under review')
    if out.exists() and any(
            row['reviewer'].strip() or row['construction_era'].strip()
            for row in csv.DictReader(out.open(encoding='utf-8'))):
        raise SystemExit(f'{out} has reviewer edits; --force will not clobber them')
    with out.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for c in chosen:
            writer.writerow(c)
    print(json.dumps({
        'queue': str(out), 'rows': len(chosen),
        'per_proxy_bin': dict(per_bin),
        'pool_size': len(candidates),
        'multi_era_with_mapillary': sum(1 for c in chosen if c['_multi']),
        'note': 'proxy_years/proxy_bin are hints for the reviewer, NOT labels',
    }, indent=2), flush=True)


if __name__ == '__main__':
    main()
