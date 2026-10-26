#!/usr/bin/env python3
"""Read-only near-image/acquisition diagnostics, never automatic deduplication.

Exact decoded pixels and a perceptual hash flag dependencies/review candidates,
not building identity. Missing metadata, unreadable images, budgets and low-detail
fingerprints are explicit; zero candidates never proves isolation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import struct
import warnings

from PIL import Image, ImageOps, features, __version__ as PILLOW_VERSION
from data_integrity import load, sha256

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
FINGERPRINT_FIELDS = ['id', 'pole', 'building_id', 'filename', 'split', 'file_sha256',
                      'decoded_sha256', 'model_rgb_sha256', 'raw_width', 'raw_height', 'width', 'height', 'dhash64', 'near_eligible',
                      'status', 'error_type']
ALGORITHM = 'exif-rgba8-dhash9x8-white-thumbnail-lanczos/1'


def safe_path(root, bid, filename):
    for value in (bid, filename):
        if not value or value in ('.', '..') or '/' in value or '\\' in value:
            raise ValueError('image IDs must be plain path components')
    root = Path(root).resolve()
    path = (root/bid/filename).resolve()
    if not path.is_relative_to(root):
        raise ValueError('image escapes configured root')
    return path


def _decode_budget(max_pixels, max_bytes):
    if type(max_pixels) is not int or max_pixels < 1 or type(max_bytes) is not int or max_bytes < 1:
        raise ValueError('positive integer decode budgets required')


def _search_budget(radius, max_visits, max_candidates):
    if type(radius) is not int or not 0 <= radius <= 4:
        raise ValueError('radius must be an integer from zero through four')
    if type(max_visits) is not int or max_visits < 1 or type(max_candidates) is not int or max_candidates < 1:
        raise ValueError('positive integer candidate budgets required')


def fingerprint(row, *, max_pixels=25_000_000, max_bytes=256*1024*1024):
    """Hash the same read buffer decoded; bounded RGBA, no multi-frame shortcut."""
    _decode_budget(max_pixels, max_bytes)
    result = dict.fromkeys(FINGERPRINT_FIELDS, '')
    result.update(id=row['_id'], pole=row['_pole'], building_id=row['building_id'],
                  filename=row['filename'], split=row['split'], near_eligible='0')
    try:
        path = Path(row['_path'])
        if path.stat().st_size > max_bytes:
            result['status'] = 'byte_limit'
            return result
        with path.open('rb') as handle:
            raw = handle.read(max_bytes + 1)
        if len(raw) > max_bytes:
            result['status'] = 'byte_limit'
            return result
        result['file_sha256'] = hashlib.sha256(raw).hexdigest()
    except OSError as exc:
        result.update(status='read_error', error_type=type(exc).__name__)
        return result
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                result.update(raw_width=image.width, raw_height=image.height)
                if getattr(image, 'n_frames', 1) != 1:
                    result['status'] = 'unsupported_multiframe'
                    return result
                if image.width * image.height > max_pixels:
                    result['status'] = 'pixel_limit'
                    return result
                # Canonical build_embeddings.py currently converts raw decoder
                # pixels to RGB without EXIF transpose or alpha compositing.
                # Keep this equivalence separate from display-normalized RGBA.
                rgb = image.convert('RGB')
                model_digest = hashlib.sha256(b'RAW-RGB8/1\0'+struct.pack('!II', *rgb.size))
                model_digest.update(rgb.tobytes())
                result['model_rgb_sha256'] = model_digest.hexdigest()
                del rgb
                rgba = ImageOps.exif_transpose(image).convert('RGBA')
                rgba.load()
                width, height = rgba.size
                digest = hashlib.sha256(b'EXIF-RGBA8/1\0'+struct.pack('!II', width, height))
                digest.update(rgba.tobytes())
                thumbnail = rgba.resize((9, 8), Image.Resampling.LANCZOS)
                white = Image.new('RGBA', (9, 8), (255, 255, 255, 255))
                white.alpha_composite(thumbnail)
                values = white.convert('L').tobytes()
                bits = 0
                for y in range(8):
                    for x in range(8):
                        bits = (bits << 1) | int(values[y*9+x] > values[y*9+x+1])
                # Flat/monotonic fingerprints create enormous ambiguous buckets.
                # They still participate in exact decoded-pixel grouping.
                informative = max(values)-min(values) >= 16 and 4 <= bits.bit_count() <= 60
                result.update(decoded_sha256=digest.hexdigest(), width=width, height=height,
                              dhash64=f'{bits:016x}', near_eligible='1' if informative else '0', status='ok')
    except (OSError, ValueError, SyntaxError, EOFError, struct.error, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        result.update(status='decode_error', error_type=type(exc).__name__)
    return result


def decoded_groups(records, field='decoded_sha256'):
    groups = defaultdict(list)
    for row in records:
        if row['status'] == 'ok':
            groups[row[field]].append(row)
    return [{field: digest,
             'ids': [r['id'] for r in rows],
             'splits': sorted({r['split'] for r in rows}),
             'buildings': sorted({r['building_id'] for r in rows}),
             'cross_split': len({r['split'] for r in rows}) > 1}
            for digest, rows in sorted(groups.items()) if len(rows) > 1]


def near_candidates(records, *, radius=4, max_visits=10_000_000, max_candidates=1000):
    """Pigeonhole hash index: radius+1 disjoint bands, bounded bucket visits.

    For informative 64-bit hashes, every pair within radius shares a band.
    This says nothing about crop/rotation/visual/identity recall of dHash itself.
    """
    _search_budget(radius, max_visits, max_candidates)
    usable = sorted((r for r in records if r['status'] == 'ok' and r['near_eligible'] == '1'), key=lambda r: r['id'])
    bands = radius + 1
    widths = [64//bands + int(i < 64 % bands) for i in range(bands)]
    index = defaultdict(list)
    retained, matches, visits, comparisons, truncated = [], 0, 0, 0, False
    for i, row in enumerate(usable):
        bits, shift, keys = int(row['dhash64'], 16), 0, []
        for band, width in enumerate(widths):
            keys.append((band, (bits >> shift) & ((1 << width)-1)))
            shift += width
        seen = set()
        for key in keys:
            for j in index[key]:
                if visits >= max_visits:
                    truncated = True
                    break
                visits += 1
                if j in seen:
                    continue
                seen.add(j)
                other = usable[j]
                if other['split'] == row['split'] or other['decoded_sha256'] == row['decoded_sha256']:
                    continue
                comparisons += 1
                distance = (bits ^ int(other['dhash64'], 16)).bit_count()
                if distance <= radius:
                    matches += 1
                    if len(retained) < max_candidates:
                        retained.append({'left': other['id'], 'right': row['id'], 'hamming_distance': distance,
                                         'meaning': 'perceptual candidate only; no identity or duplicate decision'})
            if truncated:
                break
        if truncated:
            break
        for key in keys:
            index[key].append(i)
    return {'eligible_images': len(usable), 'bucket_visits': visits,
            'distance_comparisons': comparisons, 'candidate_matches_observed': matches,
            'retained_pairs': len(retained), 'candidate_list_truncated': matches > len(retained),
            'comparison_budget_exhausted': truncated,
            'hash_pair_search_complete_for_eligible_images': not truncated,
            'candidates': retained,
            'selection': 'deterministic ID order; retained list is not a random audit sample'}


def audit(pub, mmap, *, limit_per_pole=None, radius=4, max_visits=10_000_000,
          max_candidates=1000, max_pixels=25_000_000, max_bytes=256*1024*1024):
    from sequence_metadata import sequence_groups
    if limit_per_pole is not None and (type(limit_per_pole) is not int or limit_per_pole < 1):
        raise ValueError('limit per pole must be positive')
    _decode_budget(max_pixels, max_bytes)
    _search_budget(radius, max_visits, max_candidates)
    all_rows = pub + mmap
    memberships = defaultdict(set)
    for row in all_rows:
        memberships[row['building_id']].add(row['split'])
    split_conflicts = [{'building_id': bid, 'splits': sorted(splits)}
                       for bid, splits in sorted(memberships.items()) if len(splits) > 1]
    # Sequence evidence is cheap metadata and always covers the full supplied
    # Mapillary manifest, not just the optional image smoke-test subset.
    sequences = sequence_groups([dict(row) for row in mmap])
    selected = []
    for pole, rows in [('pub', pub), ('map', mmap)]:
        ordered = sorted(rows, key=lambda r: r['_id'])
        chosen = ordered if limit_per_pole is None else ordered[:limit_per_pole]
        selected.extend(dict(row, _pole=pole) for row in chosen)
    records = [fingerprint(row, max_pixels=max_pixels, max_bytes=max_bytes) for row in selected]
    groups = decoded_groups(records)
    model_groups = decoded_groups(records, field='model_rgb_sha256')
    near = near_candidates(records, radius=radius, max_visits=max_visits, max_candidates=max_candidates)
    states = Counter(r['status'] for r in records)
    ok = states['ok']
    return {'schema': 'near-image-audit/1', 'algorithm': ALGORITHM,
            'role': 'read-only dependency/candidate diagnostic; not verified labels or automatic quarantine',
            'overall_isolation': 'not established by this diagnostic',
            'scope': {'input_rows': len(all_rows), 'selected_image_rows': len(selected),
                      'limit_per_pole': limit_per_pole,
                      'selection': 'all supplied IDs sorted within each pole' if len(selected) == len(all_rows) else 'first sorted IDs per pole; biased smoke subset only',
                      'complete_image_decode_scan': len(selected) == len(all_rows) and ok == len(selected)},
            'decode_status': dict(sorted(states.items())),
            'building_split_conflicts': split_conflicts,
            'low_information_images_not_perceptually_compared': sum(r['status']=='ok' and r['near_eligible']=='0' for r in records),
            'decoded_pixel_groups': groups,
            'decoded_cross_split_groups': sum(g['cross_split'] for g in groups),
            'model_rgb_groups': model_groups,
            'model_rgb_cross_split_groups': sum(g['cross_split'] for g in model_groups),
            'near': near, 'sequence_evidence': sequences,
            'parameters': {'radius': radius, 'max_bucket_visits': max_visits, 'max_retained_candidates': max_candidates,
                           'max_pixels': max_pixels, 'max_bytes': max_bytes,
                           'decoded_format': 'EXIF-normalized RGBA8 including dimensions; single-frame only',
                           'model_pixel_format': 'raw audit-decoder RGB8 plus dimensions, no EXIF transpose or alpha composite; matches current encoder conversion semantics, not cached-feature attestation',
                           'thumbnail': '9x8 RGBA Lanczos, white alpha composite, grayscale horizontal differences',
                           'low_information_rule': 'thumbnail range <16 or hash population outside 4..60'},
            'toolchain': {'Pillow': PILLOW_VERSION,
                          'codecs': {name: features.version(name) for name in ('jpg', 'zlib', 'libtiff', 'webp')}},
            'limitations': ['Pixel equivalence is decoder/build-specific; reconfirm encoder toolchain/preprocessing before enforcing model dependency groups.',
                           'Perceptual collisions can join unrelated pictures; never merge buildings from these candidates.',
                           'Crops, rotations and edits may be missed; dHash radius is not calibrated identity evidence.',
                           'Low-detail, failed, over-budget and multi-frame inputs are not a clean bill of health.',
                           'Candidate budgets/truncated lists and smoke subsets do not establish full-corpus absence.',
                           'Sequence IDs must be explicit; photographer/time/location are not substitute sequence labels.',
                           'No images, manifests, splits, human reviews, model weights or source labels are modified.']}, records


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--publisher-manifest', type=Path, default=REPO/'local/training/manifest.csv')
    parser.add_argument('--mapillary-manifest', type=Path, default=REPO/'local/training/mapillary_manifest.csv')
    parser.add_argument('--publisher-root', type=Path, default=REPO/'local/monument-inbox')
    parser.add_argument('--mapillary-root', type=Path, default=REPO/'local/mapillary-inbox')
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--limit-per-pole', type=int)
    parser.add_argument('--radius', type=int, default=4)
    parser.add_argument('--max-bucket-visits', type=int, default=10_000_000)
    parser.add_argument('--max-candidates', type=int, default=1000)
    parser.add_argument('--max-pixels', type=int, default=25_000_000)
    parser.add_argument('--max-bytes', type=int, default=256*1024*1024)
    args = parser.parse_args()
    if args.out_dir.exists() or args.out_dir.is_symlink():
        parser.error('output directory exists; refusing to replace any artifact')
    try:
        pins = {'publisher_manifest': sha256(args.publisher_manifest),
                'mapillary_manifest': sha256(args.mapillary_manifest)}
        pub, _ = load(args.publisher_manifest, args.publisher_root, 'pub')
        mmap, _ = load(args.mapillary_manifest, args.mapillary_root, 'map')
        for pole, rows, root in [('pub', pub, args.publisher_root), ('map', mmap, args.mapillary_root)]:
            for row in rows:
                row['_pole'] = pole
                row['_path'] = safe_path(root, row['building_id'], row['filename'])
        report, records = audit(pub, mmap, limit_per_pole=args.limit_per_pole, radius=args.radius,
                                max_visits=args.max_bucket_visits, max_candidates=args.max_candidates,
                                max_pixels=args.max_pixels, max_bytes=args.max_bytes)
        if pins != {'publisher_manifest': sha256(args.publisher_manifest),
                    'mapillary_manifest': sha256(args.mapillary_manifest)}:
            raise ValueError('input manifests changed during the scan')
        report['input_sha256'] = pins
        report['implementation_sha256'] = {'audit': sha256(Path(__file__)),
                                           'sequence_metadata': sha256(HERE/'sequence_metadata.py'),
                                           'manifest_loader': sha256(HERE/'data_integrity.py'),
                                           'encoder_reference': sha256(HERE.parent/'build_embeddings.py')}
    except (ValueError, OSError, KeyError, csv.Error) as exc:
        parser.error(str(exc))
    args.out_dir.mkdir(parents=True, exist_ok=False)
    with (args.out_dir/'fingerprints.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=FINGERPRINT_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    (args.out_dir/'audit.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    summary = {key: value for key, value in report.items()
               if key not in ('decoded_pixel_groups', 'model_rgb_groups', 'near', 'sequence_evidence')}
    summary['near_summary'] = {key: value for key, value in report['near'].items() if key != 'candidates'}
    summary['sequence_status'] = report['sequence_evidence']['status']
    print(json.dumps(summary, indent=2))
    print('Diagnostic candidates only; no source data, splits or labels changed')


if __name__ == '__main__':
    main()
