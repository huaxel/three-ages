"""Development-only grouped CV over frozen image representations.

Never supplies test rows to a fit/score operation. Buildings linked by shared
images remain together. Each fold fits its own scaler and classifier. These
are exploratory head-selection estimates, not a fresh confirmation holdout.
"""
from __future__ import annotations

import numpy as np
import sklearn
import sys
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler

from stats import building_macro_mean, classification_by_class


def development_folds(rows, *, n_splits=5, seed=42):
    """Deterministic balanced-by-image folds, independent of labels/row order."""
    if isinstance(n_splits, bool) or not isinstance(n_splits, int) or n_splits < 2:
        raise ValueError('grouped CV needs at least two folds')
    groups = {}
    buildings = {}
    ids = set()
    for index, row in enumerate(rows):
        if row.get('split') not in ('train', 'val'):
            raise ValueError('development CV accepts train/val rows only, never test')
        bid = row['building_id']
        group = row['_evaluation_group']
        key = f"{bid}/{row['filename']}"
        if key in ids:
            raise ValueError(f'duplicate image ID: {key}')
        ids.add(key)
        if bid in buildings and buildings[bid] != group:
            raise ValueError(f'building {bid} has inconsistent dependency groups')
        buildings[bid] = group
        groups.setdefault(group, []).append(index)
    if len(groups) < n_splits:
        raise ValueError(f'{n_splits} folds require at least {n_splits} independent groups; got {len(groups)}')
    # Use seeded stable hashes solely to break equal-size ties, not source labels.
    import hashlib
    ordered = sorted(groups, key=lambda g: (
        -len(groups[g]), hashlib.sha256(f'{seed}|{g}'.encode()).hexdigest(), g))
    buckets, sizes = [[] for _ in range(n_splits)], [0] * n_splits
    for group in ordered:
        fold = min(range(n_splits), key=lambda i: (sizes[i], i))
        buckets[fold].extend(groups[group])
        sizes[fold] += len(groups[group])
    indices = np.arange(len(rows))
    for bucket in buckets:
        score = np.array(sorted(bucket), dtype=int)
        fit = np.setdiff1d(indices, score)
        yield fit, score


