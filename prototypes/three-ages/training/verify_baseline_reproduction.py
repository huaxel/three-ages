#!/usr/bin/env python3
"""Pipeline-equivalence check for the pilot comparison.

Re-encodes the validation queries and full gallery with the SAME untrained
weights through the agent's own encode/evaluate path. If held-out metrics match
the frozen cache baseline, the frozen-vs-tuned delta is attributable to weight
updates rather than to pipeline differences.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_local_pilot import (  # noqa: E402
    DATA, MODEL, PRETRAINED, REPO, check_splits, encode, evaluate, healthy,
    load_rows)

def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', required=True,
                    help='directory for report.json; must not already exist')
    ap.add_argument('--batch-size', type=int, default=64)
    ap.add_argument('--workers', type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    healthy()
    pub = load_rows(DATA / 'manifest.csv', REPO / 'local' / 'monument-inbox', 'pub')
    mmap = load_rows(DATA / 'mapillary_manifest.csv',
                     REPO / 'local' / 'mapillary-inbox', 'map')
    check_splits(pub, mmap)
    import numpy as np
    keep = []
    for source, cache in ((pub, 'embeddings.npz'), (mmap, 'mapillary_embeddings.npz')):
        with np.load(DATA / cache, allow_pickle=False) as data:
            have = set(data['ids'].tolist())
        keep.append([r for r in source
                     if f"{r['building_id']}/{r['filename']}" in have])
    pub, mmap = keep
    mapval = [r for r in mmap if r['split'] == 'val']

    import open_clip
    model, _, val_tf = open_clip.create_model_and_transforms(
        MODEL, pretrained=PRETRAINED, device='cuda')
    model.eval()
    print('encoding full gallery with untrained weights', flush=True)
    pvec = encode(model, pub, val_tf, args.batch_size, args.workers)
    mvec = encode(model, mapval, val_tf, args.batch_size, args.workers)
    result = evaluate(pub, pvec, mapval, mvec)
    healthy()
    report = {'check': 'untrained weights through pilot encode path',
              'state': 'complete', 'metrics': result}
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)

if __name__ == '__main__':
    main()
