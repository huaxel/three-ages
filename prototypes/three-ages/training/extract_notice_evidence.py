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

STRONG = re.compile(r'\b(érig|erig|constru|construit|bâti|bati|édifi|edifi|reconstru)',
                   re.I)
REBUILD = re.compile(r'\b(reconstru|rebâti|rebati|réédifi|reedifi|remplacé|remplace)',
                     re.I)
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


def bin_of(year: int) -> str:
    if year < 1850: return 'pre-1850'
    if year < 1893: return '1850-1892'
    if year < 1915: return '1893-1914'
    if year < 1941: return '1918-1940'
    if year < 1976: return '1945-1975'
    return 'post-1975'


def extract(record: dict) -> dict:
    """Quote the notice and separate construction years from incidental ones.

    A building notice mentions many years: a founding, a fire, a later wing.
    Treating them all as construction evidence made 47 of 60 rows look
    multi-era, so sentences are graded: those with a construction verb carry the
    primary years, incidental years are kept separately as context.
    """
    blobs = []
    description = record.get('description') or {}
    if isinstance(description, dict) and description.get('html'):
        blobs.append(('description', plain(description['html'])))
    details = record.get('details') or {}
    if isinstance(details, dict):
        for key, value in details.items():
            if isinstance(value, (str, dict, list)):
                blobs.append((f'details:{key}', plain(value)))

    strong, contextual, sources = [], [], set()
    for label, text in blobs:
        for sentence in sentences(text):
            years = [int(y) for y in YEAR.findall(sentence)]
            if not years and not CUES.search(sentence):
                continue
            bucket = strong if (years and STRONG.search(sentence)) else contextual
            if years:
                bucket.append((sentence, years))
                sources.add(label)

    excerpts = [s_ for s_, _ in (strong + contextual)][:MAX_EXCERPTS]
    primary = sorted({y for _, years in strong for y in years})
    strength = 'construction' if strong else ('contextual' if contextual else 'none')
    if not primary:
        primary = sorted({y for _, years in contextual for y in years})
    every = sorted({y for _, years in strong + contextual for y in years})
    rebuild = any(REBUILD.search(sentence) for sentence, _ in strong + contextual)
    return {
        'suggested_era': bin_of(primary[0]) if primary else '',
        'rebuild_flag': 'review' if rebuild else '',
        'notice_excerpt': ' | '.join(e[:MAX_CHARS] for e in excerpts),
        'notice_sources': ';'.join(sorted(sources)),
        'notice_years': ';'.join(str(y) for y in every),
        'primary_years': ';'.join(str(y) for y in primary),
        'evidence_strength': strength,
    }


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
        found = extract(record if isinstance(record, dict) else {})
        row.update(found)
        if found.get('primary_years'):
            covered += 1

    fields = list(rows[0].keys())
    for extra in ('notice_excerpt', 'notice_sources', 'notice_years',
                  'primary_years', 'evidence_strength', 'suggested_era',
                  'rebuild_flag'):
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
