#!/usr/bin/env python3
"""Prepare an unlabelled CSV and contact sheet sampled from actual training pairs.

No inference or identity decisions. Samples pairs (not buildings) uniformly
from the selected seed's cross-pole training sample. Reviews stay blank.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import os
import random
from pathlib import Path

from data_integrity import load, sha256
from pair_sampling import mine_pairs

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FIELDS = ['pair_id', 'building_id', 'publisher_filename', 'mapillary_filename',
          'mapillary_source_id', 'publisher_sha256', 'mapillary_sha256',
          'identity', 'evidence', 'reviewer', 'reviewed_at', 'confidence']


def prepare(pub, mmap, *, seed=42, samples=40, sample_seed=0):
    if samples < 1:
        raise ValueError('samples must be positive')
    pairs, _ = mine_pairs(pub, mmap, seed=seed)
    cross_pole = [(a, b) for a, b in pairs if b['_id'].startswith('map/')]
    if not cross_pole:
        raise ValueError('no cross-pole training pairs')
    chosen = random.Random(sample_seed).sample(cross_pole, min(samples, len(cross_pole)))
    rows = []
    for a, b in chosen:
        row = {key: '' for key in FIELDS}
        row.update(pair_id=a['_id']+'|'+b['_id'], building_id=a['building_id'],
                   publisher_filename=a['filename'], mapillary_filename=b['filename'],
                   mapillary_source_id=b.get('source_filename', ''),
                   publisher_sha256=sha256(a['_path']), mapillary_sha256=sha256(b['_path']))
        rows.append(row)
    return rows, chosen, len(cross_pole)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    ap.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    ap.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    ap.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--sample-seed', type=int, default=0)
    ap.add_argument('--samples', type=int, default=40)
    ap.add_argument('--out-dir', type=Path, required=True)
    args = ap.parse_args()
    if args.out_dir.exists():
        ap.error('output exists; refusing to overwrite audit or human reviews')
    pub, _ = load(args.publisher_manifest, args.publisher_root, 'pub')
    mmap, _ = load(args.mapillary_manifest, args.mapillary_root, 'map')
    # Exactly the one historical missing-cache row excluded by the pilot.
    pub = [r for r in pub if r['_id'] != 'pub/17387/11500227_0192_P04.jpg']
    rows, pairs, available = prepare(pub, mmap, seed=args.seed, samples=args.samples,
                                     sample_seed=args.sample_seed)
    sections = []
    for row, (a, b) in zip(rows, pairs):
        pictures = []
        for image in (b, a):
            relative = os.path.relpath(image['_path'], args.out_dir)
            pictures.append(f'<figure><img src="{html.escape(relative, quote=True)}">'
                            f'<figcaption>{html.escape(image["_id"])}</figcaption></figure>')
        sections.append(f'<section><h2>{html.escape(row["pair_id"])}</h2>'
                        + ''.join(pictures) + '</section>')
    metadata = {'schema': 'training-pair-audit/1', 'training_seed': args.seed,
                'sample_seed': args.sample_seed, 'sampled_pairs': len(rows),
                'available_cross_pole_pairs': available,
                'sampling_unit': 'uniform pairs from actual capped training sample',
                'identity_values': ['correct', 'ambiguous', 'incorrect'],
                'status': 'unreviewed; no identity cleanliness estimate yet',
                'limits': 'Pair-weighted sample, not building-uniform; repeated buildings possible',
                'manifest_sha256': {'publisher': sha256(args.publisher_manifest),
                                    'mapillary': sha256(args.mapillary_manifest)},
                'sampler_sha256': sha256(HERE/'pair_sampling.py')}
    args.out_dir.mkdir(parents=True, exist_ok=False)
    with (args.out_dir/'reviews.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (args.out_dir/'sample.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    (args.out_dir/'index.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>Training pair identity audit</title>'
        '<style>body{font:14px system-ui}section{border-top:1px solid #ccc;padding:1em}'
        'figure{display:inline-block;width:45%;vertical-align:top;margin:1%}'
        'img{width:100%;max-height:400px;object-fit:contain}h2{overflow-wrap:anywhere}</style>'
        '<h1>Are these views of the assigned building?</h1>'
        '<p>Left: Mapillary. Right: publisher. Fill reviews.csv identity with correct, '
        'ambiguous or incorrect; record evidence, reviewer, date and confidence. '
        'No review fields have been inferred. Inspect the full scene, not just similarity.</p>'
        + ''.join(sections), encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
