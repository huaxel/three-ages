#!/usr/bin/env python3
"""Exploratory spent-test evaluation: frozen vs tuned, both legs.

Both arms use embeddings built by the SAME toolchain in this venv, at the same
settings, and the report records hashes of every input so the numbers can be
attributed to specific weights and caches.

Publisher queries are test-split images; the gallery is the full publisher
corpus (test images act as distractors, only test rows are scored as queries).
Cross-pole queries are test-split Mapillary frames.

This cohort has already been inspected for multiple checkpoints. Recomputing
fixed artifacts does not restore holdout independence. New confirmation needs
a separately frozen cohort; this entrypoint reports exploratory results only.
"""
from __future__ import annotations
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_local_pilot import ROOT, MODEL, PRETRAINED, check_splits, load_rows  # noqa: E402
from stats import building_macro_mean, paired_grouped_bootstrap  # noqa: E402


def resolve(value: str) -> Path:
    """Accept either a path relative to cwd or one relative to this directory."""
    candidate = Path(value)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    return ROOT / value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vectors(path: Path, rows, *, checkpoint_sha256='', expected_model=None):
    with np.load(path, allow_pickle=False) as data:
        keys = data['ids'].tolist()
        pos = {str(k): i for i, k in enumerate(keys)}
        if len(pos) != len(keys):
            raise ValueError(f'duplicate ids in {path}')
        v = np.asarray(data['embeddings'], dtype='float32')[
            [pos[f"{r['building_id']}/{r['filename']}"] for r in rows]]
        toolchain = str(data['toolchain']) if 'toolchain' in data else 'unrecorded'
        model = str(data['model'])
        if expected_model is not None:
            backbone = model.split('+tuned:', 1)[0]
            if backbone != expected_model or bool('+tuned:' in model) != bool(checkpoint_sha256):
                raise ValueError(f'cache backbone/tuning identity mismatch: {path}')
        recorded_checkpoint = str(data['checkpoint_sha256']) if 'checkpoint_sha256' in data else ''
        if recorded_checkpoint != checkpoint_sha256:
            raise ValueError(f'cache checkpoint mismatch: {path}')
        if toolchain == 'unrecorded' or not toolchain.strip():
            raise ValueError(f'cache lacks recorded toolchain: {path}; re-encode before comparison')
    if not np.isfinite(v).all():
        raise ValueError(f'nonfinite vectors in {path}')
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError(f'zero vectors in {path}')
    return v / norms, toolchain, model


def evaluate(pub, pvec, map_test, mvec):
    qidx = [i for i, r in enumerate(pub) if r['split'] == 'test']
    from train_local_pilot import metrics
    return {'publisher_test': metrics([pub[i] for i in qidx], pvec[qidx], pub, pvec, return_outcomes=True),
            'cross_pole_test': metrics(map_test, mvec, pub, pvec, return_outcomes=True)}


