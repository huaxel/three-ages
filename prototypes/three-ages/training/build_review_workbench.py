#!/usr/bin/env python3
"""Build a NEW offline browser workbench without modifying evidence or reviews.

The page captures drafts/downloads only. Returned CSVs still need the canonical
Python validators; browser state is not image identity or training approval.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from data_integrity import sha256
import construction_image_reviews as construction
import validate_pair_audit as pairs
from prepare_pair_audit import FIELDS as PAIR_FIELDS
from epoch_data import load_manifest, load_reviewed_labels

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def _read_csv(path, fields):
    with Path(path).open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle, strict=True)
        if (not reader.fieldnames or len(reader.fieldnames) != len(fields)
                or set(reader.fieldnames) != set(fields)):
            raise ValueError('workbench requires exactly the canonical review columns')
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError('malformed review CSV')
    return rows


def _preflight_manifest(path, root):
    root = Path(root).resolve()
    with Path(path).open(newline='', encoding='utf-8') as handle:
        for row in csv.DictReader(handle, strict=True):
            construction.image_key(row)
            if not (root/row['building_id']/row['filename']).resolve().is_relative_to(root):
                raise ValueError('manifest image escapes configured root')


def _image(root, bid, filename, expected_sha, output, caption):
    for value in (bid, filename):
        if not value or value in ('.', '..') or '/' in value or '\\' in value:
            raise ValueError('image IDs must be plain path components')
    root = Path(root).resolve()
    path = (root / bid / filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError('image escapes configured root')
    if sha256(path) != expected_sha:
        raise ValueError(f'image bytes changed: {bid}/{filename}')
    # Relative, URL-encoded paths work as file pages and under an HTTP root.
    src = quote(Path(os.path.relpath(path, Path(output).parent.resolve())).as_posix(), safe='/')
    return {'src': src, 'caption': caption}


def _json_for_html(value):
    # HTML parses closing script tags even in application/json elements.
    return (json.dumps(value, ensure_ascii=True)
            .replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026'))


def build(kind, audit_dir, output, publisher_manifest, mapillary_manifest,
          publisher_root, mapillary_root, reviewed_labels):
    audit_dir, output = Path(audit_dir), Path(output)
    publisher_manifest, mapillary_manifest = Path(publisher_manifest), Path(mapillary_manifest)
    reviewed_labels = Path(reviewed_labels)
    if output.exists() or output.is_symlink():
        raise ValueError('output exists; refusing to replace any file')
    if not output.parent.is_dir():
        raise ValueError('output parent directory must already exist')
    if kind not in ('pair', 'construction'):
        raise ValueError('unknown workbench kind')
    metadata_path = audit_dir / ('sample.json' if kind == 'pair' else 'metadata.json')
    reviews_path = audit_dir/'reviews.csv'
    inputs = {'metadata': metadata_path, 'reviews': reviews_path,
              'publisher_manifest': publisher_manifest}
    if kind == 'pair':
        inputs['mapillary_manifest'] = mapillary_manifest
    else:
        inputs['reviewed_labels'] = reviewed_labels
    pins = {key: sha256(path) for key, path in inputs.items()}
    records = []
    _preflight_manifest(publisher_manifest, publisher_root)
    if kind == 'pair':
        _preflight_manifest(mapillary_manifest, mapillary_root)
        # Reconstruct and verify the actual sampled pairs, source hashes, review
        # metadata and exact sampled bytes before displaying them.
        pairs.validate(metadata_path, reviews_path, publisher_manifest, mapillary_manifest,
                       Path(publisher_root), Path(mapillary_root))
        fields, editable = list(PAIR_FIELDS), list(pairs.REVIEW_FIELDS)
        decision_field, decisions = 'identity', list(pairs.IDENTITIES)
        for row in _read_csv(reviews_path, fields):
            bid = row['building_id']
            records.append({'key': row['pair_id'], 'values': row,
                            'images': [
                                _image(mapillary_root, bid, row['mapillary_filename'], row['mapillary_sha256'], output, 'Mapillary frame'),
                                _image(publisher_root, bid, row['publisher_filename'], row['publisher_sha256'], output, 'Publisher view')],
                            'context': [{'label': 'Assigned building', 'value': bid},
                                        {'label': 'Mapillary source ID', 'value': row['mapillary_source_id']}]})
    else:
        fields, editable = list(construction.FIELDS), list(construction.EDITABLE)
        decision_field, decisions = 'applicability', list(construction.APPLICABILITY)
        manifest_rows = load_manifest(publisher_manifest)
        for row in manifest_rows:
            row['_path'] = Path(publisher_root)/row['building_id']/row['filename']
        reviewed = load_reviewed_labels(reviewed_labels, labels_only=True)
        construction.eligible_image_keys(audit_dir, publisher_manifest, reviewed_labels,
                                         manifest_rows, reviewed)
        baseline_rows = _read_csv(reviews_path, fields)
        by_key = {construction.image_key(row): row for row in baseline_rows}
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        with reviewed_labels.open(newline='', encoding='utf-8') as handle:
            labels = {row['building_id'].strip(): row for row in csv.DictReader(handle)}
        for immutable in metadata['cohort']:
            key = construction.image_key(immutable)
            # Canonical eligibility treats omitted rows as pending. A page may
            # display them, but never invent an applicability decision.
            row = by_key.get(key, {**immutable, **dict.fromkeys(editable, '')})
            bid = row['building_id']
            source = labels[bid]
            records.append({'key': key, 'values': row,
                            'images': [_image(publisher_root, bid, row['filename'], row['image_sha256'], output, key)],
                            'context': [
                                {'label': 'Source construction era', 'value': row['construction_era']},
                                {'label': 'Source campaign years', 'value': row['phase_years']},
                                {'label': 'Source evidence (not an image decision)', 'value': source.get('evidence', '')},
                                {'label': 'Building-label reviewer (not image reviewer)', 'value': source.get('reviewer', '')}]})
    if not records:
        raise ValueError('no prepared review rows')
    immutable_fields = [field for field in fields if field not in editable]
    identity = {'schema': 'image-review-workbench/1', 'kind': kind,
                'metadata_sha256': pins['metadata'],
                'immutable': sorted(
                    [{'key': r['key'], 'fields': {f: r['values'][f] for f in immutable_fields}}
                     for r in records], key=lambda r: r['key'])}
    cohort = hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
    bundle = {'schema': 'image-review-workbench/1', 'kind': kind,
              'cohort_id': cohort, 'baseline_sha256': pins['reviews'],
              'fields': fields, 'editable': editable, 'decision_field': decision_field,
              'decisions': decisions, 'rows': records, 'source_pins': pins}
    template = (HERE/'review_workbench.html').read_text(encoding='utf-8')
    scripts = {name: (HERE/filename).read_text(encoding='utf-8') for name, filename in
               [('__REVIEW_MODEL__', 'review_workbench_model.js'),
                ('__REVIEW_UI__', 'review_workbench_ui.js')]}
    if any('</script' in script.lower() for script in scripts.values()):
        raise ValueError('embedded script contains an HTML closing tag')
    replacements = {**scripts, '__REVIEW_DATA__': _json_for_html(bundle)}
    if any(template.count(token) != 1 for token in replacements):
        raise ValueError('workbench template must contain each placeholder once')
    # One pass: data containing placeholder-looking text is never substituted.
    document = re.sub(r'__REVIEW_(?:DATA|MODEL|UI)__', lambda match: replacements[match[0]], template)
    if pins != {key: sha256(path) for key, path in inputs.items()}:
        raise ValueError('source files changed while building the workbench')
    with output.open('x', encoding='utf-8') as handle:
        handle.write(document)
    return {'output': str(output), 'kind': kind, 'rows': len(records),
            'cohort_id': cohort, 'baseline_sha256': pins['reviews'],
            'source_files_modified': False,
            'limitations': 'Browser drafts/downloads only; canonical validators still required; no identity or training approval implied'}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--kind', choices=('pair', 'construction'), required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    parser.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    parser.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    parser.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    parser.add_argument('--reviewed-labels', type=Path, default=REPO/'local/training/reviewed_construction_eras.csv')
    args = parser.parse_args()
    try:
        report = build(args.kind, args.audit_dir, args.out, args.publisher_manifest,
                       args.mapillary_manifest, args.publisher_root, args.mapillary_root,
                       args.reviewed_labels)
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
