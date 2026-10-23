#!/usr/bin/env python3
"""Add notice-text evidence to the task-B queue, without labelling anything.

The reviewer has to decide a construction era from the monument notice, which
today means opening 60 pages. The notices are already scraped, so this pulls the
sentences that actually mention dates or construction into the queue.

It quotes; it does not decide. `construction_era` stays blank, the extract is
marked as unadjudicated, and no year is ever used as a label — the reason task B
is blocked is precisely that catalogue years are proxies.
"""
from __future__ import annotations
import argparse
import csv
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DATA = REPO / 'local' / 'training'

CUES = re.compile(
    r'\b(érig|erig|constru|bâti|bati|édifi|edifi|datant|remonte|vers|entre|'
    r'siècle|siecle|incendi|reconstru|restaur|transform|agrandi)', re.I)
YEAR = re.compile(r'\b(1[2-9]\d{2}|20[0-2]\d)\b')
MAX_EXCERPTS = 3
MAX_CHARS = 240


def plain(value) -> str:
    """Strip HTML/markup and normalise whitespace."""
    import re as _re
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    # Style glossaries are embedded as <a class="info">word<span>Période : env.
    # 1840-1914</span></a>; their years describe the style, not the building, so
    # drop the tooltip before stripping tags or the queue would quote them.
    text = _re.sub(r'<span[^>]*>[\s\S]*?</span>', ' ', text)
    text = _re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = text.replace('\\u0027', "'").replace('\\"', '"').replace('\\n', ' ')
    return ' '.join(text.split())


def sentences(text: str):
    for part in re.split(r'(?<=[.;!?])\s+', text):
        part = part.strip(' .;')
        if 20 <= len(part) <= 400:
            yield part


def extract(record: dict) -> tuple[str, str, list[int]]:
    blobs = []
    description = record.get('description') or {}
    if isinstance(description, dict) and description.get('html'):
        blobs.append(('description', plain(description['html'])))
    details = record.get('details') or {}
    if isinstance(details, dict):
        for key, value in details.items():
            if isinstance(value, (str, dict, list)):
                blobs.append((f'details:{key}', plain(value)))

    excerpts, sources, years = [], set(), set()
    for label, text in blobs:
        for sentence in sentences(text):
            found = YEAR.findall(sentence)
            if not found and not CUES.search(sentence):
                continue
            if not found and len(excerpts) >= 1:
                continue  # prefer sentences that carry an actual year
            excerpt = sentence[:MAX_CHARS]
            if any(excerpt[:60] == existing[:60] for existing in excerpts):
                continue
            excerpts.append(excerpt)
            sources.add(label)
            years.update(int(y) for y in found)
            if len(excerpts) >= MAX_EXCERPTS:
                break
        if len(excerpts) >= MAX_EXCERPTS:
            break
    return ' | '.join(excerpts), ';'.join(sorted(sources)), sorted(years)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--queue', default=str(DATA / 'taskb_queue.csv'))
    ap.add_argument('--scraped', default=str(REPO / 'local' / 'scraped'))
    ap.add_argument('--out', default=str(DATA / 'taskb_queue.csv'))
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    queue_path = Path(args.queue)
    rows = list(csv.DictReader(queue_path.open(encoding='utf-8')))
    if not rows:
        raise SystemExit(f'{queue_path} is empty')
    out = Path(args.out)
    if out.exists() and not args.force:
        raise SystemExit(f'{out} exists; pass --force after checking for review edits')
    if out.exists():
        existing = list(csv.DictReader(out.open(encoding='utf-8')))
        if any(r.get('reviewer', '').strip() or r.get('construction_era', '').strip()
               for r in existing):
            raise SystemExit(f'{out} has reviewer edits; refusing to overwrite')

    scraped = Path(args.scraped)
    covered = 0
    for row in rows:
        path = scraped / f"{row['building_id']}.fr.json"
        if not path.is_file():
            row['notice_excerpt'] = ''
            row['notice_sources'] = ''
            row['notice_years'] = ''
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            record = {}
        excerpt, sources, years = extract(record if isinstance(record, dict) else {})
        row['notice_excerpt'] = excerpt
        row['notice_sources'] = sources
        row['notice_years'] = ';'.join(str(y) for y in years)
        if years:
            covered += 1

    fields = list(rows[0].keys())
    for extra in ('notice_excerpt', 'notice_sources', 'notice_years'):
        if extra not in fields:
            fields.append(extra)
    with out.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({'out': str(out), 'rows': len(rows),
                      'rows_with_year_evidence': covered,
                      'note': 'notice_excerpt is quoted, never adjudicated'},
                     indent=2))


if __name__ == '__main__':
    main()