def paired_comparison(frozen, tuned):
    """Aligned outcomes; resample connected shared-image/building clusters."""
    result = {}
    for leg in ('publisher_test', 'cross_pole_test'):
        a, b = frozen[leg]['outcomes'], tuned[leg]['outcomes']
        if [(r['id'], r['group']) for r in a] != [(r['id'], r['group']) for r in b]:
            raise ValueError('unpaired evaluation outcomes')
        result[leg] = {}
        for metric in ('top5', 'cross_era_top5_fair'):
            selected = [(x, y) for x, y in zip(a, b) if x[metric] is not None]
            if any((x[metric] is None) != (y[metric] is None) for x, y in zip(a, b)):
                raise ValueError('eligibility differs between arms')
            if not selected:
                result[leg][metric] = None
                continue
            ids = [x['group'] for x, _ in selected]
            old = [x[metric] for x, _ in selected]
            new = [y[metric] for _, y in selected]
            building_ids = [x['building_id'] for x, _ in selected]
            block = {
                'building_macro_frozen': building_macro_mean(building_ids, old),
                'building_macro_tuned': building_macro_mean(building_ids, new),
                'independent_groups': len(set(ids)),
            }
            # CI estimates are for group-macro and image-weighted effects.
            # Group macro is distinct from building macro when buildings share pixels.
            for weighting in ('building_macro', 'image_micro'):
                estimate = paired_grouped_bootstrap(ids, new, old, weighting=weighting)
                estimate['n_groups'] = estimate.pop('n_buildings')
                estimate['weighting'] = 'group_macro' if weighting == 'building_macro' else weighting
                block[estimate['weighting'] + '_paired_difference'] = estimate
            result[leg][metric] = block
    return result


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--tag', default='v2', help='output report_test_<tag>.json')
    ap.add_argument('--checkpoint', default='pilot-20261022-232106/checkpoint.pt')
    ap.add_argument('--publisher-cache', default='embeddings_tuned_seed42.npz')
    ap.add_argument('--mapillary-cache', default='mapillary_embeddings_tuned_seed42.npz')
    ap.add_argument('--note', default='')
    ap.add_argument('--frozen-publisher-cache', default='embeddings_frozen_venv.npz')
    ap.add_argument('--frozen-mapillary-cache', default='mapillary_embeddings.npz')
    ap.add_argument('--publisher-manifest', type=Path, default=ROOT/'manifest.csv')
    ap.add_argument('--mapillary-manifest', type=Path, default=ROOT/'mapillary_manifest.csv')
    ap.add_argument('--acknowledge-spent-test', action='store_true')
    args = ap.parse_args()
    if not args.acknowledge_spent_test:
        ap.error('existing test cohort is spent; explicit exploratory acknowledgement required')
    out = ROOT / f'report_test_{args.tag}.json'
    if out.exists():
        ap.error(f'{out} exists; refusing to overwrite')
    pub = load_rows(args.publisher_manifest, ROOT.parent / 'monument-inbox', 'pub')
    mmap = load_rows(args.mapillary_manifest,
                     ROOT.parent / 'mapillary-inbox', 'map')
    check_splits(pub, mmap)
    import torch
    state = torch.load(resolve(args.checkpoint), map_location='cpu', weights_only=False)
    expected = {'publisher': sha(args.publisher_manifest), 'mapillary': sha(args.mapillary_manifest)}
    if state.get('verified_manifest_sha256') != expected:
        raise ValueError('checkpoint lacks matching image-isolated training provenance; '
                         'filtering evaluation alone cannot repair leaked training')
    # Declared historical unreadable-cache exclusion; no arbitrary cache
    # intersection may silently change the query/gallery denominator.
    excluded = [r['_id'] for r in pub if r['_id'] == 'pub/17387/11500227_0192_P04.jpg']
    pub = [r for r in pub if r['_id'] not in excluded]
    map_test = [r for r in mmap if r['split'] == 'test']

    # Same-toolchain arms: every cache here was built in this venv.
    checkpoint_hash = sha(resolve(args.checkpoint))
    backbone = f'{MODEL}/{PRETRAINED}'
    if state.get('model') != MODEL or state.get('pretrained') != PRETRAINED:
        raise ValueError('checkpoint backbone mismatch')
    fp, ftc, fpm = vectors(ROOT / args.frozen_publisher_cache, pub, expected_model=backbone)
    fm, mtc, _ = vectors(ROOT / args.mapillary_cache, map_test,
                         checkpoint_sha256=checkpoint_hash, expected_model=backbone)
    fm_frozen, fmtc, _ = vectors(ROOT / args.frozen_mapillary_cache, map_test, expected_model=backbone)
    tp, ttc, tpm = vectors(ROOT / args.publisher_cache, pub,
                          checkpoint_sha256=checkpoint_hash, expected_model=backbone)
    if len({ftc, mtc, fmtc, ttc}) != 1:
        raise ValueError('all four caches must have identical recorded toolchains')

    report = {
        'note': 'Exploratory reuse of an already inspected test cohort; not locked confirmation.',
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'publisher_gallery': len(pub), 'cross_pole_queries': len(map_test),
        'inputs': {name: sha(ROOT / name) for name in
                   (args.frozen_publisher_cache, args.frozen_mapillary_cache,
                    args.publisher_cache, args.mapillary_cache)},
        'manifest_sha256': expected,
        'excluded_ids': excluded,
        'exclusion_reason': 'declared historical missing publisher embedding; no other cache gaps permitted',
        'checkpoint': {'path': str(resolve(args.checkpoint)),
                       'sha256': sha(resolve(args.checkpoint))},
        'extra_note': args.note,
        'toolchains': {'frozen': ftc, 'tuned': ttc},
        'frozen': evaluate(pub, fp, map_test, fm_frozen),
        'tuned': evaluate(pub, tp, map_test, fm),
    }
    report['paired_grouped_comparison'] = paired_comparison(report['frozen'], report['tuned'])
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
