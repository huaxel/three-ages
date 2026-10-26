"""Standard-library canonical training-pair sampler, shared with identity audits."""
from __future__ import annotations
import random
from collections import defaultdict


def photo(r):
    return str(r['drawing_flag']).lower() in ('0', 'false', '')


def cross_sample(left, right, cap, rng):
    # Uniformly sample a Cartesian product without materializing it.
    n = len(left) * len(right)
    return [(left[i // len(right)], right[i % len(right)])
            for i in rng.sample(range(n), min(cap, n))]


def mine_pairs(pub, mmap, seed=0, cap=20):
    rng = random.Random(seed)
    pb, mb = defaultdict(list), defaultdict(list)
    for source, groups in ((pub, pb), (mmap, mb)):
        for r in source:
            if r['split'] == 'train' and photo(r):
                groups[r['building_id']].append(r)
    pairs = []
    counts = {'cross_era': 0, 'cross_pole': 0}
    for bid in sorted(pb):
        era = defaultdict(list)
        for r in pb[bid]:
            if r['capture_era']:
                era[r['capture_era']].append(r)
        keys = sorted(era)
        # Flatten era-pair products into integer intervals; sample without
        # allocating O(number-of-images squared) intermediate pair lists.
        groups = [(era[a], era[b]) for i, a in enumerate(keys) for b in keys[i+1:]]
        total = sum(len(a)*len(b) for a, b in groups)
        chosen = rng.sample(range(total), min(cap, total))
        for index in chosen:
            for a, b in groups:
                n = len(a)*len(b)
                if index < n:
                    pairs.append((a[index//len(b)], b[index%len(b)]))
                    counts['cross_era'] += 1
                    break
                index -= n
        if bid in mb:
            sampled = cross_sample(pb[bid], mb[bid], cap, rng)
            pairs.extend(sampled)
            counts['cross_pole'] += len(sampled)
    rng.shuffle(pairs)
    if not pairs:
        raise ValueError('No eligible training pairs')
    return pairs, counts


