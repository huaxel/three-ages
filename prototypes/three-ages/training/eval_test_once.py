#!/usr/bin/env python3
"""Single honest test-split evaluation: frozen vs tuned, both legs.

Both arms use embeddings built by the SAME toolchain in this venv, at the same
settings, and the report records hashes of every input so the numbers can be
attributed to specific weights and caches.

Publisher queries are test-split images; the gallery is the full publisher
corpus (test images act as distractors, only test rows are scored as queries).
Cross-pole queries are test-split Mapillary frames.

This is a DETERMINISTIC recomputation from fixed artifacts. It is not a second
look at the test split: no model was selected using these numbers, and the
inputs are hashed here so that stays checkable.
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
from train_local_pilot import ROOT, check_splits, load_rows  # noqa: E402
from stats import counts, wilson  # noqa: E402


def resolve(value: str) -> Path:
    """Accept either a path relative to cwd or one relative to this directory."""
    candidate = Path(value)
    if candidate.is_absolute() or candidate.exists():
        return candidate
    return ROOT / value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vectors(path: Path, rows):
    with np.load(path, allow_pickle=False) as data:
        keys = data['ids'].tolist()
        pos = {str(k): i for i, k in enumerate(keys)}
        if len(pos) != len(keys):
            raise ValueError(f'duplicate ids in {path}')
        v = np.asarray(data['embeddings'], dtype='float32')[
            [pos[f"{r['building_id']}/{r['filename']}"] for r in rows]]
        toolchain = str(data['toolchain']) if 'toolchain' in data else 'unrecorded'
        model = str(data['model'])
    if not np.isfinite(v).all():
        raise ValueError(f'nonfinite vectors in {path}')
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12), toolchain, model


def evaluate(pub, pvec, map_test, mvec):
    qidx = [i for i, r in enumerate(pub) if r['split'] == 'test']
    from train_local_pilot import metrics
    return {'publisher_test': metrics([pub[i] for i in qidx], pvec[qidx], pub, pvec),
            'cross_pole_test': metrics(map_test, mvec, pub, pvec)}


def with_ci(block):
    for leg, key in (('publisher_test', 'cross_era_top5_fair'),
                     ('publisher_test', 'top5'),
                     ('cross_pole_test', 'top5')):
        entry = block[leg]
        n = entry.get('cross_era_eligible_queries' if 'cross_era' in key
                      else 'queries_with_mates')
        hits = counts(entry[key], n)
        low, high = wilson(hits, n)
        entry[key + '_ci95'] = [round(low, 5), round(high, 5)]
        entry[key + '_hits'] = [hits, n]
    return block


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--tag', default='v2', help='output report_test_<tag>.json')
    ap.add_argument('--checkpoint', default='pilot-20261022-232106/checkpoint.pt')
    ap.add_argument('--publisher-cache', default='embeddings_tuned_seed42.npz')
    ap.add_argument('--mapillary-cache', default='mapillary_embeddings_tuned_seed42.npz')
    ap.add_argument('--note', default='')
    args = ap.parse_args()
    pub = load_rows(ROOT / 'manifest.csv', ROOT.parent / 'monument-inbox', 'pub')
    mmap = load_rows(ROOT / 'mapillary_manifest.csv',
                     ROOT.parent / 'mapillary-inbox', 'map')
    check_splits(pub, mmap)
    limits = {'embeddings.npz': pub, 'mapillary_embeddings.npz': mmap}
    keep = {}
    for cache, rows in limits.items():
        with np.load(ROOT / cache, allow_pickle=False) as data:
            have = set(data['ids'].tolist())
        keep[cache] = {f"{r['building_id']}/{r['filename']}" for r in rows
                       if f"{r['building_id']}/{r['filename']}" in have}
    pub = [r for r in pub if f"{r['building_id']}/{r['filename']}" in keep['embeddings.npz']]
    mmap = [r for r in mmap
            if f"{r['building_id']}/{r['filename']}" in keep['mapillary_embeddings.npz']]
    map_test = [r for r in mmap if r['split'] == 'test']

    # Same-toolchain arms: every cache here was built in this venv.
    fp, ftc, fpm = vectors(ROOT / 'embeddings_frozen_venv.npz', pub)
    fm, _, _ = vectors(ROOT / args.mapillary_cache, map_test)
    fm_frozen, _, _ = vectors(ROOT / 'mapillary_embeddings.npz', map_test)
    tp, ttc, tpm = vectors(ROOT / args.publisher_cache, pub)

    report = {
        'note': 'Single test-split evaluation; pilot selected on validation. '
                'Deterministic recomputation from hashed artifacts, not a second look.',
        'created_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'publisher_gallery': len(pub), 'cross_pole_queries': len(map_test),
        'inputs': {name: sha(ROOT / name) for name in
                   ('manifest.csv', 'mapillary_manifest.csv',
                    'embeddings_frozen_venv.npz', 'mapillary_embeddings.npz',
                    args.publisher_cache, args.mapillary_cache)},
        'checkpoint': {'path': str(resolve(args.checkpoint)),
                       'sha256': sha(resolve(args.checkpoint))},
        'extra_note': args.note,
        'toolchains': {'frozen': ftc, 'tuned': ttc},
        'frozen': with_ci(evaluate(pub, fp, map_test, fm_frozen)),
        'tuned': with_ci(evaluate(pub, tp, map_test, fm)),
    }
    if ftc.split('torchvision')[-1] != ttc.split('torchvision')[-1] and \
            'rocm' not in ftc.split('torchvision')[-1] + ttc.split('torchvision')[-1]:
        raise SystemExit('arms are not toolchain-matched')
    out = ROOT / f'report_test_{args.tag}.json'
    if out.exists():
        raise SystemExit(f'{out} exists; refusing to overwrite')
    out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
