#!/usr/bin/env python3
"""Does the tuned encoder identify buildings, or merely cluster similar facades?

Control: neighbouring buildings whose centres fall in the same 0.0003-degree
grid cell. At 50.8 N that cell is ~33 m north-south by ~21 m east-west, so it is
a spatial proxy for "same street block", not an exact radius.

Two measurements on validation queries whose building has a neighbour:
  A. full gallery (val+test rows) -- top-1 is the same building?
  B. cluster-only gallery -- top-1 is the same building, where candidates are
     the neighbouring buildings' images? Chance is computed, not assumed: for
     each query it is (images of the query building) / (candidate images), the
     probability of landing on it by luck.

Galleries exclude TRAIN rows for both arms: the tuned encoder saw those images
during training, the frozen one did not, so including them would hand the tuned
arm an in-distribution advantage.
"""
from __future__ import annotations
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from train_local_pilot import ROOT, check_splits, load_rows  # noqa: E402

CELL = 0.0003


def cluster_of(rows, ids):
    pts = defaultdict(list)
    for r in rows:
        if f"{r['building_id']}/{r['filename']}" in ids:
            pts[r['building_id']].append((float(r['latitude']), float(r['longitude'])))
    return {bid: (round(np.mean([p[0] for p in v]) / CELL),
                  round(np.mean([p[1] for p in v]) / CELL))
            for bid, v in pts.items()}


def vectors(path: Path, rows):
    with np.load(path, allow_pickle=False) as data:
        keys = data['ids'].tolist()
        pos = {str(k): i for i, k in enumerate(keys)}
        if len(pos) != len(keys):
            raise ValueError(f'duplicate ids in {path}')
        v = np.asarray(data['embeddings'], dtype='float32')[
            [pos[f"{r['building_id']}/{r['filename']}"] for r in rows]]
        toolchain = str(data['toolchain']) if 'toolchain' in data else ''
    if not np.isfinite(v).all():
        raise ValueError(f'nonfinite vectors in {path}')
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-12), toolchain


def evaluate(rows, vec, cell, clusters, gallery_mask):
    idx = np.flatnonzero(gallery_mask)
    gal_ids = np.array([f"{rows[i]['building_id']}/{rows[i]['filename']}" for i in idx])
    gal_bld = np.array([rows[i]['building_id'] for i in idx])
    gal_cell = [cell.get(b) for b in gal_bld]
    queries = [i for i, r in enumerate(rows)
               if r['split'] == 'val' and len(clusters[cell[r['building_id']]]) > 1]
    full_ok = neigh = 0
    cluster_n = cluster_ok = 0
    chance_sum = 0.0
    for start in range(0, len(queries), 128):
        block = queries[start:start + 128]
        sims = vec[block] @ vec[idx].T
        for row, qi in enumerate(block):
            own = f"{rows[qi]['building_id']}/{rows[qi]['filename']}"
            hits = np.flatnonzero(gal_ids == own)
            sims[row, hits] = -np.inf
        best = np.argmax(sims, axis=1)
        for row, qi in enumerate(block):
            house = rows[qi]['building_id']
            top = best[row]
            if gal_bld[top] == house:
                full_ok += 1
            elif gal_cell[top] == cell.get(house):
                neigh += 1
            members = clusters[cell[house]]
            local = np.flatnonzero(np.isin(gal_bld, list(members)))
            local = local[np.isfinite(sims[row, local])]
            if len(local) == 0:
                continue
            cluster_n += 1
            chance_sum += float(np.sum(gal_bld[local] == house)) / len(local)
            if gal_bld[local[int(np.argmax(sims[row, local]))]] == house:
                cluster_ok += 1
    n = len(queries)
    return {'val_queries_with_neighbours': n,
            'gallery_images': int(len(idx)),
            'full_gallery_top1_same_building': full_ok / max(1, n),
            'full_gallery_top1_neighbour_confusion': neigh / max(1, n),
            'cluster_gallery_queries': cluster_n,
            'cluster_gallery_top1_same_building': cluster_ok / max(1, cluster_n),
            'cluster_gallery_chance': chance_sum / max(1, cluster_n),
            'cluster_above_chance_normalised': (
                (cluster_ok / max(1, cluster_n) - chance_sum / max(1, cluster_n)) /
                (1 - chance_sum / max(1, cluster_n)) if cluster_n else None)}


def main() -> None:
    pub = load_rows(ROOT / 'manifest.csv', ROOT.parent / 'monument-inbox', 'pub')
    mmap = load_rows(ROOT / 'mapillary_manifest.csv',
                     ROOT.parent / 'mapillary-inbox', 'map')
    check_splits(pub, mmap)
    with np.load(ROOT / 'embeddings.npz', allow_pickle=False) as d:
        have = set(d['ids'].tolist())
    rows = [r for r in pub if f"{r['building_id']}/{r['filename']}" in have]
    cell = cluster_of(rows, have)
    clusters = defaultdict(set)
    for bid, c in cell.items():
        clusters[c].add(bid)
    held_out = np.array([r['split'] in ('val', 'test') for r in rows])

    out = {'cell_degrees': CELL,
           'cell_extent_metres': '~33 m N-S x ~21 m E-W at 50.8 N',
           'gallery_policy': 'train rows excluded for BOTH arms; tuned saw them, '
                             'frozen did not',
           'note': 'validation queries only; test rows are distractors, never queries',
           'caches': {}}
    for label, name in (('frozen', 'embeddings_frozen_venv.npz'),
                        ('tuned', 'embeddings_tuned_seed42.npz')):
        vec, toolchain = vectors(ROOT / name, rows)
        out['caches'][label] = {
            'file': name, 'toolchain': toolchain,
            'sha256': hashlib.sha256((ROOT / name).read_bytes()).hexdigest()[:16]}
        out[label] = evaluate(rows, vec, cell, clusters, held_out)
    (ROOT / 'report_neighbour_control.json').write_text(json.dumps(out, indent=2) + '\n')
    print(json.dumps(out, indent=2), flush=True)


if __name__ == '__main__':
    main()
