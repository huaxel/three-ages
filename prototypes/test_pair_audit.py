#!/usr/bin/env python3
"""No-network fixtures for actual-training-pair identity audit preparation."""
import sys
import tempfile
import unittest
import runpy
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent/'three-ages/training'))
from prepare_pair_audit import prepare
from pair_sampling import mine_pairs


class PairAuditTests(unittest.TestCase):
    def test_legacy_cache_builder_forwards_manifest_to_canonical_builder(self):
        script = Path(__file__).resolve().parent/'three-ages/training/build_tuned_embeddings.py'
        with tempfile.TemporaryDirectory() as directory:
            out = str(Path(directory)/'cache.npz')
            args = [str(script), '--checkpoint', 'weights.pt', '--out', out,
                    '--manifest', 'isolated.csv', '--image-root', 'images', '--device', 'cpu']
            with patch.object(sys, 'argv', args), patch('subprocess.run') as runner:
                runpy.run_path(str(script), run_name='__main__')
            command = runner.call_args.args[0]
            self.assertTrue(command[1].endswith('/three-ages/build_embeddings.py'))
            self.assertEqual(command[command.index('--manifest')+1], 'isolated.csv')
            self.assertEqual(command[command.index('--image-root')+1], 'images')
            self.assertTrue(runner.call_args.kwargs['check'])


    def test_actual_pairs_repeatable_train_photo_only_and_reviews_blank(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'image.jpg'
            path.write_bytes(b'fixture image')
            def row(bid, pole, i, split='train', flag='0'):
                return dict(building_id=bid, filename=f'{i}.jpg',
                            _id=f'{pole}/{bid}/{i}.jpg', _path=path,
                            split=split, drawing_flag=flag, capture_era='2010+')
            pub = [row('A', 'pub', i) for i in range(4)]
            pub += [row('B', 'pub', 0, flag='1'), row('C', 'pub', 0, split='test')]
            mmap = [row(b, 'map', i) for b in 'ABC' for i in range(5)]
            rows, pairs, available = prepare(pub, mmap, seed=42, samples=3)
            again = prepare(pub, mmap, seed=42, samples=3)
            self.assertEqual((rows, pairs, available), again)
            actual, _ = mine_pairs(pub, mmap, seed=42)
            actual_ids = {a['_id']+'|'+b['_id'] for a, b in actual}
            self.assertEqual(available, 20)
            self.assertEqual(len(rows), 3)
            for reviewed in rows:
                self.assertIn(reviewed['pair_id'], actual_ids)
                self.assertEqual(reviewed['building_id'], 'A')
                self.assertEqual(len(reviewed['publisher_sha256']), 64)
                for field in ('identity', 'evidence', 'reviewer', 'reviewed_at', 'confidence'):
                    self.assertEqual(reviewed[field], '')
            with self.assertRaises(ValueError):
                prepare(pub, mmap, samples=0)
            with self.assertRaises(ValueError):
                prepare([], mmap)


if __name__ == '__main__':
    unittest.main()
