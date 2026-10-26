"""Synthetic CPU development-CV fixtures, never real corpus holdout evaluation."""
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from sklearn.preprocessing import StandardScaler
from development_cv import development_folds, grouped_development_cv


class DevelopmentCVTests(unittest.TestCase):
    def fixtures(self):
        rows = [dict(building_id=str(bid), filename=f'{image}.jpg',
                     split='train' if bid < 6 else 'val',
                     _evaluation_group=str(bid // 2), capture_era='2010+')
                for bid in range(8) for image in range(2)]
        y = np.array([i % 2 for i in range(len(rows))])
        X = np.column_stack([np.arange(len(rows)), y * 10.])
        return X, y, rows

    def test_group_folds_are_repeatable_row_order_invariant_and_disjoint(self):
        _, _, rows = self.fixtures()
        def assignment(rows):
            result = {}
            for fold, (fit, score) in enumerate(development_folds(rows, n_splits=4)):
                self.assertTrue(len(fit) and len(score))
                self.assertFalse({rows[i]['_evaluation_group'] for i in fit} &
                                 {rows[i]['_evaluation_group'] for i in score})
                for i in score:
                    key = rows[i]['building_id']+'/'+rows[i]['filename']
                    self.assertNotIn(key, result)
                    result[key] = fold
            self.assertEqual(len(result), len(rows))
            return result
        self.assertEqual(assignment(rows), assignment(rows[::-1]))

    def test_scalers_fit_only_fold_training_rows_and_report_support(self):
        X, y, rows = self.fixtures()
        observed = []
        class RecordingScaler(StandardScaler):
            def fit(self, X, y=None, **kwargs):
                observed.append(X[:, 0].tolist())
                return super().fit(X, y, **kwargs)
        with patch('development_cv.StandardScaler', RecordingScaler):
            result = grouped_development_cv(X, y, rows, ['old', 'new'], ordered=True, n_splits=4)
        expected = [X[fit, 0].tolist() for fit, _ in development_folds(rows, n_splits=4)]
        self.assertEqual(observed, expected)
        self.assertEqual(result['test_rows_used'], 0)
        self.assertEqual(result['n_groups'], 4)
        self.assertEqual(len(result['outcomes']), 16)
        self.assertAlmostEqual(result['metrics']['building_macro_exact_accuracy'], 1.)
        self.assertEqual(len(result['metrics']['confusion_matrix']), 2)
        self.assertEqual(result['metrics']['per_class']['old']['support'], 8)
        self.assertIn('recall', result['per_capture_era']['2010+']['per_class']['new'])
        self.assertIn('dummy_building_macro_within_one_era', result['metrics'])
        self.assertNotIn('ci', result['metrics'])
        for fold in result['folds']:
            self.assertFalse(set(fold['fit_buildings']) & set(fold['score_buildings']))
            self.assertEqual(set(fold['score_class_support']), {'old', 'new'})

    def test_invalid_folds_and_test_rows_refuse_before_fitting(self):
        X, y, rows = self.fixtures()
        with patch('development_cv.StandardScaler') as scaler:
            for folds in (1, 5):
                with self.assertRaises(ValueError):
                    grouped_development_cv(X, y, rows, ['a', 'b'], n_splits=folds)
            with self.assertRaisesRegex(ValueError, 'fewer than two classes'):
                grouped_development_cv(X, y * 0, rows, ['a', 'b'], n_splits=4)
            with self.assertRaisesRegex(ValueError, 'never test'):
                grouped_development_cv(X, y, [dict(rows[0], split='test')]+rows[1:], ['a', 'b'], n_splits=4)
            scaler.assert_not_called()

    def test_multilabel_has_explicit_exact_and_micro_metrics(self):
        X, y, rows = self.fixtures()
        target = np.column_stack([y, 1-y])
        report = grouped_development_cv(X, target, rows, ['a', 'b'], n_splits=4)
        self.assertIn('micro_f1', report['metrics'])
        self.assertEqual(report['outcomes'][0]['true'], [0, 1])
        with self.assertRaises(ValueError):
            grouped_development_cv(X, target, rows, ['a', 'b'], ordered=True, n_splits=4)

    def test_cli_excludes_test_labels_refuses_cache_gaps_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for i in range(10):
                split = 'train' if i < 6 else ('val' if i < 8 else 'test')
                image = root/str(i)/'a.jpg'
                image.parent.mkdir()
                image.write_bytes(f'unique-{i}'.encode())
                records.append(dict(building_id=str(i), filename='a.jpg', split=split,
                                    drawing_flag=str(i % 2)))
            # Explicit historical gap must be excluded before the isolation hasher.
            records.append(dict(building_id='17387', filename='11500227_0192_P04.jpg',
                                split='train', drawing_flag='0'))
            manifest, cache, out = root/'manifest.csv', root/'cache.npz', root/'report.json'
            with manifest.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(records[0]))
                writer.writeheader()
                writer.writerows(records)
            def write_cache(records, **extra):
                np.savez(cache, ids=[r['building_id']+'/a.jpg' for r in records],
                         embeddings=[[int(r['building_id']) % 2, 1.] for r in records],
                         model=extra.pop('model', 'fixture'),
                         image_sha256=[hashlib.sha256((root/r['building_id']/r['filename']).read_bytes()).hexdigest()
                                       for r in records], **extra)
            # Test rows have no embeddings: they cannot affect the CV denominator.
            write_cache(records[:8])
            command = [sys.executable, str(Path(__file__).resolve().parents[1]/'train_probe.py'),
                       '--head', 'drawing', '--manifest', str(manifest), '--image-root', str(root),
                       '--embeddings', str(cache), '--out', str(out), '--grouped-cv', '4']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(out.read_text())
            self.assertEqual(report['test_rows_used'], 0)
            self.assertEqual(report['n_images'], 8)
            self.assertEqual(report['excluded_cache_ids'], ['17387/11500227_0192_P04.jpg'])
            self.assertFalse({'8', '9'} & {r['building_id'] for r in report['outcomes']})
            self.assertEqual(report['input_sha256']['manifest'], hashlib.sha256(manifest.read_bytes()).hexdigest())
            original = out.read_bytes()
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(out.read_bytes(), original)
            # Use a separate output path so refusal is about the cache gap, not overwrite.
            command[command.index('--out')+1] = str(root/'gap.json')
            write_cache(records[:7])
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('undeclared CV cache gaps', result.stderr)
            self.assertFalse((root/'gap.json').exists())
            result = subprocess.run(command+['--eval-split', 'test', '--acknowledge-spent-test'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('grouped CV cannot', result.stderr)
            write_cache(records[:8], model='fixture+tuned:old')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires a project-frozen encoder', result.stderr)
            self.assertFalse((root/'gap.json').exists())
            write_cache(records[:8])
            # A correction to a source file must not reuse an earlier feature vector.
            (root/'0/a.jpg').write_bytes(b'changed pixels')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('cached image bytes differ', result.stderr)
            self.assertFalse((root/'gap.json').exists())
            # Retrofitting old caches with current hashes is not permitted by the workflow.
            np.savez(cache, ids=[r['building_id']+'/a.jpg' for r in records[:8]],
                     embeddings=[[int(r['building_id']) % 2, 1.] for r in records[:8]], model='fixture')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires per-image SHA-256', result.stderr)
            self.assertFalse((root/'gap.json').exists())


if __name__ == '__main__':
    unittest.main()
