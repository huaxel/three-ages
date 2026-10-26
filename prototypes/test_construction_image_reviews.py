#!/usr/bin/env python3
"""Standard-library, fixture-only image applicability review regression tests."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TRAINING = Path(__file__).with_name('three-ages') / 'training'
sys.path.insert(0, str(TRAINING))
import construction_image_reviews as reviews
from epoch_data import load_manifest, load_reviewed_labels
from data_integrity import sha256


def write_csv(path, rows, fields=None):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as handle:
        return list(csv.DictReader(handle))


class ConstructionImageReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = self.root / 'manifest.csv'
        self.labels = self.root / 'labels.csv'
        self.images = self.root / 'images'
        self.out = self.root / 'review'
        self.raw = []
        for bid in ('7', '8', '9'):
            (self.images / bid).mkdir(parents=True)
            for i in range(8):
                filename = f'{i}.jpg'
                (self.images / bid / filename).write_bytes(f'{bid} image {i}'.encode())
                self.raw.append(dict(building_id=bid, filename=filename,
                                     drawing_flag='1' if i == 7 else '0', split='train'))
        write_csv(self.manifest, self.raw)
        write_csv(self.labels, [dict(
            building_id=bid, construction_era='1850-1892', phase_years='1882',
            evidence='<human evidence>', reviewer='Building reviewer',
            reviewed_at='2026-10-24', confidence='high', depicts_building='no',
        ) for bid in ('7', '8')])
        self.prepare()

    def prepare(self, ids=None, out=None):
        return reviews.prepare(self.manifest, self.labels, self.images, out or self.out, ids)

    def check(self, hashed=False):
        rows = load_manifest(self.manifest)
        for row in rows:
            row['_path'] = self.images / row['building_id'] / row['filename']
            if hashed:
                row['_sha256'] = sha256(row['_path'])
        return reviews.eligible_image_keys(
            self.out, self.manifest, self.labels, rows,
            load_reviewed_labels(self.labels, labels_only=True))

    def edited(self, updates=None):
        rows = read_csv(self.out / 'reviews.csv')
        if updates:
            rows[0].update(updates)
        write_csv(self.out / 'reviews.csv', rows, reviews.FIELDS)
        return rows

    def positive(self):
        self.edited(dict(applicability='applicable', observation='Matching whole facade and phase',
                         reviewer='Image reviewer', reviewed_at='2026-10-25T12:00:00Z', confidence='high'))

    def test_contact_sheet_uses_relative_encoded_urls(self):
        filename = 'one #?%.jpg'
        (self.images/'7'/filename).write_bytes(b'unusual filename image')
        self.raw[0]['filename'] = filename
        write_csv(self.manifest, self.raw)
        fresh = self.root/'url-review'
        self.prepare(ids=['7'], out=fresh)
        sheet = (fresh/'contact-sheet.html').read_text()
        self.assertNotIn('file://', sheet)
        self.assertNotIn(str(self.images), sheet)
        self.assertIn('../images/7/one%20%23%3F%25.jpg', sheet)
        self.assertEqual(read_csv(fresh/'reviews.csv')[0]['filename'], filename)

    def test_blank_defaults_and_building_wide_no_not_substituted(self):
        rows = read_csv(self.out / 'reviews.csv')
        self.assertEqual(len(rows), 14)
        self.assertEqual({r['building_id'] for r in rows}, {'7', '8'})
        self.assertTrue(all(all(r[field] == '' for field in reviews.EDITABLE) for r in rows))
        keys, report = self.check()
        self.assertEqual(keys, set())
        self.assertEqual(report['unreviewed_images'], 14)
        self.positive()
        self.assertEqual(self.check()[0], {'7/0.jpg'})
        self.assertEqual(self.check(hashed=True)[0], {'7/0.jpg'})

    def test_explicit_negative_unknown_blank_and_missing(self):
        rows = read_csv(self.out / 'reviews.csv')[:7]
        decisions = ['applicable', 'wrong_subject', 'predecessor', 'interior_or_detail',
                     'not_visually_inferable', 'unknown', '']
        for row, decision in zip(rows, decisions):
            row.update(applicability=decision, observation='Image-level observation',
                       reviewer='Visual reviewer', reviewed_at='2026-10-25', confidence='medium')
        write_csv(self.out / 'reviews.csv', rows)
        keys, report = self.check()
        self.assertEqual(keys, {'7/0.jpg'})
        self.assertEqual(report['missing_reviews'], 7)
        self.assertEqual(report['unreviewed_images'], 8)
        self.assertEqual(report['excluded_images'], 13)
        for decision in decisions[:-1]:
            self.assertEqual(report['by_applicability'][decision], 1)
        write_csv(self.out / 'reviews.csv', [], reviews.FIELDS)
        self.assertEqual(self.check()[1]['missing_reviews'], 14)

    def test_positive_review_requires_complete_metadata(self):
        for field, bad in [('observation', ''), ('reviewer', ' '), ('reviewed_at', ''),
                           ('reviewed_at', 'yesterday'), ('confidence', ''), ('confidence', 'certain')]:
            with self.subTest(field=field, bad=bad):
                self.positive()
                self.edited({field: bad})
                with self.assertRaises(ValueError):
                    self.check()
        self.edited({'applicability': 'yes'})
        with self.assertRaisesRegex(ValueError, 'invalid applicability'):
            self.check()

    def test_each_immutable_review_field_is_checked(self):
        original = (self.out / 'reviews.csv').read_bytes()
        for field, bad in [('building_id', '8'), ('filename', '1.jpg'), ('image_sha256', 'f'*64),
                           ('construction_era', 'post-1975'), ('phase_years', '1999')]:
            with self.subTest(field=field):
                (self.out / 'reviews.csv').write_bytes(original)
                self.edited({field: bad})
                with self.assertRaises(ValueError):
                    self.check()

    def test_source_files_pinned_even_semantically_identical_bytes(self):
        for path in (self.manifest, self.labels):
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original + b'\n')
                with self.assertRaisesRegex(ValueError, 'source files changed'):
                    self.check()
                path.write_bytes(original)

    def test_image_byte_changes_including_unreviewed_fail(self):
        for hashed in (False, True):
            path = self.images / '8' / '6.jpg'
            original = path.read_bytes()
            path.write_bytes(b'new pixels')
            with self.assertRaisesRegex(ValueError, 'immutable image/era/phase changed'):
                self.check(hashed=hashed)
            path.write_bytes(original)

    def test_metadata_era_phase_and_hash_tamper_rejected(self):
        path = self.out / 'metadata.json'
        original = path.read_text()
        for field in ('construction_era', 'phase_years', 'image_sha256'):
            metadata = json.loads(original)
            metadata['cohort'][0][field] = 'tampered'
            path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'immutable image/era/phase changed'):
                self.check()
        path.write_text(original)

    def test_duplicate_and_extra_reviews(self):
        original = read_csv(self.out / 'reviews.csv')
        for extra in [original[0], {**original[0], 'filename': '7.jpg'},
                      {**original[0], 'building_id': '9'}]:
            with self.subTest(extra=extra):
                write_csv(self.out / 'reviews.csv', original + [extra])
                with self.assertRaisesRegex(ValueError, 'duplicate|extra'):
                    self.check()

    def test_bounded_cohort_refuses_unsolicited_valid_image(self):
        bounded = self.root / 'bounded'
        self.prepare(['7'], bounded)
        rows = read_csv(bounded / 'reviews.csv')
        rows.append(read_csv(self.out / 'reviews.csv')[-1])
        write_csv(bounded / 'reviews.csv', rows)
        self.out = bounded
        with self.assertRaisesRegex(ValueError, 'extra image review'):
            self.check()
        with self.assertRaisesRegex(ValueError, 'human-reviewed'):
            self.prepare(['9'], self.root / 'bad')
        self.assertFalse((self.root / 'bad').exists())

    def test_prepare_no_clobber_and_no_source_mutation(self):
        paths = [self.manifest, self.labels, *self.images.glob('*/*')]
        before = {path: path.read_bytes() for path in paths}
        new = self.root / 'fresh'
        self.prepare(out=new)
        outputs = {path: path.read_bytes() for path in new.iterdir()}
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.prepare(out=new)
        self.assertEqual(outputs, {path: path.read_bytes() for path in new.iterdir()})
        self.assertEqual(before, {path: path.read_bytes() for path in paths})
        sheet = (new / 'contact-sheet.html').read_text()
        self.assertIn('&lt;human evidence&gt;', sheet)
        self.assertIn('not image reviewer', sheet)
        self.assertIn('../images/7/0.jpg', sheet)
        self.assertNotIn('file://', sheet)
        self.assertIn('Image applicability reviewer', sheet)

    def test_failed_prepare_does_not_create_outputs(self):
        (self.images / '7' / '0.jpg').unlink()
        new = self.root / 'missing-image'
        with self.assertRaises(OSError):
            self.prepare(out=new)
        self.assertFalse(new.exists())

    def test_cli_bounded_prepare(self):
        out = self.root / 'cli'
        result = subprocess.run([
            sys.executable, str(TRAINING / 'construction_image_reviews.py'), 'prepare',
            '--manifest', str(self.manifest), '--reviewed-labels', str(self.labels),
            '--image-root', str(self.images), '--out-dir', str(out), '--building-ids', '7,8'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['prepared_images'], 14)
        self.assertEqual(self.check()[0], set())

    def test_prepared_cohort_tamper_and_duplicate_rejected(self):
        path = self.out / 'metadata.json'
        original = path.read_text()
        for duplicate in (False, True):
            metadata = json.loads(original)
            if duplicate:
                metadata['cohort'].append(metadata['cohort'][0])
            else:
                metadata['cohort'].pop()
            path.write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, 'duplicate|cohort differs'):
                self.check()
        path.write_text(original)

    def test_unknown_drawing_status_excluded_and_duplicate_manifest_refused(self):
        self.raw[0]['drawing_flag'] = ''
        write_csv(self.manifest, self.raw)
        new = self.root / 'unknown-drawing'
        report = self.prepare(out=new)
        self.assertEqual(report['prepared_images'], 13)
        self.assertNotIn('7/0.jpg', {reviews.image_key(r) for r in read_csv(new / 'reviews.csv')})
        write_csv(self.manifest, self.raw + [self.raw[0]])
        bad = self.root / 'duplicate-manifest'
        with self.assertRaisesRegex(ValueError, 'duplicate manifest'):
            self.prepare(out=bad)
        self.assertFalse(bad.exists())

    def test_missing_phase_column_supported(self):
        rows = read_csv(self.labels)
        for row in rows:
            del row['phase_years']
        write_csv(self.labels, rows)
        new = self.root / 'no-phase'
        self.prepare(out=new)
        self.assertEqual({r['phase_years'] for r in read_csv(new / 'reviews.csv')}, {''})


if __name__ == '__main__':
    unittest.main()
