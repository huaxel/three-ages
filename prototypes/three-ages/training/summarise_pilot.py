#!/usr/bin/env python3
"""Summarise a finished pilot: frozen vs tuned held-out validation.

Fails loudly on incomplete runs. Reports differences in absolute terms and
relative to each baseline, and states plainly what the numbers do and do not
establish. Test-split metrics are never read here.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REQUIRED = ('frozen_validation', 'tuned_validation', 'training', 'sha256')


def pct(value: float) -> str:
    return f'{100*value:.2f}%'


def main() -> None:
    run = Path(sys.argv[1])
    report_path = run / 'report.json'
    if not report_path.is_file():
        raise SystemExit(f'no report at {report_path}')
    report = json.loads(report_path.read_text())
    if report.get('state') != 'complete':
        raise SystemExit(f"run state is {report.get('state')!r}, not complete")
    missing = [k for k in REQUIRED if k not in report]
    if missing:
        raise SystemExit(f'report missing: {missing}')
    for name in ('publisher', 'cross_pole'):
        for side in ('frozen_validation', 'tuned_validation'):
            if name not in report[side] or 'top5' not in report[side][name]:
                raise SystemExit(f'{side}.{name} incomplete')

    lines = ['# Contrastive pilot: held-out validation summary', '',
             f"run: `{run}`",
             f"kernel: `{report['kernel']}`  torch: `{report['torch']}`",
             f"pairs: {report['pairs']} ({report['pair_kinds']})",
             f"training: {report['training']['steps']} steps, "
             f"{report['training']['pairs_seen']} pairs, "
             f"{report['training']['seconds']:.0f}s, "
             f"mean loss {report['training']['mean_loss']:.4f}, "
             f"peak {report['training']['peak_allocated_gib']:.2f} GiB",
             f"query split: **{report['query_split']}** only, "
             f"gallery: {report['gallery']} publisher images", '',
             '| leg | metric | frozen | tuned | delta |',
             '|---|---|---:|---:|---:|']
    for leg, label in (('publisher', 'publisher cross-era'),
                       ('cross_pole', 'cross-pole')):
        fz, tu = report['frozen_validation'][leg], report['tuned_validation'][leg]
        key = 'cross_era_top5_fair' if leg == 'publisher' else 'top5'
        rows = [('top5', 'top5'), ('cross_era_top5_fair', 'cross-era top5')]
        for metric, name in rows:
            if metric not in fz or metric not in tu:
                continue
            lines.append(f"| {label} | {name} | {pct(fz[metric])} | "
                         f"{pct(tu[metric])} | {100*(tu[metric]-fz[metric]):+.2f} pp |")
        lines.append(f"| {label} | queries (denominator) | {fz.get('queries_with_mates')} "
                     f"| {tu.get('queries_with_mates')} | — |")
        if 'cross_era_eligible_queries' in fz:
            lines.append(f"| {label} | cross-era eligible | "
                         f"{fz['cross_era_eligible_queries']} | "
                         f"{tu.get('cross_era_eligible_queries')} | — |")
    lines += ['', '## What this establishes', '',
              '- Both feature sets were scored on identical galleries, identical '
              'query IDs, and identical denominators.',
              '- Queries come from the validation split; test images act only as '
              'fixed distractors and are never queries.',
              '- These validation numbers are **not** comparable to the earlier '
              'test-split headlines (frozen test: 1.9% publisher cross-era, '
              '0.9% cross-pole).',
              '', '## What this does not establish', '',
              '- A lift shows the backbone learned to match **same-building** '
              'pairs given weak building labels; it does not prove architectural-'
              'age disentanglement.',
              '- Publisher-era bins are caption-derived; Mapillary-to-building '
              'assignment can be noisy, so some positives may be wrong.',
              '- One epoch, one seed, one learning rate: no variance estimate.',
              '']
    text = '\n'.join(lines)
    (run / 'summary.md').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
