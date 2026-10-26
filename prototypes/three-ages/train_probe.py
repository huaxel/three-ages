#!/usr/bin/env python3
"""Linear probes over frozen embeddings: the first trainable ML in the project.

Heads (single-image, linear on frozen CLIP, CPU):
  drawing      -- binary photo-vs-drawing triage (the gate for everything else)
  capture_era  -- 6-era photo dating (task A; doubles as the B backbone later)
  style        -- multi-label style-family classification (weak source labels)

Construction-era training needs --reviewed-labels source truth AND
--image-reviews with current, explicit per-image applicability. Building-wide
labels or depicts flags cannot stand in for an image review. Contributor years,
style windows, missing/unknown image decisions and stale feature bytes never
silently become training truth.

Eval reports top-1, within-one-era (ordered heads), dummy baselines, and --
the disentanglement check -- per-capture-era confusion slices, so a model
that detects film stock instead of architecture fails visibly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from epoch_data import (  # noqa: E402
    CAPTURE_ERAS, CONSTRUCTION_ERAS, FAMILY_NAMES, load_manifest,
    load_reviewed_labels, with_reviewed_labels)

sys.path.insert(0, str(ROOT / "training"))
from stats import building_macro_mean, classification_by_class  # noqa: E402
from data_integrity import assert_image_isolation  # noqa: E402
from development_cv import grouped_development_cv  # noqa: E402
from construction_image_reviews import eligible_image_keys  # noqa: E402

HEADS = ("drawing", "capture_era", "style", "construction_era")
TARGET_SEMANTICS = {
    'drawing': 'caption-keyword photo/drawing proxy; not independently reviewed image truth',
    'capture_era': 'caption-derived capture-era proxy; not independently verified capture dates',
    'style': 'weak catalogue style metadata; not reviewed ground truth',
    'construction_era': 'human-reviewed construction campaign; image applicability must be reviewed separately',
}


def targets(rows: list[dict], head: str, reviewed: dict[str, str] | None = None):
    if head == "drawing":
        return np.array([r["drawing_flag"] for r in rows], dtype=int), ["photo", "drawing"]
    if head == "capture_era":
        return np.array([CAPTURE_ERAS.index(r["capture_era"]) for r in rows]), CAPTURE_ERAS
    if head == "construction_era":
        if not reviewed:
            raise SystemExit(
                "construction_era needs --reviewed-labels: contributor years and style "
                "windows are proxies, not training truth (see epoch_data docstring).")
        return (np.array([CONSTRUCTION_ERAS.index(reviewed[r["building_id"]])
                         for r in rows]), CONSTRUCTION_ERAS)
    if head == "style":
        matrix = np.zeros((len(rows), len(FAMILY_NAMES)), dtype=int)
        for pos, row in enumerate(rows):
            for family in row["families"]:
                if family in FAMILY_NAMES:
                    matrix[pos, FAMILY_NAMES.index(family)] = 1
        return matrix, FAMILY_NAMES
    raise AssertionError(f"unreachable: {head}")


def within_one_era(true: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(np.abs(true - pred) <= 1))


def validate_cache_training(cache, manifest, checkpoint=''):
    """Frozen probes need no project-training provenance; tuned ones do."""
    recorded = str(cache['checkpoint_sha256']) if 'checkpoint_sha256' in cache else ''
    tuned = '+tuned' in str(cache['model']) or bool(recorded)
    if not tuned:
        if checkpoint:
            raise ValueError('checkpoint supplied for a frozen cache')
        return
    if not checkpoint or not recorded:
        raise ValueError('tuned probe cache needs --checkpoint and checkpoint hash metadata')
    path = Path(checkpoint)
    if hashlib.sha256(path.read_bytes()).hexdigest() != recorded:
        raise ValueError('probe cache checkpoint hash mismatch')
    import torch
    state = torch.load(path, map_location='cpu', weights_only=False)
    verified = state.get('verified_manifest_sha256', {})
    if verified.get('publisher') != hashlib.sha256(Path(manifest).read_bytes()).hexdigest():
        raise ValueError('tuned probe checkpoint lacks matching isolated training provenance')


def write_report(path, report):
    payload = json.dumps(report, indent=1, allow_nan=False) + '\n'
    with Path(path).open('x', encoding='utf-8') as handle:
        handle.write(payload)
    print(payload, end='')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", default="local/training/manifest.csv")
    parser.add_argument("--embeddings", default="local/training/embeddings.npz")
    parser.add_argument("--head", choices=HEADS, required=True)
    parser.add_argument("--out", default="local/training/probe_report.json")
    parser.add_argument("--reviewed-labels", default="",
                        help="required for the construction_era head (label-campaign output)")
    parser.add_argument('--image-root', type=Path, default=Path('local/monument-inbox'))
    parser.add_argument('--image-reviews', type=Path,
                        help='required construction-image review directory; building-wide depicts is insufficient')
    parser.add_argument('--checkpoint', default='', help='required for tuned caches; verified training provenance')
    parser.add_argument('--eval-split', choices=('val', 'test'), default='val',
                        help='development validation by default; existing test cohort is spent')
    parser.add_argument('--acknowledge-spent-test', action='store_true',
                        help='required for exploratory reuse of the old test cohort')
    parser.add_argument('--grouped-cv', type=int, default=0, metavar='FOLDS',
                        help='exploratory train+val out-of-fold probe; frozen encoders only')
    parser.add_argument('--cv-seed', type=int, default=42)
    args = parser.parse_args()
    if args.grouped_cv != 0 and args.grouped_cv < 2:
        parser.error('--grouped-cv needs at least two folds')
    if args.grouped_cv and (args.eval_split != 'val' or args.acknowledge_spent_test):
        parser.error('grouped CV cannot use or acknowledge test evaluation')
    if args.eval_split == 'test' and not args.acknowledge_spent_test:
        parser.error('test cohort is spent; use validation or explicitly acknowledge exploratory reuse')
    if Path(args.out).exists():
        parser.error('output exists; refusing to replace a prior report')

    if args.head == "construction_era" and not args.reviewed_labels:
        raise SystemExit(
            "construction_era needs --reviewed-labels: contributor years and style "
            "windows are proxies, not training truth (see epoch_data docstring).")

    if args.head == 'construction_era' and not args.image_reviews:
        parser.error('construction_era requires --image-reviews with explicit per-image applicability')
    if args.head != 'construction_era' and args.image_reviews:
        parser.error('--image-reviews applies only to construction_era')

    cache = np.load(args.embeddings, allow_pickle=False)
    if args.grouped_cv and ('+tuned' in str(cache['model']) or
                            ('checkpoint_sha256' in cache and str(cache['checkpoint_sha256']))):
        parser.error('grouped CV requires a project-frozen encoder; tuned features saw fold-held-out buildings')
    validate_cache_training(cache, args.manifest, args.checkpoint)
    keys = cache['ids'].tolist()
    vectors = cache['embeddings']
    if len(keys) != len(set(keys)) or len(keys) != len(vectors):
        parser.error('embedding cache needs unique IDs and aligned vectors')
    by_id = dict(zip(keys, vectors))
    manifest_rows = load_manifest(args.manifest)
    manifest_ids, manifest_membership = set(), {}
    for row in manifest_rows:
        bid, split = row['building_id'], row['split']
        key = f"{bid}/{row['filename']}"
        if split not in ('train', 'val', 'test') or key in manifest_ids:
            parser.error('manifest needs valid splits and unique image IDs')
        if bid in manifest_membership and manifest_membership[bid] != split:
            parser.error(f'building {bid} occurs in multiple splits')
        manifest_ids.add(key)
        manifest_membership[bid] = split
        row['_path'] = args.image_root / row['building_id'] / row['filename']
    require_feature_bytes = bool(args.grouped_cv or args.head == 'construction_era')
    historical_excluded = set()
    if require_feature_bytes:
        for row in manifest_rows:
            key = f"{row['building_id']}/{row['filename']}"
            if key == '17387/11500227_0192_P04.jpg' and (key not in by_id or not row['_path'].is_file()):
                historical_excluded.add(key)
    audit_rows = [r for r in manifest_rows
                  if f"{r['building_id']}/{r['filename']}" not in historical_excluded]
    assert_image_isolation(audit_rows, [])
    rows = [r for r in audit_rows
            if (not args.grouped_cv or r['split'] in ('train', 'val'))
            and (require_feature_bytes or f"{r['building_id']}/{r['filename']}" in by_id)
            and (args.head != "capture_era" or (r["capture_era"] and r['drawing_flag'] is False))
            and (args.head != "drawing" or r['drawing_flag'] is not None)]
    reviewed: dict[str, str] = {}
    image_applicability = None
    if args.head == "construction_era":
        # Source labels describe buildings. Image-level reviews alone decide
        # which photographs may inherit those labels; no building-wide fallback.
        reviewed = load_reviewed_labels(args.reviewed_labels, labels_only=True)
        rows = with_reviewed_labels(rows, reviewed, labels_only=False)
        eligible, image_applicability = eligible_image_keys(
            args.image_reviews, args.manifest, args.reviewed_labels,
            manifest_rows, reviewed)
        rows = [r for r in rows if f"{r['building_id']}/{r['filename']}" in eligible]
    excluded = [f"{r['building_id']}/{r['filename']}" for r in rows
                if f"{r['building_id']}/{r['filename']}" not in by_id]
    if require_feature_bytes and not set(excluded) <= {'17387/11500227_0192_P04.jpg'}:
        scope = 'CV' if args.grouped_cv else 'construction'
        parser.error(f'undeclared {scope} cache gaps: {excluded}')
    rows = [r for r in rows if f"{r['building_id']}/{r['filename']}" in by_id]
    if not rows:
        if args.head == 'construction_era':
            raise SystemExit('no applicable construction image rows; complete human image reviews and encode eligible images')
        raise SystemExit("no labelled rows with embeddings; run build_embeddings.py first")

    if require_feature_bytes:
        scope = 'grouped CV' if args.grouped_cv else 'construction evaluation'
        if 'image_sha256' not in cache or len(cache['image_sha256']) != len(keys):
            parser.error(f'{scope} requires per-image SHA-256 cache metadata; re-encode, do not retrofit hashes')
        cached_hashes = dict(zip(keys, cache['image_sha256'].tolist()))
        for row in rows:
            key = f"{row['building_id']}/{row['filename']}"
            if cached_hashes[key] != row['_sha256']:
                parser.error(f'cached image bytes differ from current file: {key}')

    X = np.stack([by_id[f"{r['building_id']}/{r['filename']}"] for r in rows])
    y, classes = targets(rows, args.head, reviewed)
    if args.grouped_cv:
        report = grouped_development_cv(
            X, y, rows, classes, ordered=args.head in ('capture_era', 'construction_era'),
            n_splits=args.grouped_cv, seed=args.cv_seed)
        report['excluded_cache_ids'] = sorted(set(excluded) | historical_excluded)
        report['image_byte_provenance'] = 'per-image cache SHA-256 verified against current files before fold assignment'
        report['head'] = args.head
        report['embeddings_model'] = str(cache['model'])
        if args.head == 'construction_era':
            report['applicability_gate'] = 'explicit applicable per-image reviews pinned to current source bytes, label and phase'
            report['image_applicability'] = image_applicability
        report['target_semantics'] = TARGET_SEMANTICS[args.head]
        report['input_sha256'] = {
            'manifest': hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
            'embeddings': hashlib.sha256(Path(args.embeddings).read_bytes()).hexdigest(),
            'implementation': hashlib.sha256((ROOT/'training/development_cv.py').read_bytes()).hexdigest(),
            'probe': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'data_definitions': hashlib.sha256((ROOT/'epoch_data.py').read_bytes()).hexdigest(),
            'isolation': hashlib.sha256((ROOT/'training/data_integrity.py').read_bytes()).hexdigest(),
            'statistics': hashlib.sha256((ROOT/'training/stats.py').read_bytes()).hexdigest(),
        }
        if args.reviewed_labels:
            report['input_sha256']['reviewed_labels'] = hashlib.sha256(Path(args.reviewed_labels).read_bytes()).hexdigest()
        if args.image_reviews:
            for name in ('metadata.json', 'reviews.csv'):
                report['input_sha256']['image_reviews/' + name] = hashlib.sha256((args.image_reviews/name).read_bytes()).hexdigest()
            report['input_sha256']['image_review_implementation'] = hashlib.sha256((ROOT/'training/construction_image_reviews.py').read_bytes()).hexdigest()
        write_report(args.out, report)
        return

    splits = np.array([r["split"] for r in rows])
    eras = [r["capture_era"] for r in rows]
    building_ids = np.array([r["building_id"] for r in rows])
    # Internal legacy metric names are rewritten to the selected split below.
    evaluation = splits == args.eval_split
    test_ids = building_ids[evaluation].tolist()
    for split in ("train", args.eval_split):
        if not np.any(splits == split):
            raise SystemExit(f"no eligible {split} rows")
    membership = {}
    for bid, split in zip(building_ids, splits):
        if bid in membership and membership[bid] != split:
            raise SystemExit(f"building {bid} occurs in multiple splits")
        membership[bid] = split

    scaler = StandardScaler().fit(X[splits == "train"])
    Xs = scaler.transform(X)
    multilabel = y.ndim == 2
    base = LogisticRegression(max_iter=2000, C=1.0)
    clf = OneVsRestClassifier(base) if multilabel else base
    clf.fit(Xs[splits == "train"], y[splits == "train"])
    pred = clf.predict(Xs[evaluation])

    report: dict = {"head": args.head, "classes": list(classes),
                    "n_train": int((splits == "train").sum()),
                    "n_test": int((evaluation).sum()),
                    "embeddings_model": str(cache["model"]),
                    "dummy_majority_test_accuracy": None}
    for split in ("train", "val", "test"):
        report[f"n_{split}_buildings"] = len(set(building_ids[splits == split]))
    if args.head == "construction_era":
        report['applicability_gate'] = 'explicit applicable per-image reviews pinned to current source bytes, label and phase'
        report['image_applicability'] = image_applicability
        report['excluded_cache_ids'] = sorted(set(excluded) | historical_excluded)
        report['image_byte_provenance'] = 'per-image cache SHA-256 verified against current files before fitting'
        report['image_review_input_sha256'] = {
            'manifest': hashlib.sha256(Path(args.manifest).read_bytes()).hexdigest(),
            'labels': hashlib.sha256(Path(args.reviewed_labels).read_bytes()).hexdigest(),
            'metadata': hashlib.sha256((args.image_reviews/'metadata.json').read_bytes()).hexdigest(),
            'reviews': hashlib.sha256((args.image_reviews/'reviews.csv').read_bytes()).hexdigest(),
        }
    if multilabel:
        report["building_macro_exact_match_test"] = building_macro_mean(
            test_ids, np.all(pred == y[evaluation], axis=1))
        report["micro_f1_test"] = float(
            __import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(
                y[evaluation], pred, average="micro", zero_division=0))
        per_family = {}
        for pos, family in enumerate(classes):
            col_t, col_p = y[evaluation][:, pos], pred[:, pos]
            per_family[family] = {
                "support": int(col_t.sum()),
                "f1": float(__import__("sklearn.metrics", fromlist=["f1_score"]).f1_score(
                    col_t, col_p, zero_division=0))}
        report["per_family"] = per_family
    else:
        report['confusion_matrix'] = confusion_matrix(y[evaluation], pred, labels=range(len(classes))).tolist()
        report['per_class'] = classification_by_class(report['confusion_matrix'], classes)
        report["top1_test"] = float(np.mean(pred == y[evaluation]))
        report["building_macro_top1_test"] = building_macro_mean(
            test_ids, pred == y[evaluation])
        dummy = DummyClassifier(strategy="most_frequent").fit(
            Xs[splits == "train"], y[splits == "train"])
        report["dummy_majority_test_accuracy"] = float(dummy.score(Xs[evaluation], y[evaluation]))
        report["dummy_majority_building_macro_test_accuracy"] = building_macro_mean(
            test_ids, dummy.predict(Xs[evaluation]) == y[evaluation])
        if args.head in ("capture_era", "construction_era"):
            report["building_macro_within_one_era_test"] = building_macro_mean(
                test_ids, np.abs(pred - y[evaluation]) <= 1)
            report["within_one_era_test"] = within_one_era(y[evaluation], pred)
    if args.head in ("drawing", "capture_era", "construction_era"):
        # Disentanglement slices: accuracy per capture era on the test split.
        slices = {}
        for era in sorted(set(eras)):
            mask = np.array([(s == args.eval_split and e == era) for s, e in zip(splits, eras)])
            if mask.sum() >= 20:
                slices[era] = {"n": int(mask.sum()),
                               "n_buildings": len(set(building_ids[mask])),
                               "building_macro_accuracy": building_macro_mean(
                                   building_ids[mask].tolist(),
                                   pred[mask[evaluation]] == y[mask]),
                               "accuracy": float(np.mean(pred[mask[evaluation]] == y[mask]))}
                matrix = confusion_matrix(y[mask], pred[mask[evaluation]], labels=range(len(classes))).tolist()
                slices[era]['confusion_matrix'] = matrix
                slices[era]['per_class'] = classification_by_class(matrix, classes)
        report["per_capture_era_test"] = slices

    if args.eval_split != 'test':
        report = {key.replace('_test', '_val'): value for key, value in report.items()}
        # Keep dataset inventory counts named for their actual split.
        report['n_test_buildings'] = len(set(building_ids[splits == 'test']))
        report['n_val_buildings'] = len(set(building_ids[splits == 'val']))
    report['target_semantics'] = TARGET_SEMANTICS[args.head]
    report['evaluation_split'] = args.eval_split
    report['evaluation_role'] = 'exploratory development; not a new locked holdout'
    write_report(args.out, report)


if __name__ == "__main__":
    main()
