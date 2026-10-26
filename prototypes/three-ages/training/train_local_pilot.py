#!/usr/bin/env python3
"""One-epoch local FP32 contrastive pilot; validation-only, full gallery.

No test-query metrics or architecture/model search. Both cached baselines and
updated features use the same exact gallery and validation denominator.
"""
from __future__ import annotations
import argparse
import csv
import json
import hashlib
import math
import os
from pathlib import Path
import sys
import random
import time
from collections import defaultdict

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

CODE = Path(__file__).resolve().parent          # prototypes/three-ages/training
PROTO = CODE.parent                              # prototypes/three-ages (epoch_data)
REPO = CODE.parents[2]                           # repository root
DATA = REPO / 'local' / 'training'               # manifests, caches, runs (all ignored)
ROOT = DATA                                      # keep the existing name working
sys.path.insert(0, str(PROTO))
MODEL = 'ViT-B-32'
PRETRAINED = 'laion2b_s34b_b79k'

from data_integrity import assert_image_isolation  # noqa: E402
from pair_sampling import photo, cross_sample, mine_pairs  # noqa: E402


def healthy():
    if int(Path('/proc/sys/kernel/tainted').read_text()) & 128:
        raise RuntimeError('Kernel oops: stop GPU execution until reboot')


def load_rows(manifest, image_root, pole):
    with Path(manifest).open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r['_id'] = f"{pole}/{r['building_id']}/{r['filename']}"
        r['_path'] = Path(image_root) / r['building_id'] / r['filename']
        if not r['_path'].is_file():
            raise ValueError(f"Missing image: {r['_path']}")
    if len({r['_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate image IDs')
    return rows


def check_splits(pub, mmap):
    known = {}
    for r in pub + mmap:
        if r['split'] not in ('train', 'val', 'test'):
            raise ValueError(f"Unknown split: {r['split']!r}")
        bid = r['building_id']
        if bid in known and known[bid] != r['split']:
            raise ValueError(f'Split leakage for building {bid}')
        known[bid] = r['split']
    assert_image_isolation(pub, mmap)


def building_loss(a, b, bids, scale):
    logits = scale * (F.normalize(a, dim=-1) @ F.normalize(b, dim=-1).T)
    positive = bids[:, None] == bids[None, :]
    # Sum probability of ALL same-building positives, rather than repel
    # other views of the same building as diagonal-only InfoNCE would do.
    def one_way(x, mask):
        return (torch.logsumexp(x, dim=1) -
                torch.logsumexp(x.masked_fill(~mask, -torch.inf), dim=1)).mean()
    return (one_way(logits, positive) + one_way(logits.T, positive.T)) / 2


def neighbour_order(pairs, seed, cell=0.0003):
    """Order pairs so batches contain spatially neighbouring buildings.

    Random shuffling makes in-batch negatives easy (a townhouse versus a
    warehouse), which is the most likely reason one epoch saturates: the loss can
    fall without the encoder learning to separate things that look alike. This
    order groups pairs by the anchor building's ~33 m N x 21 m grid cell, so a
    batch's negatives are usually the houses next door.
    """
    rng = random.Random(seed)
    pts = defaultdict(list)
    for a, _ in pairs:
        if a.get('latitude') and a.get('longitude'):
            pts[a['building_id']].append((float(a['latitude']), float(a['longitude'])))
    cell_of = {b: (round(np.mean([p[0] for p in v]) / cell),
                   round(np.mean([p[1] for p in v]) / cell))
               for b, v in pts.items()}
    groups = defaultdict(list)
    for i, (a, _) in enumerate(pairs):
        groups[cell_of.get(a['building_id'], ('', i))].append(i)
    order = []
    keys = sorted(groups, key=lambda k: (str(k), len(groups[k])))
    rng.shuffle(keys)
    for key in keys:
        block = groups[key]
        rng.shuffle(block)
        order.extend(block)
    return order


def hard_negative_batches(pairs, embeddings_path, seed, batch_size, k=8, per_building=4):
    """Batches of distinct buildings that look alike -- real hard negatives.

    Grouping by location alone failed measurably: a cell's pairs mostly belong to
    the same few buildings, and same-building items are positives under the
    building-aware loss, so batches got easier (loss 0.45 vs ~2.1 for random
    order). Here each batch is one anchor building plus its k most visually
    similar *other* buildings, chosen from frozen embeddings, so every negative is
    a plausible confusion rather than a random warehouse.
    """
    rng = random.Random(seed)
    with np.load(embeddings_path, allow_pickle=False) as data:
        ids = data['ids'].tolist()
        vec = np.asarray(data['embeddings'], dtype='float32')
    vec = vec / (np.linalg.norm(vec, axis=1, keepdims=True) + 1e-12)
    owner = np.array([key.split('/', 1)[0] for key in ids])
    order = np.argsort(owner)
    owner_sorted = owner[order]
    uniq, starts = np.unique(owner_sorted, return_index=True)
    centroids = np.add.reduceat(vec[order], starts, axis=0)
    centroids /= (np.linalg.norm(centroids, axis=1, keepdims=True) + 1e-12)
    index_of = {b: i for i, b in enumerate(uniq)}

    by_building = defaultdict(list)
    for i, (a, _) in enumerate(pairs):
        by_building[a['building_id']].append(i)
    usable = [b for b in by_building if b in index_of]
    if not usable:
        raise RuntimeError('no buildings overlap the embedding cache')
    centres = centroids[[index_of[b] for b in usable]]

    neighbours = {}
    for start in range(0, len(usable), 512):
        block = centres[start:start + 512] @ centres.T
        for row in range(block.shape[0]):
            sims = block[row].copy()
            sims[start + row] = -np.inf
            top = np.argpartition(-sims, min(k, len(usable) - 1))[:k]
            neighbours[usable[start + row]] = [usable[j] for j in top]

    unused = set(range(len(pairs)))
    shuffled = list(range(len(pairs)))
    rng.shuffle(shuffled)
    batches = []
    while unused:
        anchor = rng.choice(usable)
        chosen = [i for i in by_building[anchor] if i in unused][:per_building]
        for other in neighbours[anchor]:
            chosen.extend([i for i in by_building[other] if i in unused][:2])
            if len(chosen) >= batch_size:
                break
        chosen = list(dict.fromkeys(chosen))[:batch_size]
        if len(chosen) < batch_size:
            chosen.extend([i for i in shuffled if i in unused and i not in chosen]
                          [:batch_size - len(chosen)])
        if len(chosen) < 2:
            break  # remaining pairs belong to buildings outside the cache
        unused.difference_update(chosen)
        batches.append(chosen)
    return batches


class Pairs(torch.utils.data.Dataset):
    def __init__(self, pairs, transform):
        self.pairs, self.transform = pairs, transform
        self.bids = {bid: i for i, bid in enumerate(sorted({a['building_id'] for a, _ in pairs}))}

    def __len__(self): return len(self.pairs)

    def __getitem__(self, index):
        a, b = self.pairs[index]
        images = []
        for r in (a, b):
            with Image.open(r['_path']) as im:
                images.append(self.transform(im.convert('RGB')))
        return *images, self.bids[a['building_id']]


class Images(torch.utils.data.Dataset):
    def __init__(self, rows, transform): self.rows, self.transform = rows, transform
    def __len__(self): return len(self.rows)
    def __getitem__(self, i):
        with Image.open(self.rows[i]['_path']) as im:
            return self.transform(im.convert('RGB'))


def worker_seed(_):
    seed = torch.initial_seed() % (2**32)
    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(1)


@torch.no_grad()
def encode(model, rows, transform, batch, workers):
    loader = torch.utils.data.DataLoader(Images(rows, transform), batch_size=batch,
        num_workers=workers, worker_init_fn=worker_seed, shuffle=False,
        **({'multiprocessing_context': 'spawn'} if workers else {}))
    result = []
    model.eval()
    for i, x in enumerate(loader):
        f = model.encode_image(x.to('cuda'), normalize=True)
        if not torch.isfinite(f).all().item(): raise RuntimeError('Nonfinite embedding')
        result.append(f.cpu().numpy())
        if i % 100 == 0:
            healthy()
            print(f'encode {min((i+1)*batch,len(rows))}/{len(rows)}', flush=True)
    return np.concatenate(result).astype('float32')


def cached_vectors(path, rows):
    with np.load(path, allow_pickle=False) as data:
        if str(data['model']) != f'{MODEL}/{PRETRAINED}':
            raise ValueError('Frozen cache model differs from pilot backbone')
        ids = data['ids'].tolist()
        pos = {str(key): i for i, key in enumerate(ids)}
        if len(pos) != len(ids): raise ValueError('Duplicate cache IDs')
        v = np.asarray(data['embeddings'], dtype='float32')
        aligned = v[[pos[f"{r['building_id']}/{r['filename']}"] for r in rows]]
    if not np.isfinite(aligned).all(): raise ValueError('Nonfinite cache')
    norms = np.linalg.norm(aligned, axis=1, keepdims=True)
    if np.any(norms == 0): raise ValueError('Zero cache vector')
    return aligned / norms


def metrics(qrows, qvec, grows, gvec, *, return_outcomes=False):
    if not qrows or len(grows) < 6: raise ValueError('Insufficient evaluation data')
    assert len(qrows) == len(qvec) and len(grows) == len(gvec)
    gb = np.array([r['building_id'] for r in grows])
    ge = np.array([r['capture_era'] for r in grows])
    identities = np.array([r.get('_image_identity', r['_id']) for r in grows])
    mates = defaultdict(list)
    for i, r in enumerate(grows):
        mates[r['building_id']].append(i)
    top5 = cross5 = eligible = n = 0
    outcomes = []
    for start in range(0, len(qrows), 128):
        qr = qrows[start:start+128]
        sims = qvec[start:start+128] @ gvec.T
        for i, r in enumerate(qr):
            identity = r.get('_image_identity', r['_id'])
            sims[i, identities == identity] = -np.inf
        order = np.argpartition(-sims, 4, axis=1)[:, :5]
        for i, r in enumerate(qr):
            identity = r.get('_image_identity', r['_id'])
            available = [j for j in mates[r['building_id']] if identities[j] != identity]
            if not available: continue
            n += 1
            same = (gb[order[i]] == r['building_id']) & np.isfinite(sims[i, order[i]])
            hit = bool(same.any())
            top5 += hit
            cross_hit = None
            valid = bool(r['capture_era']) and any(
                ge[j] and ge[j] != r['capture_era'] for j in available)
            if valid:
                eligible += 1
                cross_hit = bool((same & (ge[order[i]] != '') &
                                  (ge[order[i]] != r['capture_era'])).any())
                cross5 += cross_hit
            outcomes.append({'id': r['_id'], 'building_id': r['building_id'],
                             'group': r.get('_evaluation_group', r['building_id']),
                             'top5': int(hit),
                             'cross_era_top5_fair': int(cross_hit) if valid else None})
    result = {'queries_with_mates': n, 'top5': top5/max(1,n),
              'cross_era_eligible_queries': eligible,
              'cross_era_top5_fair': cross5/max(1,eligible),
              'query_buildings': len({r['building_id'] for r in outcomes}),
              'independent_groups': len({r['group'] for r in outcomes})}
    if return_outcomes:
        result['outcomes'] = outcomes
    return result


def atomic_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2)+'\n')
    temp.replace(path)


