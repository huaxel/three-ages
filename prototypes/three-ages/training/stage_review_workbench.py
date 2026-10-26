#!/usr/bin/env python3
"""Validate a returned review CSV and stage a NEW cohort; never modify originals."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path

from build_review_workbench import _preflight_manifest, _read_csv
from data_integrity import sha256
import construction_image_reviews as construction
import validate_pair_audit as pairs
from prepare_pair_audit import FIELDS as PAIR_FIELDS
from epoch_data import load_manifest, load_reviewed_labels

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def stage(kind, audit_dir, returned_reviews, output_dir, publisher_manifest,
          mapillary_manifest, publisher_root, mapillary_root, reviewed_labels):
    audit_dir, returned_reviews, output_dir = map(Path, (audit_dir, returned_reviews, output_dir))
    publisher_manifest, mapillary_manifest, reviewed_labels = map(
        Path, (publisher_manifest, mapillary_manifest, reviewed_labels))
    if kind not in ('pair', 'construction'):
        raise ValueError('unknown review kind')
    if output_dir.exists() or output_dir.is_symlink():
        raise ValueError('output directory exists; refusing to replace any artifacts')
    if not output_dir.parent.is_dir():
        raise ValueError('output parent directory must already exist')
    name = 'sample.json' if kind == 'pair' else 'metadata.json'
    inputs = {'metadata': audit_dir/name, 'baseline_reviews': audit_dir/'reviews.csv',
              'returned_reviews': returned_reviews, 'publisher_manifest': publisher_manifest}
    inputs['mapillary_manifest' if kind == 'pair' else 'reviewed_labels'] = (
        mapillary_manifest if kind == 'pair' else reviewed_labels)
    pins = {key: sha256(path) for key, path in inputs.items()}
    metadata_bytes = (audit_dir/name).read_bytes()
    returned_bytes = returned_reviews.read_bytes()
    if (hashlib.sha256(metadata_bytes).hexdigest() != pins['metadata'] or
            hashlib.sha256(returned_bytes).hexdigest() != pins['returned_reviews']):
        raise ValueError('review inputs changed while reading snapshots')
    fields = list(PAIR_FIELDS) if kind == 'pair' else list(construction.FIELDS)
    editable = pairs.REVIEW_FIELDS if kind == 'pair' else construction.EDITABLE
    key_of = (lambda row: row['pair_id']) if kind == 'pair' else construction.image_key
    baseline = _read_csv(audit_dir/'reviews.csv', fields)
    returned = _read_csv(returned_reviews, fields)
    by_key = {}
    for row in returned:
        key = key_of(row)
        if key in by_key:
            raise ValueError(f'duplicate returned review key: {key}')
        by_key[key] = row
    # A stale page must never erase or overwrite work entered since it was built.
    for row in baseline:
        if any(row[field].strip() for field in editable):
            if by_key.get(key_of(row)) != row:
                raise ValueError('returned CSV modifies or removes an existing source review')
    _preflight_manifest(publisher_manifest, publisher_root)
    if kind == 'pair':
        _preflight_manifest(mapillary_manifest, mapillary_root)
        # Validate baseline as well as return; corrupt originals cannot silently
        # become the basis of a new review branch.
        pairs.validate(audit_dir/name, audit_dir/'reviews.csv', publisher_manifest,
                       mapillary_manifest, Path(publisher_root), Path(mapillary_root))
        report = pairs.validate(audit_dir/name, returned_reviews, publisher_manifest,
                                mapillary_manifest, Path(publisher_root), Path(mapillary_root))
    else:
        rows = load_manifest(publisher_manifest)
        for row in rows:
            row['_path'] = Path(publisher_root)/row['building_id']/row['filename']
        reviewed = load_reviewed_labels(reviewed_labels, labels_only=True)
        construction.eligible_image_keys(audit_dir, publisher_manifest, reviewed_labels, rows, reviewed)
        # Canonical construction validation uses a directory. This private test
        # staging area is not a source replacement and is removed after checking.
        with tempfile.TemporaryDirectory(prefix='construction-review-check-') as directory:
            temporary = Path(directory)
            (temporary/name).write_bytes(metadata_bytes)
            (temporary/'reviews.csv').write_bytes(returned_bytes)
            _, report = construction.eligible_image_keys(
                temporary, publisher_manifest, reviewed_labels, rows, reviewed)
    if pins != {key: sha256(path) for key, path in inputs.items()}:
        raise ValueError('source files changed during return validation')
    # All validation occurs before any destination is created. A disk error may
    # leave a partial NEW directory, but never replaces a source or prior result.
    output_dir.mkdir(exist_ok=False)
    (output_dir/name).write_bytes(metadata_bytes)
    (output_dir/'reviews.csv').write_bytes(returned_bytes)
    result = {'schema': 'review-workbench-stage/1', 'kind': kind,
              'input_sha256': pins, 'validation': report,
              'source_files_modified': False,
              'limitations': 'Metadata/byte checks and human attestations only; no model fitting or training approval'}
    (output_dir/'validation.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return {'output_dir': str(output_dir), 'kind': kind, 'source_files_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--kind', choices=('pair', 'construction'), required=True)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    parser.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    parser.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    parser.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    parser.add_argument('--reviewed-labels', type=Path, default=REPO/'local/training/reviewed_construction_eras.csv')
    args = parser.parse_args()
    try:
        result = stage(args.kind, args.audit_dir, args.reviews, args.out_dir,
                       args.publisher_manifest, args.mapillary_manifest,
                       args.publisher_root, args.mapillary_root, args.reviewed_labels)
    except (ValueError, OSError, KeyError, TypeError, csv.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
