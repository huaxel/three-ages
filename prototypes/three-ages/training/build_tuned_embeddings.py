#!/usr/bin/env python3
"""Encode the publisher corpus with a tuned checkpoint, for the linear probes.

Uses the pilot's own encode path and the frozen cache's ID set, so probe results
are directly comparable to the frozen baselines (same rows, same order rules).
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_local_pilot import MODEL, PRETRAINED, ROOT, encode, healthy, load_rows  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--checkpoint', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--batch-size', type=int, default=64)
    ap.add_argument('--workers', type=int, default=2)
    args = ap.parse_args()
    out = Path(args.out)
    if out.exists():
        raise SystemExit(f'{out} exists; refusing to overwrite')
    healthy()

    state = torch.load(args.checkpoint, map_location='cpu', weights_only=False)
    if state.get('model') != MODEL or state.get('pretrained') != PRETRAINED:
        raise SystemExit('checkpoint backbone mismatch')
    rows = load_rows(ROOT / 'manifest.csv', ROOT.parent / 'monument-inbox', 'pub')
    # Same inclusion set as the frozen cache, so probes compare like with like.
    with np.load(ROOT / 'embeddings.npz', allow_pickle=False) as data:
        have = set(data['ids'].tolist())
    rows = [r for r in rows if f"{r['building_id']}/{r['filename']}" in have]

    import open_clip
    model, _, val_tf = open_clip.create_model_and_transforms(
        MODEL, pretrained=PRETRAINED, device='cuda')
    model.load_state_dict(state['state_dict'])
    model.eval()
    print(f'encoding {len(rows)} publisher images with tuned weights', flush=True)
    vectors = encode(model, rows, val_tf, args.batch_size, args.workers)
    if len(vectors) != len(rows):
        raise SystemExit('row/vector count mismatch')
    healthy()
    temp = out.with_suffix('.tmp.npz')
    np.savez(temp,
             ids=np.array([f"{r['building_id']}/{r['filename']}" for r in rows]),
             embeddings=vectors,
             model=np.array(f'{MODEL}/{PRETRAINED}+tuned:{Path(args.checkpoint).parent.name}'))
    temp.replace(out)
    print(json.dumps({'out': str(out), 'rows': len(rows),
                      'checkpoint': str(args.checkpoint),
                      'steps': state.get('steps')}), flush=True)


if __name__ == '__main__':
    main()
