#!/usr/bin/env python3
"""Look up cross-era matches for a building or a single photograph.

Turns the fine-tuned encoder into something usable: give it a building id or an
image file and it ranks the corpus by cosine similarity, showing capture era and
building for each hit. Matches are *candidates* produced by the model, not
verified identifications — the catalogue is the authority.

Examples:
  three_ages.py --building 37300                 # every picture of that building
  three_ages.py --image path/to/photo.jpg        # an unseen photo, encoded on the fly
  three_ages.py --building 37300 --cross-era     # only hits from another era
  three_ages.py --building 37300 --index frozen  # what the frozen encoder found

Both indexes come from the same venv toolchain, so the comparison is fair.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from epoch_data import load_manifest  # noqa: E402

ROOT = HERE.parents[2] / 'local' / 'training'
# 'tuned' is the checkpoint chosen on validation: hard negatives, two epochs,
# fresh pair sample per epoch. The older checkpoints stay addressable so results
# remain comparable instead of silently drifting.
INDEXES = {
    'tuned': ROOT / 'embeddings_refresh2e.npz',
    'hard1': ROOT / 'embeddings_hard42.npz',
    'random1': ROOT / 'embeddings_tuned_seed42.npz',
    'frozen': ROOT / 'embeddings_frozen_venv.npz',
}
CHECKPOINT = ROOT / 'pilot-refresh2e-20261023-173100' / 'checkpoint.pt'


def load_index(kind: str):
    path = INDEXES[kind]
    if not path.is_file():
        raise SystemExit(f'missing index {path}')
    with np.load(path, allow_pickle=False) as data:
        ids = data['ids'].tolist()
        vec = np.asarray(data['embeddings'], dtype='float32')
        meta_tag = str(data['model']) if 'model' in data else kind
    vec = vec / (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-12)
    meta = {}
    for row in load_manifest(ROOT / 'manifest.csv'):
        meta[f"{row['building_id']}/{row['filename']}"] = row
    keep = [i for i, key in enumerate(ids) if key in meta]
    return ([ids[i] for i in keep], vec[keep],
            [meta[ids[i]] for i in keep], meta_tag)


def encode_file(path: Path) -> np.ndarray:
    import torch
    import open_clip
    from PIL import Image
    model, _, transform = open_clip.create_model_and_transforms(
        'ViT-B-32', pretrained='laion2b_s34b_b79k', device='cpu')
    state = torch.load(CHECKPOINT, map_location='cpu', weights_only=False)
    model.load_state_dict(state['state_dict'])
    model.eval()
    with torch.no_grad():
        v = model.encode_image(transform(Image.open(path).convert('RGB')).unsqueeze(0),
                               normalize=True)
    return v[0].numpy().astype('float32')


def query(vecs, queries, qrows, ids, matrix, rows, k, cross_era_only, min_score):
    if not (len(vecs) == len(queries) == len(qrows)):
        raise SystemExit('query metadata is misaligned')
    hits = []
    for qvec, qname, qrow in zip(vecs, queries, qrows):
        external = qrow.get('building_id') == '<external>'
        sims = matrix @ qvec
        for i, key in enumerate(ids):
            if key == qname:
                sims[i] = -np.inf
        if cross_era_only and qrow.get('capture_era'):
            era = qrow['capture_era']
            mask = [i for i, r in enumerate(rows)
                    if r['capture_era'] and r['capture_era'] != era]
            if not mask:
                continue
            order = np.array(mask)[np.argsort(-sims[mask])][:k]
        else:
            order = np.argsort(-sims)[:k]
        for i in order:
            score = float(sims[i])
            if score < min_score:
                break
            same = None if external else (
                rows[i]['building_id'] == qrow['building_id'])
            hits.append({'query': qname, 'query_building': qrow['building_id'],
                         'query_era': qrow['capture_era'],
                         'match': ids[i], 'match_building': rows[i]['building_id'],
                         'match_era': rows[i]['capture_era'],
                         'same_building': same, 'score': round(score, 4)})
    return hits


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--building', help='building id from the corpus')
    src.add_argument('--image', help='image file to encode on the fly')
    ap.add_argument('--index', choices=sorted(INDEXES), default='tuned')
    ap.add_argument('--topk', type=int, default=5)
    ap.add_argument('--cross-era', action='store_true',
                    help='only show hits from a different capture era')
    ap.add_argument('--min-score', type=float, default=0.0)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    if args.topk < 1:
        raise SystemExit('--topk must be >= 1')

    ids, matrix, rows, tag = load_index(args.index)
    if args.image:
        path = Path(args.image)
        if not path.is_file():
            raise SystemExit(f'no such image: {path}')
        # If the file lives inside a corpus building folder, reuse its real
        # metadata: that gives correct self-exclusion and era information.
        guess = f'{path.parent.name}/{path.name}'
        if guess in ids:
            i = ids.index(guess)
            queries, qrows = [guess], [rows[i]]
        else:
            queries = [f'<{path.name}>']
            qrows = [{'building_id': '<external>', 'capture_era': '',
                      'filename': path.name}]
        vecs = [encode_file(path)]
    else:
        picks = [i for i, key in enumerate(ids) if key.split('/')[0] == args.building]
        if not picks:
            raise SystemExit(f'building {args.building} has no indexed pictures')
        vecs = [matrix[i] for i in picks]
        queries = [ids[i] for i in picks]
        qrows = [rows[i] for i in picks]

    hits = query(vecs, queries, qrows, ids, matrix, rows, args.topk,
                 args.cross_era, args.min_score)
    if args.json:
        print(json.dumps({'index': args.index, 'model': tag, 'hits': hits}, indent=2))
        return
    print(f'index: {args.index} ({tag})   queries: {len(queries)}   '
          f'gallery: {len(ids)}')
    print('matches are model candidates, not verified identifications\n')
    cur = None
    for h in hits:
        if h['query'] != cur:
            cur = h['query']
            era = h['query_era'] or 'undated'
            print(f'{cur}  [{era}]')
        flag = ('external query' if h['same_building'] is None
                else 'same building' if h['same_building'] else 'OTHER building')
        print(f"   {h['score']:.3f}  {h['match']:<42} "
              f"{h['match_era'] or 'undated':<10} {flag}")
    if not hits:
        print('no matches above the score threshold')


if __name__ == '__main__':
    main()
