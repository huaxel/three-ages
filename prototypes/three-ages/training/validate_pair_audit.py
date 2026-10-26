#!/usr/bin/env python3
"""Validate a returned training pair audit; write only a NEW JSON report.

This checks reproducibility, not reviewer honesty or authenticated provenance.
SHA-256 checks exact file bytes (as in the preparer), not decoded pixels.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, datetime
import json
from pathlib import Path

from data_integrity import load, sha256
from pair_sampling import mine_pairs
from prepare_pair_audit import FIELDS, prepare
from stats import paired_grouped_bootstrap

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
HISTORICAL_EXCLUDED_ID = 'pub/17387/11500227_0192_P04.jpg'
REVIEW_FIELDS = ['identity', 'evidence', 'reviewer', 'reviewed_at', 'confidence']
IDENTITIES = ['correct', 'ambiguous', 'incorrect']
METADATA_FIELDS = {'schema', 'training_seed', 'sample_seed', 'sampled_pairs',
                   'available_cross_pole_pairs', 'sampling_unit', 'identity_values',
                   'status', 'limits', 'manifest_sha256', 'sampler_sha256'}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def read_metadata(path, publisher_manifest, mapillary_manifest):
    with path.open(encoding='utf-8') as handle:
        meta = json.load(handle, object_pairs_hook=strict_object)
    if not isinstance(meta, dict) or set(meta) != METADATA_FIELDS:
        raise ValueError('unexpected sample.json fields')
    constants = {
        'schema': 'training-pair-audit/1',
        'sampling_unit': 'uniform pairs from actual capped training sample',
        'identity_values': IDENTITIES,
        'status': 'unreviewed; no identity cleanliness estimate yet',
        'limits': 'Pair-weighted sample, not building-uniform; repeated buildings possible',
    }
    for key, expected in constants.items():
        if meta[key] != expected:
            raise ValueError(f'invalid sample metadata: {key}')
    for key in ('training_seed', 'sample_seed', 'sampled_pairs', 'available_cross_pole_pairs'):
        if type(meta[key]) is not int:
            raise ValueError(f'metadata {key} must be an integer')
    if not 0 < meta['sampled_pairs'] <= meta['available_cross_pole_pairs']:
        raise ValueError('invalid sample size')
    expected_hashes = {'publisher': sha256(publisher_manifest),
                       'mapillary': sha256(mapillary_manifest)}
    if meta['manifest_sha256'] != expected_hashes:
        raise ValueError('input manifest hash mismatch')
    if meta['sampler_sha256'] != sha256(HERE / 'pair_sampling.py'):
        raise ValueError('current sampler hash mismatch')
    return meta


def valid_date(value):
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat() == value
        # Accept ISO dates or ISO timestamps, not arbitrary free-form dates.
        if len(value) > 10 and value[10] == 'T':
            datetime.fromisoformat(value.replace('Z', '+00:00'))
            return True
    except ValueError:
        pass
    return False


def read_reviews(path, expected):
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle, strict=True)
        if (not reader.fieldnames or len(reader.fieldnames) != len(FIELDS)
                or set(reader.fieldnames) != set(FIELDS)):
            raise ValueError('review CSV fields must match preparer schema exactly')
        rows = list(reader)
    by_id = {r['pair_id']: r for r in expected}
    seen = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('malformed CSV row')
        pid = row['pair_id']
        if pid in seen:
            raise ValueError(f'duplicate pair ID: {pid}')
        seen.add(pid)
        if pid not in by_id:
            raise ValueError(f'extra or changed pair ID: {pid}')
        for key in FIELDS:
            if key not in REVIEW_FIELDS and row[key] != by_id[pid][key]:
                raise ValueError(f'immutable field mismatch: {pid}: {key}')
        values = [row[key].strip() for key in REVIEW_FIELDS]
        if not any(values):
            continue  # Pending is not a label.
        if not all(values):
            raise ValueError(f'partially filled reviewer row: {pid}')
        if row['identity'] not in IDENTITIES:
            raise ValueError(f'unknown identity decision: {pid}')
        if row['confidence'] not in ('low', 'medium', 'high'):
            raise ValueError(f'unknown confidence: {pid}')
        if not valid_date(row['reviewed_at']):
            raise ValueError(f'invalid ISO review date: {pid}')
    if seen != set(by_id):
        raise ValueError('missing sampled pair IDs')
    return sorted(rows, key=lambda row: row['pair_id'])


def sampled_components(rows):
    """Connect pairs by building, shared Mapillary source, or either byte hash."""
    parent = list(range(len(rows)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owners = {}
    for i, row in enumerate(rows):
        keys = [('building', row['building_id']),
                ('hash', row['publisher_sha256']), ('hash', row['mapillary_sha256'])]
        if row['mapillary_source_id']:
            keys.append(('source', row['mapillary_source_id']))
        for key in keys:
            if key in owners:
                parent[root(i)] = root(owners[key])
            else:
                owners[key] = i
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        groups[root(i)].append(row['pair_id'])
    labels = {pid: min(group) for group in groups.values() for pid in group}
    return [labels[row['pair_id']] for row in rows]


def validate(sample, reviews, publisher_manifest, mapillary_manifest,
             publisher_root, mapillary_root):
    meta = read_metadata(sample, publisher_manifest, mapillary_manifest)
    pub, _ = load(publisher_manifest, publisher_root, 'pub')
    mmap, _ = load(mapillary_manifest, mapillary_root, 'map')
    pub = [r for r in pub if r['_id'] != HISTORICAL_EXCLUDED_ID]
    expected, _, available = prepare(pub, mmap, seed=meta['training_seed'],
                                    samples=meta['sampled_pairs'], sample_seed=meta['sample_seed'])
    if available != meta['available_cross_pole_pairs']:
        raise ValueError('available pair count mismatch')
    rows = read_reviews(reviews, expected)
    all_pairs, _ = mine_pairs(pub, mmap, seed=meta['training_seed'])
    population = Counter(a['building_id'] for a, b in all_pairs if b['_id'].startswith('map/'))
    counts = Counter(row['identity'] if row['identity'].strip() else 'pending' for row in rows)
    n, reviewed = len(rows), len(rows) - counts['pending']
    groups = sampled_components(rows)
    support = {}
    for bid, total in sorted(population.items()):
        selected = [row for row in rows if row['building_id'] == bid]
        decisions = Counter(row['identity'] if row['identity'].strip() else 'pending' for row in selected)
        support[bid] = {'available_pairs': total, 'sampled_pairs': len(selected),
                        'reviewed_pairs': len(selected) - decisions['pending'],
                        'counts': {key: decisions[key] for key in IDENTITIES + ['pending']}}
    report = {
        'schema': 'training-pair-audit-validation/1',
        'status': 'fully reviewed' if reviewed == n else 'pending reviews',
        'training_seed': meta['training_seed'], 'sample_seed': meta['sample_seed'],
        'historical_excluded_id': HISTORICAL_EXCLUDED_ID,
        'input_sha256': {'sample': sha256(sample), 'reviews': sha256(reviews),
                         'publisher_manifest': sha256(publisher_manifest),
                         'mapillary_manifest': sha256(mapillary_manifest),
                         'sampler': sha256(HERE / 'pair_sampling.py'),
                         'preparer': sha256(HERE / 'prepare_pair_audit.py'),
                         'validator': sha256(Path(__file__)),
                         'statistics': sha256(HERE / 'stats.py')},
        'counts': {key: counts[key] for key in IDENTITIES + ['pending']},
        'coverage': {'sampled_pairs': n, 'available_pairs': available,
                     'sample_fraction': n / available, 'reviewed_pairs': reviewed,
                     'review_fraction': reviewed / n,
                     'sampled_buildings': len({r['building_id'] for r in rows}),
                     'available_buildings': len(population),
                     'sampled_components': len(set(groups))},
        'per_building': support,
        'cleanliness': None,
        'limits': [
            'Uniform pair sample from one seed of the capped training sampler; not building-uniform or full-corpus cleanliness.',
            'Ambiguous is not correct. Pending reviews never imply labels or cleanliness.',
            'Hashes check exact bytes, not near duplicates, camera sequences, or reviewer honesty.',
            'Unsigned sample metadata is not authenticated; coordinated rewriting of inputs and hashes cannot be detected.',
            'Dependence components use sampled buildings, source IDs and exact hashes only; unseen links may remain.',
            'No quarantine, model evaluation or training is performed.',
        ],
    }
    if reviewed == n:
        scores = [float(row['identity'] == 'correct') for row in rows]
        uncertainty = None
        if len(set(groups)) > 1:
            result = paired_grouped_bootstrap(groups, scores, [0.0] * n,
                                              weighting='image_micro')
            uncertainty = {'method': 'sampled connected-component percentile bootstrap',
                           'ci': result['ci'], 'confidence': result['confidence'],
                           'n_resamples': result['n_resamples'], 'seed': result['seed'],
                           'n_components': result['n_buildings'],
                           'limits': 'Descriptive approximate interval; sparse or homogeneous components can yield degenerate bounds; no finite-population correction.'}
        report['cleanliness'] = {
            'estimand': 'correct fraction of this seed capped cross-pole pair population',
            'correct_fraction': counts['correct'] / n,
            'uncertainty': uncertainty,
            'uncertainty_note': 'Unavailable with one dependence component' if uncertainty is None
                                else 'Resamples whole connected components, retaining pair weights',
        }
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--sample', type=Path, help='prepared sample.json')
    source.add_argument('--audit-dir', type=Path, help='directory holding sample.json and reviews.csv')
    ap.add_argument('--reviews', type=Path, help='returned CSV; defaults beside sample.json')
    ap.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    ap.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    ap.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    ap.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    ap.add_argument('--out', type=Path, required=True, help='NEW report file; existing paths refused')
    args = ap.parse_args()
    if args.out.exists() or args.out.is_symlink():
        ap.error('output exists; refusing to overwrite any artifact')
    sample = args.sample if args.sample else args.audit_dir / 'sample.json'
    reviews = args.reviews if args.reviews else sample.parent / 'reviews.csv'
    try:
        report = validate(sample, reviews, args.publisher_manifest, args.mapillary_manifest,
                          args.publisher_root, args.mapillary_root)
    except (ValueError, OSError, KeyError, csv.Error) as exc:
        ap.error(str(exc))
    # Exclusive creation also guards against races and symlink overwrites.
    with args.out.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(f"{report['status']}: {report['coverage']['reviewed_pairs']}/"
          f"{report['coverage']['sampled_pairs']} reviewed; report: {args.out}")


if __name__ == '__main__':
    main()