def grouped_development_cv(X, y, rows, classes, *, ordered=False, n_splits=5, seed=42):
    """Return out-of-fold diagnostics; never select C/thresholds on these data."""
    X, y = np.asarray(X), np.asarray(y)
    if len(rows) != len(X) or len(rows) != len(y) or X.ndim != 2 or not np.isfinite(X).all():
        raise ValueError('finite aligned feature/target rows required')
    multilabel = y.ndim == 2
    if y.ndim not in (1, 2):
        raise ValueError('single-label vector or multi-label matrix required')
    if not classes or len(set(classes)) != len(classes) or not np.isfinite(y).all():
        raise ValueError('finite targets and nonempty unique classes required')
    if multilabel:
        if ordered or y.shape[1] != len(classes) or not np.isin(y, [0, 1]).all():
            raise ValueError('multilabel targets must be binary class columns and cannot be ordered')
    elif not np.isin(y, np.arange(len(classes))).all():
        raise ValueError('class targets must be integer indices into classes')
    folds = list(development_folds(rows, n_splits=n_splits, seed=seed))
    # Fail before any fitting if a fold cannot train an actual classifier.
    for fit, _ in folds:
        if not multilabel and len(np.unique(y[fit])) < 2:
            raise ValueError('a CV training fold has fewer than two classes; reduce folds or review more development groups')
    prediction = np.empty_like(y)
    dummy_prediction = np.empty_like(y)
    fold_of = np.empty(len(rows), dtype=int)
    reports = []
    for fold, (fit, score) in enumerate(folds):
        scaler = StandardScaler().fit(X[fit])
        Xfit, Xscore = scaler.transform(X[fit]), scaler.transform(X[score])
        base = LogisticRegression(max_iter=2000, C=1.0)
        estimator = OneVsRestClassifier(base) if multilabel else base
        estimator.fit(Xfit, y[fit])
        prediction[score] = estimator.predict(Xscore)
        dummy = DummyClassifier(strategy='most_frequent').fit(Xfit, y[fit])
        dummy_prediction[score] = dummy.predict(Xscore)
        fold_of[score] = fold
        reports.append({
            'fold': fold,
            'n_fit_images': len(fit), 'n_score_images': len(score),
            'fit_buildings': sorted({rows[i]['building_id'] for i in fit}),
            'score_buildings': sorted({rows[i]['building_id'] for i in score}),
            'fit_groups': sorted({rows[i]['_evaluation_group'] for i in fit}),
            'score_groups': sorted({rows[i]['_evaluation_group'] for i in score}),
            'fit_class_support': _support(y[fit], classes),
            'score_class_support': _support(y[score], classes),
        })
    bids = [r['building_id'] for r in rows]
    groups = [r['_evaluation_group'] for r in rows]
    exact = np.all(prediction == y, axis=1) if multilabel else prediction == y
    dummy_exact = np.all(dummy_prediction == y, axis=1) if multilabel else dummy_prediction == y
    metrics = {
        'image_exact_accuracy': float(np.mean(exact)),
        'building_macro_exact_accuracy': building_macro_mean(bids, exact),
        'dummy_image_exact_accuracy': float(np.mean(dummy_exact)),
        'dummy_building_macro_exact_accuracy': building_macro_mean(bids, dummy_exact),
    }
    # Folds share training data. A naive bootstrap of fixed OOF predictions is
    # NOT a generalisation CI for the fitting/model-selection process, so none
    # is emitted. Report paired descriptive effects and raw outcomes instead.
    metrics['building_macro_exact_improvement_over_dummy'] = (
        metrics['building_macro_exact_accuracy'] - metrics['dummy_building_macro_exact_accuracy'])
    if multilabel:
        metrics['micro_f1'] = float(f1_score(y, prediction, average='micro', zero_division=0))
    else:
        metrics['confusion_matrix'] = confusion_matrix(y, prediction, labels=range(len(classes))).tolist()
        metrics['per_class'] = classification_by_class(metrics['confusion_matrix'], classes)
    if ordered:
        adjacent = np.abs(prediction - y) <= 1
        dummy_adjacent = np.abs(dummy_prediction - y) <= 1
        metrics.update(image_within_one_era=float(np.mean(adjacent)),
                       building_macro_within_one_era=building_macro_mean(bids, adjacent),
                       dummy_building_macro_within_one_era=building_macro_mean(bids, dummy_adjacent))
    era_slices = {}
    era_labels = np.array([r.get('capture_era') or 'unknown' for r in rows])
    for era in sorted(set(era_labels)):
        mask = era_labels == era
        slice_bids = [bid for bid, keep in zip(bids, mask) if keep]
        slice_groups = [group for group, keep in zip(groups, mask) if keep]
        entry = {'n_images': int(mask.sum()), 'n_buildings': len(set(slice_bids)),
                 'n_groups': len(set(slice_groups)), 'class_support': _support(y[mask], classes),
                 'building_macro_exact_accuracy': building_macro_mean(slice_bids, exact[mask]),
                 'dummy_building_macro_exact_accuracy': building_macro_mean(slice_bids, dummy_exact[mask])}
        if not multilabel:
            entry['confusion_matrix'] = confusion_matrix(y[mask], prediction[mask], labels=range(len(classes))).tolist()
            entry['per_class'] = classification_by_class(entry['confusion_matrix'], classes)
        if ordered:
            entry['building_macro_within_one_era'] = building_macro_mean(slice_bids, adjacent[mask])
        era_slices[str(era)] = entry
    outcomes = []
    for i, row in enumerate(rows):
        outcomes.append({'id': f"{row['building_id']}/{row['filename']}",
                         'building_id': row['building_id'], 'group': row['_evaluation_group'],
                         'fold': int(fold_of[i]), 'capture_era': row.get('capture_era', ''),
                         'true': y[i].tolist(), 'predicted': prediction[i].tolist(),
                         'dummy_predicted': dummy_prediction[i].tolist()})
    return {
        'schema': 'development-grouped-cv/1',
        'evaluation_role': 'exploratory development; not locked confirmation',
        'representation_requirement': 'project-frozen encoder; no fine-tuning on fold-held-out buildings',
        'pretraining_overlap': 'foundation-model pretraining overlap with this corpus is unverified',
        'splits_used': sorted({r['split'] for r in rows}), 'test_rows_used': 0,
        'n_images': len(rows), 'n_buildings': len(set(bids)), 'n_groups': len(set(groups)),
        'classes': list(classes), 'seed': seed, 'n_folds': n_splits,
        'estimator': {'name': 'LogisticRegression', 'C': 1.0, 'max_iter': 2000,
                      'preprocessing': 'fold-local StandardScaler',
                      'multilabel': 'OneVsRestClassifier' if multilabel else None,
                      'dummy': 'most_frequent, fitted per fold'},
        'toolchain': {'python': sys.version.split()[0], 'numpy': np.__version__,
                      'scikit_learn': sklearn.__version__},
        'fold_assignment': 'greedy image-count balance; seeded hash tie-break; independent of labels',
        'metrics': metrics, 'per_capture_era': era_slices,
        'folds': reports, 'outcomes': outcomes,
        'uncertainty_limitation': 'OOF folds share fitted training data; no independent-replication or generalisation CI claimed',
    }


def _support(y, classes):
    if y.ndim == 2:
        return {name: int(y[:, i].sum()) for i, name in enumerate(classes)}
    return {name: int(np.sum(y == i)) for i, name in enumerate(classes)}
