#!/usr/bin/env python3
"""Audit exact-image split leakage and write NEW quarantined manifests.

Mapillary source IDs and SHA-256 bytes are identity keys; publisher filenames
are not. Hashes are recomputed from disk, never trusted from a manifest. This
catches exact duplicates, not near-duplicates or adjacent camera frames.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def image_groups(pub: list[dict], mmap: list[dict]) -> list[dict]:
    """Return shared identity groups, including transitive source/hash matches."""
    rows = pub + mmap
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owners = {}
    for i, row in enumerate(rows):
        row['_sha256'] = sha256(Path(row['_path']))
        keys = [('sha256', row['_sha256'])]
        if i >= len(pub) and row.get('source_filename'):
            keys.append(('mapillary', row['source_filename']))
        for key in keys:
            if key in owners:
                parent[root(i)] = root(owners[key])
            else:
                owners[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[root(i)].append(row)
    for group in groups.values():
        identity = min(r.get('_id', f"{r['building_id']}/{r['filename']}") for r in group)
        for row in group:
            row['_image_identity'] = identity
    return [dict(rows=group,
                 splits=sorted({r['split'] for r in group}),
                 buildings=sorted({r['building_id'] for r in group}))
            for group in groups.values() if len(group) > 1]


def assert_image_isolation(pub: list[dict], mmap: list[dict]) -> None:
    groups = image_groups(pub, mmap)
    leaks = [g for g in groups if len(g['splits']) > 1]
    if leaks:
        sample = [r.get('_id', f"{r['building_id']}/{r['filename']}")
                  for r in leaks[0]['rows']]
        raise ValueError(f"Shared-image split leakage: {len(leaks)} groups; "
                         f"example {sample}. Run training/data_integrity.py into "
                         "a NEW output directory; existing results are exploratory.")
    # Dependence can remain within one split. Bootstrap connected buildings,
    # not individual assignments of a shared street-view frame.
    parent = {r['building_id']: r['building_id'] for r in pub + mmap}

    def root(bid):
        while parent[bid] != bid:
            parent[bid] = parent[parent[bid]]
            bid = parent[bid]
        return bid

    for group in groups:
        first = group['buildings'][0]
        for bid in group['buildings'][1:]:
            a, b = root(first), root(bid)
            parent[max(a, b)] = min(a, b)
    for row in pub + mmap:
        row['_evaluation_group'] = root(row['building_id'])


def load(path: Path, image_root: Path, pole: str) -> tuple[list[dict], list[str]]:
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        rows, fields = list(reader), reader.fieldnames
    if not fields or not rows:
        raise ValueError(f'empty manifest: {path}')
    seen, buildings = set(), {}
    for row in rows:
        bid, filename = row['building_id'], row['filename']
        if row['split'] not in ('train', 'val', 'test'):
            raise ValueError(f'unknown split in {path}')
        if bid in buildings and buildings[bid] != row['split']:
            raise ValueError(f'building split leakage: {bid}')
        buildings[bid] = row['split']
        row['_id'] = f'{pole}/{bid}/{filename}'
        if row['_id'] in seen:
            raise ValueError(f'duplicate image id: {row["_id"]}')
        seen.add(row['_id'])
        row['_path'] = image_root / bid / filename
    return rows, fields


def audit(pub, mmap):
    groups = image_groups(pub, mmap)
    leaks = [g for g in groups if len(g['splits']) > 1]
    excluded = {r['_id'] for g in leaks for r in g['rows']}
    report = {
        'schema': 'shared-image-audit/1',
        'policy': 'quarantine all copies of cross-split shared source IDs or exact bytes',
        'limits': 'No near-duplicate, camera-sequence or human identity verification',
        'rows': {'publisher': len(pub), 'mapillary': len(mmap)},
        'shared_groups': len(groups),
        'cross_split_groups': len(leaks),
        'excluded_rows': len(excluded),
        'excluded_by_pole_split': dict(sorted(Counter(
            (r['_id'].split('/')[0] + '/' + r['split'])
            for r in pub + mmap if r['_id'] in excluded).items())),
        'groups': [{'ids': [r['_id'] for r in g['rows']],
                    'splits': g['splits'], 'buildings': g['buildings']}
                   for g in groups],
    }
    return report, excluded


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    ap.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    ap.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    ap.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    ap.add_argument('--out-dir', type=Path, required=True, help='new directory; existing paths refused')
    ap.add_argument('--audit-only', action='store_true', help='write report only, no filtered manifests')
    args = ap.parse_args()
    if args.out_dir.exists():
        ap.error('output directory exists; refusing to replace any artifacts')
    pub, pf = load(args.publisher_manifest, args.publisher_root, 'pub')
    mmap, mf = load(args.mapillary_manifest, args.mapillary_root, 'map')
    # One building must remain in one split across poles as well.
    building_splits = defaultdict(set)
    for row in pub + mmap:
        building_splits[row['building_id']].add(row['split'])
    if any(len(s) > 1 for s in building_splits.values()):
        raise ValueError('building split leakage across poles')
    report, excluded = audit(pub, mmap)
    report['input_sha256'] = {name: sha256(path) for name, path in (
        ('publisher_manifest', args.publisher_manifest),
        ('mapillary_manifest', args.mapillary_manifest))}
    report['code_sha256'] = sha256(Path(__file__))
    # Do all reads/validation before creating any output.
    args.out_dir.mkdir(parents=True, exist_ok=False)
    if not args.audit_only:
        for name, rows, fields in [('manifest.csv', pub, pf), ('mapillary_manifest.csv', mmap, mf)]:
            with (args.out_dir/name).open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(r for r in rows if r['_id'] not in excluded)
    (args.out_dir/'shared-image-audit.json').write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'groups'}, indent=2))


if __name__ == '__main__':
    main()
