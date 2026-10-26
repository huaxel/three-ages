#!/usr/bin/env python3
"""Synthetic Python -> browser-model CSV -> canonical-validator round trips."""
from __future__ import annotations
import csv
import hashlib
import json
import re
import struct
import subprocess
import zlib
import sys
import tempfile
import unittest
from pathlib import Path

TRAINING = Path(__file__).resolve().parent/'three-ages/training'
sys.path.insert(0, str(TRAINING))
from build_review_workbench import build
from stage_review_workbench import stage
from construction_image_reviews import prepare as prepare_images, eligible_image_keys
from epoch_data import load_manifest, load_reviewed_labels
from validate_pair_audit import validate as validate_pairs


def synthetic_png(red, green, blue):
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', zlib.crc32(kind + payload))
    pixels = (b'\x00' + bytes((red, green, blue)) * 16) * 16
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 16, 16, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b''))


def write_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def bundle_at(path):
    document = Path(path).read_text(encoding='utf-8')
    match = re.search(r'<script\b(?=[^>]*\bid=[\"\']reviewData[\"\'])[^>]*>(.*?)</script>', document, re.S)
    if not match:
        raise AssertionError('generated page lacks baked reviewData')
    return json.loads(match[1])


class ReviewWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pub, self.mp = self.root/'pub', self.root/'map'
        self.pm, self.mm, self.labels = self.root/'pub.csv', self.root/'map.csv', self.root/'labels.csv'
        pub_rows, map_rows, labels = [], [], []
        for bid in ('a', 'b'):
            for pole, root, rows in [('pub', self.pub, pub_rows), ('map', self.mp, map_rows)]:
                (root/bid).mkdir(parents=True)
                for i in range(2):
                    filename = f'{pole} #{i}.jpg'
                    (root/bid/filename).write_bytes(synthetic_png(40 + i * 50, 80 if pole == 'pub' else 160, 10 if bid == 'a' else 200))
                    rows.append(dict(building_id=bid, filename=filename,
                                     source_filename=f'{pole}-{bid}-{i}', split='train',
                                     drawing_flag='0', capture_era='2010+'))
            labels.append(dict(building_id=bid, construction_era='1850-1892', phase_years='1880',
                               evidence='</script> __REVIEW_UI__ __REVIEW_MODEL__ & "été"\nsource quote',
                               reviewer='Source label reviewer', reviewed_at='2026-10-25', confidence='high'))
        write_csv(self.pm, pub_rows)
        write_csv(self.mm, map_rows)
        write_csv(self.labels, labels)
        self.pair_dir, self.image_dir = self.root/'pairs', self.root/'images'
        result = subprocess.run([sys.executable, str(TRAINING/'prepare_pair_audit.py'),
            '--publisher-manifest', str(self.pm), '--mapillary-manifest', str(self.mm),
            '--publisher-root', str(self.pub), '--mapillary-root', str(self.mp),
            '--samples', '3', '--out-dir', str(self.pair_dir)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        prepare_images(self.pm, self.labels, self.pub, self.image_dir)

    def generate(self, kind, audit=None, output=None):
        audit = audit or (self.pair_dir if kind == 'pair' else self.image_dir)
        output = output or audit/'workbench.html'
        result = build(kind, audit, output, self.pm, self.mm, self.pub, self.mp, self.labels)
        return output, bundle_at(output), result

    def export_from_model(self, bundle, patches):
        code = """
const fs = require('node:fs');
const api = require(process.argv[1]);
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const model = api.create(input.bundle);
for (const [key, fields] of input.patches) model.setDraft(key, fields);
process.stdout.write(model.exportCSV());
"""
        result = subprocess.run(['node', '-e', code, str(TRAINING/'review_workbench_model.js')],
                                input=json.dumps({'bundle': bundle, 'patches': patches}),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_pair_round_trip_preserves_immutable_fields_and_escaped_review_text(self):
        output, bundle, _ = self.generate('pair')
        first = bundle['rows'][0]
        evidence = 'same "facade", étude\nsecond line'
        fields = dict(identity='ambiguous', evidence=evidence, reviewer='Synthetic reviewer',
                      reviewed_at='2026-10-25', confidence='low')
        returned = self.root/'returned.csv'
        returned.write_text(self.export_from_model(bundle, [(first['key'], fields)]), encoding='utf-8')
        report = validate_pairs(self.pair_dir/'sample.json', returned, self.pm, self.mm, self.pub, self.mp)
        self.assertEqual(report['counts']['ambiguous'], 1)
        self.assertIsNone(report['cleanliness'])
        with returned.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(rows[0]['evidence'], evidence)
        for field, value in first['values'].items():
            if field not in bundle['editable']:
                self.assertEqual(rows[0][field], value)
        self.assertIn('%23', first['images'][0]['src'])
        self.assertTrue(first['images'][0]['src'].startswith('../'))

    def test_construction_round_trip_and_inert_json_payload(self):
        output, bundle, _ = self.generate('construction')
        self.assertEqual(bundle['rows'][0]['context'][2]['value'],
                         '</script> __REVIEW_UI__ __REVIEW_MODEL__ & "été"\nsource quote')
        document = output.read_text()
        self.assertNotIn('</script> __REVIEW_UI__', document)
        self.assertIn('\\u003c/script\\u003e', document)
        first = bundle['rows'][0]
        fields = dict(applicability='applicable', observation='Synthetic "view", étage\nline',
                      reviewer='Synthetic image reviewer', reviewed_at='2026-10-25', confidence='medium')
        returned = self.root/'returned-images'
        returned.mkdir()
        (returned/'metadata.json').write_bytes((self.image_dir/'metadata.json').read_bytes())
        (returned/'reviews.csv').write_text(self.export_from_model(bundle, [(first['key'], fields)]), encoding='utf-8')
        rows = load_manifest(self.pm)
        for row in rows:
            row['_path'] = self.pub/row['building_id']/row['filename']
        keys, report = eligible_image_keys(returned, self.pm, self.labels, rows,
                                          load_reviewed_labels(self.labels, labels_only=True))
        self.assertEqual(keys, {first['key']})
        self.assertEqual(report['eligible_images'], 1)

    def test_no_clobber_and_no_source_mutation(self):
        before = {path: path.read_bytes() for path in [self.pm, self.mm, self.labels,
                 self.image_dir/'metadata.json', self.image_dir/'reviews.csv']}
        output, _, _ = self.generate('construction')
        original = output.read_bytes()
        with self.assertRaisesRegex(ValueError, 'exists'):
            self.generate('construction')
        self.assertEqual(output.read_bytes(), original)
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_source_changes_refuse_without_output(self):
        (self.pub/'a'/'pub #0.jpg').write_bytes(b'new source bytes')
        target = self.image_dir/'new.html'
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.generate('construction', output=target)
        self.assertFalse(target.exists())

    def test_review_revision_changes_storage_identity_not_cohort(self):
        first_path, first, _ = self.generate('construction')
        with (self.image_dir/'reviews.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        rows[0].update(applicability='unknown')  # Conservative source-owned negative/unknown row.
        write_csv(self.image_dir/'reviews.csv', rows)
        _, second, _ = self.generate('construction', output=self.image_dir/'second.html')
        self.assertEqual(first['cohort_id'], second['cohort_id'])
        self.assertNotEqual(first['baseline_sha256'], second['baseline_sha256'])
        self.assertEqual(second['rows'][0]['values']['applicability'], 'unknown')

    def test_missing_construction_rows_are_pending_not_automatic_labels(self):
        with (self.image_dir/'reviews.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        write_csv(self.image_dir/'reviews.csv', rows[:1])
        _, bundle, _ = self.generate('construction')
        self.assertEqual(len(bundle['rows']), 4)
        self.assertTrue(all(row['values']['applicability'] == '' for row in bundle['rows']))

    def test_stage_validated_returns_into_new_cohorts_only(self):
        for kind in ('pair', 'construction'):
            with self.subTest(kind=kind):
                audit = self.pair_dir if kind == 'pair' else self.image_dir
                _, bundle, _ = self.generate(kind)
                decision = {'identity': 'correct', 'evidence': 'Synthetic quoted view'} if kind == 'pair' else {
                    'applicability': 'applicable', 'observation': 'Synthetic matching principal volume'}
                fields = dict(decision, reviewer='Synthetic human fixture', reviewed_at='2026-10-25', confidence='high')
                returned = self.root/f'{kind}-returned.csv'
                returned.write_text(self.export_from_model(bundle, [(bundle['rows'][0]['key'], fields)]), encoding='utf-8')
                baseline = (audit/'reviews.csv').read_bytes()
                output = self.root/f'{kind}-staged'
                stage(kind, audit, returned, output, self.pm, self.mm, self.pub, self.mp, self.labels)
                self.assertEqual((audit/'reviews.csv').read_bytes(), baseline)
                self.assertEqual((output/'reviews.csv').read_bytes(), returned.read_bytes())
                report = json.loads((output/'validation.json').read_text())
                if kind == 'pair':
                    self.assertEqual(report['validation']['counts']['correct'], 1)
                else:
                    self.assertEqual(report['validation']['eligible_images'], 1)
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with self.assertRaisesRegex(ValueError, 'exists'):
                    stage(kind, audit, returned, output, self.pm, self.mm, self.pub, self.mp, self.labels)
                self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)

    def test_stage_refuses_reviews_entered_since_page_generation(self):
        _, bundle, _ = self.generate('pair')
        returned = self.root/'stale.csv'
        returned.write_text(self.export_from_model(bundle, []), encoding='utf-8')
        with (self.pair_dir/'reviews.csv').open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        rows[0].update(identity='correct', evidence='Existing human work', reviewer='Original reviewer',
                       reviewed_at='2026-10-25', confidence='high')
        write_csv(self.pair_dir/'reviews.csv', rows)
        original = (self.pair_dir/'reviews.csv').read_bytes()
        output = self.root/'refused-stage'
        with self.assertRaisesRegex(ValueError, 'existing source review'):
            stage('pair', self.pair_dir, returned, output, self.pm, self.mm, self.pub, self.mp, self.labels)
        self.assertFalse(output.exists())
        self.assertEqual((self.pair_dir/'reviews.csv').read_bytes(), original)

    def test_stage_refuses_tampering_before_creating_destination(self):
        _, bundle, _ = self.generate('construction')
        returned = self.root/'tampered.csv'
        text = self.export_from_model(bundle, [])
        returned.write_text(text.replace('1850-1892', 'pre-1850'), encoding='utf-8')
        output = self.root/'tampered-stage'
        with self.assertRaisesRegex(ValueError, 'immutable'):
            stage('construction', self.image_dir, returned, output, self.pm, self.mm, self.pub, self.mp, self.labels)
        self.assertFalse(output.exists())

    def test_manifest_escape_is_rejected_before_image_reads(self):
        with self.pm.open(newline='') as handle:
            rows = list(csv.DictReader(handle))
        rows[0]['filename'] = '../outside.jpg'
        write_csv(self.pm, rows)
        target = self.pair_dir/'unsafe.html'
        with self.assertRaisesRegex(ValueError, 'filename'):
            self.generate('pair', output=target)
        self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
