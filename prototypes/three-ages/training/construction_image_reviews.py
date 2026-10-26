#!/usr/bin/env python3
"""Prepare NEW image applicability worksheets; never infer visual review decisions.

CSV decisions are human attestations, not authentication. Keep metadata.json
read-only alongside reviews.csv. Coordinated rewriting of unsigned metadata and
reviews is not detectable; exact bytes do not detect near-duplicate imagery.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from epoch_data import load_manifest, load_reviewed_labels
from data_integrity import sha256

APPLICABILITY = (
    'applicable', 'wrong_subject', 'predecessor', 'interior_or_detail',
    'not_visually_inferable', 'unknown',
)
IMMUTABLE = ('building_id', 'filename', 'image_sha256', 'construction_era', 'phase_years')
EDITABLE = ('applicability', 'observation', 'reviewer', 'reviewed_at', 'confidence')
FIELDS = IMMUTABLE + EDITABLE
SCHEMA = 'construction-image-reviews/1'
LIMITATIONS = (
    'Only explicit applicable image reviews with complete human metadata are eligible; '
    'missing, blank and unknown decisions are excluded. Building-level depicts_building '
    'is not image evidence. Exact hashes do not establish identity, visibility, licence, '
    'near-duplicate isolation or label correctness. Human attestations and unsigned '
    'metadata are not cryptographically authenticated.'
)


def image_key(row: dict) -> str:
    # Components are disk names, not paths; avoid ambiguous keys/path traversal.
    for field in ('building_id', 'filename'):
        value = row.get(field, '')
        if not value or value in ('.', '..') or '/' in value or '\\' in value:
            raise ValueError(f'invalid {field}: {value!r}')
    return f"{row['building_id']}/{row['filename']}"


def _csv(path: Path, required=()) -> list[dict]:
    with path.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        if len(fields) != len(set(fields)) or not set(required) <= set(fields):
            raise ValueError(f'invalid CSV columns: {path}')
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError(f'malformed CSV row: {path}')
    return rows


def _labels(path: Path) -> tuple[dict[str, str], dict[str, dict]]:
    # Deliberately ignore building-wide depicts_building as an eligibility gate.
    reviewed = load_reviewed_labels(path, labels_only=True)
    source = {r['building_id'].strip(): r for r in _csv(path)}
    return reviewed, source


def _snapshot(row: dict, reviewed: dict, source: dict) -> dict:
    bid = row['building_id']
    digest = row.get('_sha256') or sha256(Path(row['_path']))
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError(f'invalid current image SHA-256 for {image_key(row)}')
    return dict(building_id=bid, filename=row['filename'], image_sha256=digest,
                construction_era=reviewed[bid],
                phase_years=(source[bid].get('phase_years') or '').strip())


def prepare(manifest_path: Path, reviewed_labels_path: Path, image_root: Path,
            out_dir: Path, building_ids: list[str] | None = None) -> dict:
    """Write metadata.json, reviews.csv and contact-sheet.html to a NEW directory."""
    manifest_path, reviewed_labels_path = Path(manifest_path), Path(reviewed_labels_path)
    image_root, out_dir = Path(image_root), Path(out_dir)
    if out_dir.exists() or out_dir.is_symlink():
        raise ValueError('output directory exists; refusing to replace any artifacts')
    reviewed, source = _labels(reviewed_labels_path)
    selected = set(building_ids) if building_ids is not None else set(reviewed)
    if not selected <= set(reviewed):
        raise ValueError('building IDs must have human-reviewed construction labels')
    rows, cards, seen = [], [], set()
    for row in load_manifest(manifest_path):
        key = image_key(row)
        if key in seen:
            raise ValueError(f'duplicate manifest image ID: {key}')
        seen.add(key)
        if row['building_id'] not in selected or row.get('drawing_flag') is not False:
            continue
        path = (image_root / row['building_id'] / row['filename']).resolve()
        if not path.is_relative_to(image_root.resolve()):
            raise ValueError(f'image escapes root: {key}')
        row['_path'] = path
        immutable = _snapshot(row, reviewed, source)
        rows.append({**immutable, **dict.fromkeys(EDITABLE, '')})
        label = source[row['building_id']]
        esc = lambda value: html.escape(str(value), quote=True)
        image_url = quote(Path(os.path.relpath(path, out_dir.resolve())).as_posix(), safe='/')
        cards.append(
            '<article><h2>' + esc(key) + '</h2><a href="' + esc(image_url) +
            '"><img loading="lazy" width="360" src="' + esc(image_url) +
            '"></a><p>Source construction label: ' + esc(immutable['construction_era']) +
            '; phase years: ' + esc(immutable['phase_years']) + '</p><p>Source evidence: ' +
            esc(label.get('evidence', '')) + '</p><p>Building-label reviewer (not image reviewer): ' +
            esc(label.get('reviewer', '')) + '</p></article>')
    metadata = {
        'schema': SCHEMA,
        'input_sha256': {'manifest': sha256(manifest_path),
                         'reviewed_labels': sha256(reviewed_labels_path)},
        'building_ids': sorted(selected),
        'cohort': [{field: row[field] for field in IMMUTABLE} for row in rows],
        'limitations': LIMITATIONS,
    }
    # Complete all source reads and validation before creating output.
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    with (out_dir / 'reviews.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / 'contact-sheet.html').write_text(
        '<!doctype html><meta charset="utf-8"><title>Image applicability review</title>'
        '<h1>Human image applicability review</h1><p>Edit reviews.csv, not immutable columns. '
        'Inspect each linked image: does this photograph visibly support the source building '
        'and construction phase? No decision has been inferred from its building label.</p>'
        '<p>Image applicability reviewer is recorded separately in the CSV. Allowed decisions: ' +
        ', '.join(APPLICABILITY) + '.</p><p>' + html.escape(LIMITATIONS) + '</p>' + ''.join(cards),
        encoding='utf-8')
    return {'prepared_images': len(rows), 'prepared_buildings': len({r['building_id'] for r in rows}),
            'limitations': LIMITATIONS}


def eligible_image_keys(review_dir, manifest_path, reviewed_labels_path,
                        manifest_rows, reviewed_map) -> tuple[set[str], dict]:
    """Return (eligible building_id/filename keys, counts/limitations report).

    Pass typed manifest rows with current _sha256 from data_integrity, or _path
    for a fresh fallback hash. Cached hashes must have been recomputed this run.
    Pass the full labels_only=True map; this function verifies it against disk.
    Missing CSV rows are unreviewed, not an error. Extra/duplicate rows fail closed.
    """
    review_dir = Path(review_dir)
    metadata = json.loads((review_dir / 'metadata.json').read_text(encoding='utf-8'))
    if metadata.get('schema') != SCHEMA:
        raise ValueError('unknown image review metadata schema')
    expected_pins = {'manifest': sha256(Path(manifest_path)),
                     'reviewed_labels': sha256(Path(reviewed_labels_path))}
    if metadata.get('input_sha256') != expected_pins:
        raise ValueError('image review source files changed: SHA-256 mismatch')
    reviewed, source = _labels(Path(reviewed_labels_path))
    if reviewed_map != reviewed:
        raise ValueError('reviewed_map differs from current labels_only source labels')
    current = {}
    for row in manifest_rows:
        key = image_key(row)
        if key in current:
            raise ValueError(f'duplicate manifest image ID: {key}')
        current[key] = row
    selection = metadata.get('building_ids')
    if (not isinstance(selection, list) or any(not isinstance(bid, str) for bid in selection)
            or len(set(selection)) != len(selection) or not set(selection) <= set(reviewed)):
        raise ValueError('invalid prepared building selection')
    cohort = {}
    for immutable in metadata['cohort']:
        key = image_key(immutable)
        if key in cohort:
            raise ValueError(f'duplicate prepared image ID: {key}')
        row = current.get(key)
        if (row is None or row['building_id'] not in reviewed or
                row['building_id'] not in metadata['building_ids'] or
                row.get('drawing_flag') is not False):
            raise ValueError(f'prepared image no longer a reviewed non-drawing: {key}')
        if immutable != _snapshot(row, reviewed, source):
            raise ValueError(f'prepared immutable image/era/phase changed: {key}')
        cohort[key] = immutable
    expected_cohort = {key for key, row in current.items()
                       if row['building_id'] in selection and row.get('drawing_flag') is False}
    if set(cohort) != expected_cohort:
        raise ValueError('prepared cohort differs from pinned manifest selection')
    eligible, seen, counts = set(), set(), Counter()
    for row in _csv(review_dir / 'reviews.csv', FIELDS):
        key = image_key(row)
        if key in seen:
            raise ValueError(f'duplicate image review ID: {key}')
        seen.add(key)
        if key not in cohort:
            raise ValueError(f'extra image review outside prepared cohort: {key}')
        if {field: row[field] for field in IMMUTABLE} != cohort[key]:
            raise ValueError(f'immutable image review fields changed: {key}')
        decision = row['applicability']
        if decision not in ('',) + APPLICABILITY:
            raise ValueError(f'invalid applicability for {key}: {decision!r}')
        counts[decision or 'blank'] += 1
        if decision != 'applicable':
            continue
        if any(not row[field].strip() for field in ('observation', 'reviewer', 'reviewed_at')):
            raise ValueError(f'incomplete positive image review metadata: {key}')
        if row['confidence'] not in ('low', 'medium', 'high'):
            raise ValueError(f'invalid confidence for applicable image: {key}')
        try:
            datetime.fromisoformat(row['reviewed_at'].replace('Z', '+00:00'))
        except ValueError as exc:
            raise ValueError(f'invalid reviewed_at for applicable image: {key}') from exc
        eligible.add(key)
    missing = len(cohort) - len(seen)
    return eligible, {
        'prepared_images': len(cohort), 'review_rows': len(seen),
        'eligible_images': len(eligible), 'excluded_images': len(cohort) - len(eligible),
        'missing_reviews': missing, 'unreviewed_images': missing + counts['blank'],
        'by_applicability': {key: counts[key] for key in ('blank',) + APPLICABILITY},
        'limitations': LIMITATIONS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    for name in ('manifest', 'reviewed-labels', 'image-root', 'out-dir'):
        prep.add_argument('--' + name, type=Path, required=True)
    prep.add_argument('--building-ids', nargs='+', help='bounded IDs (space or comma separated)')
    args = parser.parse_args()
    ids = ([bid for value in args.building_ids for bid in value.split(',')]
           if args.building_ids is not None else None)
    try:
        report = prepare(args.manifest, args.reviewed_labels, args.image_root, args.out_dir, ids)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