def evaluate(pub, pvec, mmap, mvec):
    # Same full publisher gallery for both frozen and tuned features.
    qidx = [i for i, r in enumerate(pub) if r['split'] == 'val']
    return {'publisher': metrics([pub[i] for i in qidx], pvec[qidx], pub, pvec),
            'cross_pole': metrics(mmap, mvec, pub, pvec)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--batch-size', type=int, default=16)
    ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--max-steps', type=int, default=0, help='smoke only; 0=one full epoch')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--epochs', type=int, default=1)
    ap.add_argument('--refresh-pairs', action='store_true',
                    help='re-mine a different pair sample each epoch instead of '
                         'repeating the same fixed pairs')
    ap.add_argument('--negatives', choices=('random', 'hard'), default='random',
                    help='hard draws batchmates from the visually nearest other '
                         'buildings (frozen embeddings) so negatives are confusable')
    ap.add_argument('--resume', default='',
                    help='checkpoint to continue training from (same optimiser state)')
    ap.add_argument('--publisher-manifest', default=str(DATA/'manifest.csv'))
    ap.add_argument('--mapillary-manifest', default=str(DATA/'mapillary_manifest.csv'))
    args = ap.parse_args()
    if args.batch_size < 2 or args.workers < 0: raise ValueError('Invalid batch/workers')
    run = Path(args.run_dir)
    if run.exists():
        raise ValueError(f'Run directory exists: {run}')
    healthy()
    random.seed(args.seed); np.random.seed(args.seed); torch.manual_seed(args.seed)
    torch.set_num_threads(4)
    pub = load_rows(args.publisher_manifest, REPO/'local'/'monument-inbox', 'pub')
    mmap = load_rows(args.mapillary_manifest, REPO/'local'/'mapillary-inbox', 'map')
    check_splits(pub, mmap)
    manifest_hashes = {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                       for name, path in [('publisher', args.publisher_manifest),
                                          ('mapillary', args.mapillary_manifest)]}
    resume_state = None
    if args.resume:
        resume_state = torch.load(args.resume, map_location='cpu', weights_only=False)
        if resume_state.get('verified_manifest_sha256') != manifest_hashes:
            raise ValueError('Resume checkpoint lacks matching image-isolated manifest provenance; '
                             'start a fresh run, do not resume contaminated weights')
    run.mkdir(parents=True, exist_ok=False)
    (run/'train_local_pilot.snapshot.py').write_text(Path(__file__).read_text())
    # One historical publisher frame has no frozen embedding. Explicitly
    # exclude cache gaps from BOTH train/eval so comparisons use identical IDs.
    excluded = []
    aligned = []
    for source, cache in ((pub, 'embeddings.npz'), (mmap, 'mapillary_embeddings.npz')):
        with np.load(ROOT/cache, allow_pickle=False) as data:
            have = set(data['ids'].tolist())
        excluded.extend(r['_id'] for r in source
                        if f"{r['building_id']}/{r['filename']}" not in have)
        aligned.append([r for r in source
                        if f"{r['building_id']}/{r['filename']}" in have])
    if not set(excluded) <= {'pub/17387/11500227_0192_P04.jpg'}:
        raise ValueError(f'Unexpected frozen-cache exclusions: {excluded}')
    pub, mmap = aligned
    pairs, kinds = mine_pairs(pub, mmap, args.seed)
    mapval = [r for r in mmap if r['split'] == 'val']
    report = {'state': 'baseline', 'config': vars(args), 'model': MODEL,
              'pretrained': PRETRAINED, 'kernel': os.uname().release,
              'torch': torch.__version__, 'pairs': len(pairs), 'pair_kinds': kinds,
              'query_split': 'val', 'gallery': len(pub), 'excluded_cache_ids': excluded,
              'verified_manifest_sha256': manifest_hashes,
              'sha256': {name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                         for name, path in [('code', Path(__file__)),
                                            ('publisher_manifest', args.publisher_manifest),
                                            ('mapillary_manifest', args.mapillary_manifest),
                                            ('pair_sampling', CODE/'pair_sampling.py'),
                                            ('data_integrity', CODE/'data_integrity.py')]},
              'note': 'Full gallery incl. all splits; only validation queries scored'}
    pbase = cached_vectors(ROOT/'embeddings.npz', pub)
    mbase = cached_vectors(ROOT/'mapillary_embeddings.npz', mapval)
    report['frozen_validation'] = evaluate(pub, pbase, mapval, mbase)
    atomic_json(run/'report.json', report)
    print(json.dumps(report), flush=True)
    import open_clip
    model, train_tf, val_tf = open_clip.create_model_and_transforms(
        MODEL, pretrained=PRETRAINED, device='cpu')
    model.to('cuda'); model.visual.train()
    opt = torch.optim.AdamW(list(model.visual.parameters())+[model.logit_scale],
                            lr=3e-6, weight_decay=0.01)
    with torch.no_grad(): model.logit_scale.fill_(math.log(1/0.07))
    resumed_from = ''
    if args.resume:
        state = resume_state
        if state.get('model') != MODEL or state.get('pretrained') != PRETRAINED:
            raise SystemExit('resume checkpoint backbone mismatch')
        model.load_state_dict(state['state_dict'])
        if 'optimizer' in state:
            opt.load_state_dict(state['optimizer'])
        resumed_from = str(args.resume)
        report['resumed_from'] = resumed_from
        report['resumed_steps'] = state.get('steps')
        print(f"resumed from {args.resume} at {state.get('steps')} steps", flush=True)
    common = dict(num_workers=args.workers, worker_init_fn=worker_seed,
                  **({'multiprocessing_context': 'spawn'} if args.workers else {}))

    def build_loader(seed):
        """Re-mine and re-batch for one epoch; identical seeding keeps default."""
        epoch_pairs, epoch_kinds = (mine_pairs(pub, mmap, seed) if args.refresh_pairs
                                    else (pairs, kinds))
        sampler = None
        if args.negatives == 'hard':
            sampler = hard_negative_batches(
                epoch_pairs, ROOT / 'embeddings_frozen_venv.npz', seed, args.batch_size)
        gen = torch.Generator().manual_seed(seed)
        dataset = Pairs(epoch_pairs, train_tf)
        if sampler is None:
            return torch.utils.data.DataLoader(
                dataset, batch_size=args.batch_size, shuffle=True,
                drop_last=False, generator=gen, **common), len(epoch_pairs), epoch_kinds
        return torch.utils.data.DataLoader(
            dataset, batch_sampler=sampler, **common), len(epoch_pairs), epoch_kinds

    if args.negatives == 'hard':
        report['negatives'] = 'hard'
    report['state'] = 'training'; atomic_json(run/'report.json', report)
    start = time.monotonic(); total = 0.; n = 0; seen = 0
    epoch_losses = []
    for epoch in range(args.epochs):
        epoch_seed = args.seed + epoch if args.refresh_pairs else args.seed
        loader, n_pairs, epoch_kinds = build_loader(epoch_seed)
        report.setdefault('per_epoch', []).append(
            {'epoch': epoch + 1, 'pairs': n_pairs, 'kinds': epoch_kinds})
        print(f'epoch {epoch+1}/{args.epochs}: {n_pairs} pairs, '
              f'{len(loader)} batches', flush=True)
        epoch_total = 0.; epoch_seen = 0
        for step, (a, b, bids) in enumerate(loader, 1):
            healthy()
            if len(a) < 2: continue
            opt.zero_grad(set_to_none=True)
            fa = model.encode_image(a.to('cuda'))
            fb = model.encode_image(b.to('cuda'))
            loss = building_loss(fa, fb, bids.to('cuda'), model.logit_scale.exp())
            if not torch.isfinite(loss).item(): raise RuntimeError('Nonfinite training loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.visual.parameters(), 10., error_if_nonfinite=True)
            if not torch.isfinite(model.logit_scale.grad).item(): raise RuntimeError('Bad scale gradient')
            opt.step()
            with torch.no_grad(): model.logit_scale.clamp_(0, math.log(100))
            total += loss.item()*len(a); seen += len(a); n += 1
            epoch_total += loss.item()*len(a); epoch_seen += len(a)
            if step == 1 or step % 50 == 0:
                elapsed=time.monotonic()-start
                progress={'epoch':epoch+1,'step':step,'total_steps':len(loader),
                          'pairs_seen':seen,'mean_loss':total/seen,'last_loss':loss.item(),
                          'pairs_per_second':seen/elapsed,'elapsed_seconds':elapsed,
                          'peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30}
                print(json.dumps(progress), flush=True)
                atomic_json(run/'progress.json',progress)
            if args.max_steps and n >= args.max_steps: break
        if epoch_seen:
            epoch_losses.append(epoch_total/epoch_seen)
            print(f'epoch {epoch+1} done: mean loss {epoch_losses[-1]:.4f}', flush=True)
        if args.max_steps and n >= args.max_steps: break
    if n == 0: raise RuntimeError('No optimizer steps completed')
    torch.cuda.synchronize()
    healthy()
    report['training']={'steps':n,'pairs_seen':seen,'mean_loss':total/max(1,seen),
                        'seconds':time.monotonic()-start,
                        'peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30}
    # Checkpoint BEFORE the long full-gallery embedding pass. Copy tensors to
    # CPU for portable loading; optimizer state included for later recovery.
    if not all(torch.isfinite(p).all().item() for p in model.visual.parameters()):
        raise RuntimeError('Nonfinite trained parameters')
    temp=run/'checkpoint.tmp'
    torch.save({'state_dict':{k:v.detach().cpu() for k,v in model.state_dict().items()},
                'optimizer':opt.state_dict(),'model':MODEL,'pretrained':PRETRAINED,
                'seed':args.seed,'steps':n,'epoch_complete':not bool(args.max_steps),
                'config':vars(args), 'verified_manifest_sha256': manifest_hashes},temp)
    temp.replace(run/'checkpoint.pt')
    report['state']='checkpoint_saved'; atomic_json(run/'report.json',report)
    if args.max_steps:
        report['state']='smoke_complete'; atomic_json(run/'report.json',report)
        print('SMOKE COMPLETE; evaluation deliberately skipped',flush=True)
        return
    print('CHECKPOINT SAVED; validation encoding starts',flush=True)
    pvec=encode(model,pub,val_tf,64,args.workers)
    mvec=encode(model,mapval,val_tf,64,args.workers)
    np.savez(run/'validation_features.npz',publisher_ids=np.array([r['_id'] for r in pub]),
             publisher=pvec,mapillary_ids=np.array([r['_id'] for r in mapval]),mapillary=mvec)
    report['tuned_validation']=evaluate(pub,pvec,mapval,mvec)
    report['state']='complete'; healthy(); atomic_json(run/'report.json',report)
    print(json.dumps(report),flush=True)


if __name__ == '__main__':
    main()
