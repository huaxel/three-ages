#!/usr/bin/env python3
"""Check every headline number in the results document against its evidence file.

The narrative lives in docs/three-ages-finetune-pilot-result.md, but its numbers
are only trustworthy if a reader can trace them. This asserts the quoted values
against the reports committed in ./evidence/, using the standard library only so
it can run anywhere without a GPU, torch or the corpus.

A failure here means the document and its evidence have drifted apart.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EV = HERE / 'evidence'


def load(name: str) -> dict:
    path = EV / name
    if not path.is_file():
        raise SystemExit(f'missing evidence file: {path}')
    return json.loads(path.read_text())


def pct(value: float) -> str:
    return f'{100 * value:.2f}%'


CHECKS = []


def check(label, actual, expected, tol=0.0002):
    CHECKS.append((label, actual, expected, abs(actual - expected) <= tol))


def main() -> None:
    # Test split: random-order checkpoint, then the validation-selected one.
    v2 = load('report_test_final_v2.json')
    check('test publisher cross-era, frozen',
          v2['frozen']['publisher_test']['cross_era_top5_fair'], 0.006356)
    check('test publisher cross-era, random order',
          v2['tuned']['publisher_test']['cross_era_top5_fair'], 0.045767)
    check('test cross-pole top5, frozen',
          v2['frozen']['cross_pole_test']['top5'], 0.009274)
    check('test cross-pole top5, random order',
          v2['tuned']['cross_pole_test']['top5'], 0.042072)

    hn = load('report_test_hardneg.json')
    check('test publisher cross-era, hard negatives',
          hn['tuned']['publisher_test']['cross_era_top5_fair'], 0.054200)
    check('test publisher top5, hard negatives',
          hn['tuned']['publisher_test']['top5'], 0.342600)
    check('test cross-pole top5, hard negatives',
          hn['tuned']['cross_pole_test']['top5'], 0.047300)
    check('test cross-pole cross-era, hard negatives',
          hn['tuned']['cross_pole_test']['cross_era_top5_fair'], 0.016100)

    # Validation runs quoted in the training tables.
    r1 = load('pilot-20261022-232106__report.json')['tuned_validation']
    check('val publisher cross-era, epoch 1 random',
          r1['publisher']['cross_era_top5_fair'], 0.038000)
    check('val cross-pole top5, epoch 1 random', r1['cross_pole']['top5'], 0.046800)

    # Two different second-epoch runs: random order and hard negatives.
    e2 = load('pilot-epoch2-20261023-105251__report.json')['tuned_validation']
    check('val publisher top5, epoch 2 (random)', e2['publisher']['top5'], 0.284500)
    h2 = load('pilot-hard-epoch2-20261023-163620__report.json')['tuned_validation']
    check('val publisher top5, epoch 2 (hard neg)', h2['publisher']['top5'], 0.284100)
    check('val cross-pole top5, epoch 2 (hard neg)', h2['cross_pole']['top5'], 0.044400)

    ref = load('pilot-refresh2e-20261023-173100__report.json')['tuned_validation']
    check('val publisher cross-era, epoch 2 refreshed',
          ref['publisher']['cross_era_top5_fair'], 0.046200)
    check('val cross-pole cross-era, epoch 2 refreshed',
          ref['cross_pole']['cross_era_top5_fair'], 0.014500)

    # Neighbour control and out-of-source slice.
    nc = load('report_neighbour_control.json')
    check('neighbour chance floor', nc['frozen']['cluster_gallery_chance'], 0.790700)
    check('neighbour cluster top1, frozen',
          nc['frozen']['cluster_gallery_top1_same_building'], 0.801700)
    check('neighbour cluster top1, tuned',
          nc['tuned']['cluster_gallery_top1_same_building'], 0.829000)
    cs = load('report_curated_slice.json')
    check('out-of-source top5, tuned', cs['tuned']['top5_same_unit'], 0.558400)
    check('out-of-source cross-era, tuned', cs['tuned']['top5_cross_era_same_unit'], 0.350600)
    check('out-of-source chance', cs['tuned']['top5_same_unit_chance'], 0.144800)
    # Drift guard: the worksheet is a living file. If it grows, the slice numbers
    # above describe data that no longer exists and this check must fail.
    worksheet = (HERE.parent / 'data' / 'three-ages-image-review.csv')
    if worksheet.is_file():
        import csv as _csv
        rows = sum(1 for _ in _csv.DictReader(worksheet.open(encoding='utf-8')))
        check('curated slice image count matches worksheet', cs['images'], rows, tol=0)

    # Forgetting check.
    fd = load('report_drawing_frozen_venv.json')
    td = load('report_drawing_tuned.json')
    check('drawing probe frozen', fd['top1_test'], 0.977700)
    check('drawing probe tuned', td['top1_test'], 0.976800)
    fc = load('report_capture_era_frozen_venv.json')
    tc = load('report_capture_era_tuned.json')
    check('capture-era probe frozen', fc['top1_test'], 0.904000)
    check('capture-era probe tuned', tc['top1_test'], 0.887000)
    # The recommended checkpoint, whose forgetting profile was measured later.
    fd2 = load('report_drawing_refresh2e.json')
    tc2 = load('report_capture_era_refresh2e.json')
    check('drawing probe, hard + refreshed', fd2['top1_test'], 0.975100)
    check('capture-era probe, hard + refreshed', tc2['top1_test'], 0.874100)
    fd1 = load('report_drawing_hard42.json')
    tc1 = load('report_capture_era_hard42.json')
    check('drawing probe, hard e1', fd1['top1_test'], 0.976100)
    check('capture-era probe, hard e1', tc1['top1_test'], 0.873300)

    # Frozen, isolated, development-only follow-up. No spent-test queries scored.
    dev = load('drawing-grouped-development-20261025.json')
    protocol_path = EV / 'drawing-development-protocol-20261025.json'
    import hashlib
    check('development protocol hash mismatch',
          int(hashlib.sha256(protocol_path.read_bytes()).hexdigest() != dev['protocol_sha256']), 0, tol=0)
    check('development test rows scored', dev['test_rows_used'], 0, tol=0)
    check('development images', dev['n_images'], 69376, tol=0)
    check('development buildings', dev['n_buildings'], 23734, tol=0)
    check('development dependency groups', dev['n_groups'], 23601, tol=0)
    check('frozen cache byte-verified vectors', dev['cache_verification']['rows'], 76999, tol=0)
    check('development drawing macro', dev['metrics']['building_macro_exact_accuracy'], .9871, tol=.00005)
    check('development drawing macro dummy', dev['metrics']['dummy_building_macro_exact_accuracy'], .9350, tol=.00005)
    check('development drawing image accuracy', dev['metrics']['image_exact_accuracy'], .9761, tol=.00005)
    check('development drawing image dummy', dev['metrics']['dummy_image_exact_accuracy'], .9025, tol=.00005)
    check('development macro improvement', dev['metrics']['building_macro_exact_improvement_over_dummy'], .0521, tol=.00005)
    for era, expected in [('pre-1900', .8329), ('1900-1929', .8528),
                          ('1930-1959', .8471), ('1960-1989', .9860),
                          ('1990-2009', .9967), ('2010+', .9995), ('unknown', .9796)]:
        check('development drawing era ' + era,
              dev['per_capture_era'][era]['building_macro_exact_accuracy'], expected, tol=.00005)
    class_slices = dev['post_hoc_class_diagnostics']['per_capture_era']
    for era, photo_recall, drawing_recall in [
            ('pre-1900', .4136, .9354), ('1900-1929', .5564, .9409),
            ('1930-1959', .6998, .9234), ('1960-1989', .9901, .8393),
            ('1990-2009', .9992, .5495), ('2010+', .9997, .2449),
            ('unknown', .9843, .7656)]:
        check('development photo recall ' + era, class_slices[era]['photo']['recall'], photo_recall, tol=.00005)
        check('development drawing recall ' + era, class_slices[era]['drawing']['recall'], drawing_recall, tol=.00005)
    check('modern drawing proxy support', class_slices['2010+']['drawing']['support'], 49, tol=0)
    check('modern drawing proxy recovered', class_slices['2010+']['drawing']['true_positive'], 12, tol=0)
    check('old photo proxy support', class_slices['pre-1900']['photo']['support'], 324, tol=0)
    check('old photo proxy recovered', class_slices['pre-1900']['photo']['true_positive'], 134, tol=0)
    scope = load('capture-era-scope-audit-20261025.json')
    check('historical dated drawing-flag rows', scope['drawing_flag_rows'], 767, tol=0)
    check('historical dated rows scope', scope['dated_test_rows'], 7143, tol=0)

    # Publication guard: this repository is public, so committed artifacts must
    # not carry absolute home paths (they leak usernames and local layout).
    leaks = []
    for path in sorted((HERE / 'evidence').glob('*')):
        if path.is_file() and path.suffix in ('.json', '.md', '.csv'):
            text = path.read_text(encoding='utf-8', errors='replace')
            if '/home/' in text or '/Users/' in text:
                leaks.append(path.name)
    check('no absolute home paths in evidence', len(leaks), 0, tol=0)
    if leaks:
        print('  leaking files:', ', '.join(leaks))

    failures = 0
    for label, actual, expected, ok in CHECKS:
        status = 'ok  ' if ok else 'FAIL'
        # Rates are printed as percentages; counts (e.g. image totals) as integers.
        fmt = (lambda v: pct(v)) if expected <= 1.5 else (lambda v: f'{int(round(v))}')
        print(f'{status} {label:46} evidence {fmt(actual):>8}  doc {fmt(expected):>8}')
        failures += not ok
    print(f'\n{len(CHECKS) - failures}/{len(CHECKS)} documented numbers trace to evidence')
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
