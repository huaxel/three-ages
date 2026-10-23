#!/usr/bin/env python3
"""Out-of-source check on the curated Grand-Place slice.

The pilot was trained and scored on monument.heritage.brussels + Mapillary.
This slice comes from KIK-IRPA / IDPS / Commons previews already in the repo --
different photographers, different scanning, different decades (1878-2024). It
asks the narrow question: does the fine-tuned encoder still match the same
facade unit across eras when the pictures come from somewhere it has never seen?

n = 72 images / 27 units is small, so this is a sanity check on generalisation,
not a headline. Chance is computed exactly (hypergeometric), not assumed.
"""
from __future__ import annotations
import csv
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_local_pilot import MODEL, PRETRAINED, ROOT  # noqa: E402
from stats import wilson  # noqa: E402

PROTO = HERE.parent
CHECKPOINT = ROOT / 'pilot-20261022-232106' / 'checkpoint.pt'


def load_slice():
    rows = list(csv.DictReader(
        (PROTO / 'data' / 'three-ages-image-review.csv').open(encoding='utf-8')))
    out = []
    for r in rows:
        path = PROTO / r['preview']
        if not path.is_file():
            raise SystemExit(f'missing preview: {path}')
        out.append({'unit': r['facade_unit_id'], 'epoch': int(r['epoch']), 'path': path})
    if len({(x['unit'], x['path']) for x in out}) != len(out):
        raise SystemExit('duplicate rows in curated slice')
    return out


@torch.no_grad()
def encode(model, rows, transform, device='cuda'):
    batch = torch.stack([transform(Image.open(r['path']).convert('RGB')) for r in rows])
    v = model.encode_image(batch.to(device), normalize=True)
    if not torch.isfinite(v).all():
        raise SystemExit('nonfinite embeddings')
    return v.cpu().numpy().astype('float32')


def chance_topk(mates: int, gallery: int, k: int) -> float:
    if gallery <= 0 or mates <= 0:
        return 0.0
    miss = 1.0
    for i in range(k):
        if gallery - i - mates <= 0:
            return 1.0
        miss *= (gallery - i - mates) / (gallery - i)
    return 1.0 - miss


def evaluate(rows, vec, k=5):
    unit = np.array([r['unit'] for r in rows])
    epoch = np.array([r['epoch'] for r in rows])
    sims = vec @ vec.T
    np.fill_diagonal(sims, -np.inf)
    order = np.argsort(-sims, axis=1)[:, :k]
    n = len(rows)
    same = cross = 0
    chance = 0.0
    chance_cross = 0.0
    for i in range(n):
        mates = (unit == unit[i])
        mates[i] = False
        other_era = mates & (epoch != epoch[i])
        hit = mates[order[i]].any()
        same += bool(hit)
        cross += bool(other_era[order[i]].any())
        chance += chance_topk(int(mates.sum()), n - 1, k)
        chance_cross += chance_topk(int(other_era.sum()), n - 1, k)
    return {'queries': n,
            f'top{k}_same_unit': same / n,
            f'top{k}_same_unit_ci95': [round(x, 4) for x in wilson(same, n)],
            f'top{k}_same_unit_chance': round(chance / n, 4),
            f'top{k}_cross_era_same_unit': cross / n,
            f'top{k}_cross_era_ci95': [round(x, 4) for x in wilson(cross, n)],
            f'top{k}_cross_era_chance': round(chance_cross / n, 4)}


def main() -> None:
    rows = load_slice()
    import open_clip
    model, _, transform = open_clip.create_model_and_transforms(
        MODEL, pretrained=PRETRAINED, device='cuda')
    model.eval()
    frozen = encode(model, rows, transform)
    state = torch.load(CHECKPOINT, map_location='cpu', weights_only=False)
    if state.get('model') != MODEL or state.get('pretrained') != PRETRAINED:
        raise SystemExit('checkpoint backbone mismatch')
    model.load_state_dict(state['state_dict'])
    model.eval()
    tuned = encode(model, rows, transform)
    report = {
        'slice': 'curated Grand-Place previews (KIK-IRPA / IDPS / Commons)',
        'note': 'out-of-source sanity check; 72 images / 27 units; not a headline',
        'images': len(rows), 'units': len({r['unit'] for r in rows}),
        'units_with_multiple_eras': len(
            {r['unit'] for r in rows if len({s['epoch'] for s in rows
                                             if s['unit'] == r['unit']}) > 1}),
        'epoch_range': [min(r['epoch'] for r in rows), max(r['epoch'] for r in rows)],
        'checkpoint': str(CHECKPOINT.relative_to(ROOT)),
        'frozen': evaluate(rows, frozen),
        'tuned': evaluate(rows, tuned)}
    (ROOT / 'report_curated_slice.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
