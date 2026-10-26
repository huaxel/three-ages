#!/usr/bin/env python3
"""Offline, standard-library shared-image isolation regression tests."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TRAINING = Path(__file__).resolve().parent/'three-ages/training'
sys.path.insert(0, str(TRAINING))
from data_integrity import assert_image_isolation, audit


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def row(self, bid, split, content, name='a.jpg', source=''):
        path = self.root/bid/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return dict(building_id=bid, filename=name, split=split,
                    source_filename=source, _path=path, _id=f'{bid}/{name}')

    def test_identical_bytes_different_names_rejected_across_poles(self):
        a = self.row('A', 'train', b'pixels', 'old.jpg')
        b = self.row('B', 'test', b'pixels', 'new.jpg')
        with self.assertRaisesRegex(ValueError, 'Shared-image split leakage'):
            assert_image_isolation([a], [b])

    def test_mapillary_source_id_is_identity_even_if_bytes_differ(self):
        a = self.row('A', 'train', b'resize1', source='123')
        b = self.row('B', 'val', b'resize2', source='123')
        with self.assertRaises(ValueError):
            assert_image_isolation([], [a, b])

    def test_publisher_filename_is_not_identity(self):
        a = self.row('A', 'train', b'a', source='same.jpg')
        b = self.row('B', 'test', b'b', source='same.jpg')
        assert_image_isolation([a, b], [])

    def test_transitive_group_quarantines_every_copy(self):
        a = self.row('A', 'train', b'a', source='123')
        b = self.row('B', 'train', b'b', source='123')
        c = self.row('C', 'test', b'b', source='456')
        report, excluded = audit([], [a, b, c])
        self.assertEqual(report['cross_split_groups'], 1)
        self.assertEqual(excluded, {a['_id'], b['_id'], c['_id']})

    def test_within_split_shared_buildings_share_bootstrap_group(self):
        a = self.row('A', 'test', b'a')
        b = self.row('B', 'test', b'a')
        c = self.row('C', 'test', b'c')
        assert_image_isolation([a, b, c], [])
        self.assertEqual(a['_evaluation_group'], b['_evaluation_group'])
        self.assertNotEqual(a['_evaluation_group'], c['_evaluation_group'])

    def test_missing_pixels_refused(self):
        a = self.row('A', 'train', b'a')
        a['_path'].unlink()
        with self.assertRaises(FileNotFoundError):
            assert_image_isolation([a], [])

    def test_cli_new_manifests_preserve_originals_and_refuse_overwrite(self):
        rows = [self.row('A', 'train', b'shared'), self.row('B', 'test', b'shared'),
                self.row('C', 'train', b'clean')]
        paths = []
        for pole, chosen in [('pub', rows[:2]), ('map', rows[2:])]:
            path = self.root/f'{pole}.csv'
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=['building_id', 'filename', 'split', 'source_filename'], extrasaction='ignore')
                writer.writeheader()
                writer.writerows(chosen)
            paths.append(path)
        originals = [p.read_bytes() for p in paths]
        out = self.root/'clean'
        command = [sys.executable, str(TRAINING/'data_integrity.py'),
                   '--publisher-manifest', str(paths[0]), '--mapillary-manifest', str(paths[1]),
                   '--publisher-root', str(self.root), '--mapillary-root', str(self.root),
                   '--out-dir', str(out)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((out/'shared-image-audit.json').read_text())['excluded_rows'], 2)
        with (out/'manifest.csv').open() as handle:
            self.assertEqual(list(csv.DictReader(handle)), [])
        self.assertEqual([p.read_bytes() for p in paths], originals)
        before = {p.name: p.read_bytes() for p in out.iterdir()}
        result = subprocess.run(command, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, before)


if __name__ == '__main__':
    unittest.main()
