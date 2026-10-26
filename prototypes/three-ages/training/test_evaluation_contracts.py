"""Synthetic CPU-only ML contract tests; never score corpus holdouts."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

from data_integrity import assert_image_isolation
from eval_test_once import paired_comparison, vectors
from train_local_pilot import check_splits, metrics


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train_probe import validate_cache_training
from construction_image_reviews import prepare as prepare_image_reviews


class EvaluationContractTests(unittest.TestCase):
    def test_old_tuned_probe_cache_rejected_even_with_clean_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'manifest.csv'
            path.write_text('clean manifest')
            with self.assertRaisesRegex(ValueError, 'needs --checkpoint'):
                validate_cache_training({'model': 'ViT-B-32/laion2b+tuned:old'}, path)

    def test_duplicate_copy_cannot_be_cross_era_mate(self):
        gallery = [dict(building_id='A', _id=f'pub/A/{i}', capture_era=era,
                        _image_identity='same-pixels')
                   for i, era in enumerate(['pre-1900', '2010+'])]
        gallery += [dict(building_id=str(i), _id=f'pub/{i}/x', capture_era='2010+',
                         _image_identity=f'other-{i}') for i in range(5)]
        vec = np.array([[1., 0.]]*2 + [[0., 1.]]*5)
        result = metrics([gallery[0]], vec[:1], gallery, vec, return_outcomes=True)
        self.assertEqual(result['queries_with_mates'], 0)
        self.assertEqual(result['cross_era_eligible_queries'], 0)
        self.assertEqual(result['outcomes'], [])

    def test_train_split_check_rejects_pixels_shared_between_buildings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'a.jpg'
            path.write_bytes(b'same pixels')
            rows = [dict(building_id=b, filename='a.jpg', split=s, _path=path)
                    for b, s in [('A', 'train'), ('B', 'test')]]
            with self.assertRaisesRegex(ValueError, 'Shared-image'):
                check_splits(rows, [])

    def test_paired_comparison_keeps_shared_groups_and_eligibility(self):
        old = [dict(id='1', group='A', building_id='A', top5=0, cross_era_top5_fair=None),
               dict(id='2', group='A', building_id='B', top5=1, cross_era_top5_fair=0)]
        new = [dict(old[0], top5=1), dict(old[1], cross_era_top5_fair=1)]
        a = {leg: {'outcomes': old} for leg in ['publisher_test', 'cross_pole_test']}
        b = {leg: {'outcomes': new} for leg in ['publisher_test', 'cross_pole_test']}
        result = paired_comparison(a, b)['publisher_test']['top5']
        self.assertEqual(result['independent_groups'], 1)
        self.assertEqual(result['image_micro_paired_difference']['difference'], .5)
        self.assertEqual(result['group_macro_paired_difference']['ci'], [.5, .5])
        new[0]['cross_era_top5_fair'] = 0
        with self.assertRaisesRegex(ValueError, 'eligibility'):
            paired_comparison(a, b)

    def test_cache_checkpoint_and_toolchain_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'cache.npz'
            row = dict(building_id='A', filename='a.jpg')
            def write(**kwargs):
                np.savez(path, ids=['A/a.jpg'], embeddings=[[1., 0.]], model='test', **kwargs)
            write(toolchain='same', checkpoint_sha256='weights')
            with self.assertRaisesRegex(ValueError, 'checkpoint mismatch'):
                vectors(path, [row], checkpoint_sha256='different')
            self.assertEqual(vectors(path, [row], checkpoint_sha256='weights')[1], 'same')
            with self.assertRaisesRegex(ValueError, 'backbone'):
                vectors(path, [row], checkpoint_sha256='weights', expected_model='other/backbone')
            write()
            with self.assertRaisesRegex(ValueError, 'toolchain'):
                vectors(path, [row])

    def test_construction_cli_needs_explicit_image_reviews_not_building_yes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records, labels = [], []
            for i in range(8):
                bid = str(i)
                path = root/bid/'a.jpg'
                path.parent.mkdir()
                path.write_bytes(f'pixels-{i}'.encode())
                records.append(dict(building_id=bid, filename='a.jpg', drawing_flag='0',
                                    split='train' if i < 4 else ('val' if i < 6 else 'test')))
                labels.append(dict(building_id=bid, construction_era='pre-1850' if i % 2 == 0 else 'post-1975',
                                   phase_years='1800' if i % 2 == 0 else '1980', evidence='synthetic source quote',
                                   reviewer='Source reviewer', reviewed_at='2026-10-25', confidence='high',
                                   depicts_building='yes'))
            manifest, label_path, cache = root/'manifest.csv', root/'labels.csv', root/'cache.npz'
            for path, rows in [(manifest, records), (label_path, labels)]:
                with path.open('w', newline='') as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
            import hashlib
            np.savez(cache, ids=[r['building_id']+'/a.jpg' for r in records],
                     embeddings=[[i % 2, 1.] for i in range(8)], model='fixture',
                     image_sha256=[hashlib.sha256((root/r['building_id']/r['filename']).read_bytes()).hexdigest()
                                   for r in records])
            out, review_dir = root/'report.json', root/'image-reviews'
            command = [sys.executable, str(Path(__file__).resolve().parents[1]/'train_probe.py'),
                       '--head', 'construction_era', '--reviewed-labels', str(label_path),
                       '--manifest', str(manifest), '--image-root', str(root),
                       '--embeddings', str(cache), '--out', str(out), '--grouped-cv', '3']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires --image-reviews', result.stderr)
            prepare_image_reviews(manifest, label_path, root, review_dir)
            command += ['--image-reviews', str(review_dir)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('no applicable construction image rows', result.stderr)
            self.assertFalse(out.exists())
            reviews_path = review_dir/'reviews.csv'
            with reviews_path.open() as handle:
                rows = list(csv.DictReader(handle))
            for row in rows:
                row.update(applicability='applicable' if int(row['building_id']) < 6 else 'wrong_subject',
                           observation='Synthetic human image decision', reviewer='Image reviewer',
                           reviewed_at='2026-10-25', confidence='high')
            with reviews_path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report['n_images'], 6)
            self.assertEqual(report['image_applicability']['eligible_images'], 6)
            self.assertEqual(report['test_rows_used'], 0)
            self.assertTrue(all(r['building_id'] not in ('6', '7') for r in report['outcomes']))
            # Fresh human review of a corrected source must not validate stale features.
            (root/'0/a.jpg').write_bytes(b'corrected source bytes')
            corrected = root/'corrected-reviews'
            prepare_image_reviews(manifest, label_path, root, corrected)
            with (corrected/'reviews.csv').open() as handle:
                corrected_rows = list(csv.DictReader(handle))
            for row in corrected_rows:
                row.update(applicability='applicable' if int(row['building_id']) < 6 else 'wrong_subject',
                           observation='Synthetic corrected-source review', reviewer='Image reviewer',
                           reviewed_at='2026-10-25', confidence='high')
            with (corrected/'reviews.csv').open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(corrected_rows[0]))
                writer.writeheader()
                writer.writerows(corrected_rows)
            ordinary = list(command)
            index = ordinary.index('--grouped-cv')
            del ordinary[index:index+2]
            ordinary[ordinary.index('--out')+1] = str(root/'ordinary.json')
            ordinary[ordinary.index('--image-reviews')+1] = str(corrected)
            result = subprocess.run(ordinary, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cached image bytes differ', result.stderr)
            self.assertFalse((root/'ordinary.json').exists())

    def test_capture_era_cli_excludes_dated_drawings_and_unknown_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for bid in range(6):
                for i, era in enumerate(('pre-1900', '2010+')):
                    rows.append(dict(building_id=str(bid), filename=f'{i}.jpg', split='train',
                                     drawing_flag='0', capture_era=era))
            rows += [dict(building_id='drawing', filename='a.jpg', split='train', drawing_flag='1', capture_era='pre-1900'),
                     dict(building_id='unknown', filename='a.jpg', split='train', drawing_flag='', capture_era='pre-1900')]
            for row in rows:
                path = root/row['building_id']/row['filename']
                path.parent.mkdir(exist_ok=True)
                path.write_bytes((row['building_id']+'/'+row['filename']).encode())
            manifest, cache, out = root/'manifest.csv', root/'cache.npz', root/'report.json'
            with manifest.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            import hashlib
            np.savez(cache, ids=[r['building_id']+'/'+r['filename'] for r in rows],
                     embeddings=[[int(r['capture_era']=='2010+'), 1.] for r in rows], model='fixture',
                     image_sha256=[hashlib.sha256((root/r['building_id']/r['filename']).read_bytes()).hexdigest() for r in rows])
            result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1]/'train_probe.py'),
                '--head', 'capture_era', '--manifest', str(manifest), '--image-root', str(root),
                '--embeddings', str(cache), '--out', str(out), '--grouped-cv', '3'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report['n_images'], 12)
            self.assertFalse({'drawing', 'unknown'} & {r['building_id'] for r in report['outcomes']})
            self.assertIn('proxy', report['target_semantics'])

    def test_probe_defaults_to_val_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root/'manifest.csv'
            records = []
            for i, split in enumerate(['train', 'train', 'train', 'train', 'val', 'val', 'test', 'test']):
                bid = str(i)
                image = root/bid/'a.jpg'
                image.parent.mkdir()
                image.write_bytes(f'unique-{i}'.encode())
                records.append(dict(building_id=bid, filename='a.jpg', split=split, drawing_flag=str(i % 2)))
            with manifest.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
            cache = root/'cache.npz'
            np.savez(cache, ids=[r['building_id']+'/a.jpg' for r in records],
                     embeddings=np.array([[i % 2, 1.] for i in range(8)]), model='fixture')
            out = root/'report.json'
            command = [sys.executable, str(Path(__file__).resolve().parents[1]/'train_probe.py'),
                       '--head', 'drawing', '--manifest', str(manifest), '--image-root', str(root),
                       '--embeddings', str(cache), '--out', str(out)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report['evaluation_split'], 'val')
            self.assertEqual(report['n_val'], 2)
            self.assertEqual(report['n_val_buildings'], 2)
            self.assertEqual(report['n_test_buildings'], 2)
            self.assertNotIn('top1_test', report)
            self.assertIn('building_macro_top1_val', report)
            self.assertEqual(report['per_class']['drawing']['support'], 1)
            self.assertIn('recall', report['per_class']['drawing'])
            original = out.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(out.read_bytes(), original)
            result = subprocess.run(command+['--eval-split', 'test'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('test cohort is spent', result.stderr)


if __name__ == '__main__':
    unittest.main()
