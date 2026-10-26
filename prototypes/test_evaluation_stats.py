"""Offline statistics fixtures; never train or evaluate a real model."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'three-ages' / 'training'))
from stats import building_macro_mean, paired_grouped_bootstrap, classification_by_class


class EvaluationStatsTests(unittest.TestCase):
    def test_minority_recall_not_hidden_by_dominant_class(self):
        modern = classification_by_class([[10000, 0], [37, 12]], ['photo', 'drawing'])
        self.assertEqual(modern['drawing']['support'], 49)
        self.assertAlmostEqual(modern['drawing']['recall'], 12 / 49)
        older = classification_by_class([[134, 190], [4, 1157]], ['photo', 'drawing'])
        self.assertEqual(older['photo']['support'], 324)
        self.assertAlmostEqual(older['photo']['recall'], 134 / 324)

    def test_unsupported_classes_remain_undefined(self):
        result = classification_by_class([[4, 0], [0, 0]], ['photo', 'drawing'])
        self.assertIsNone(result['drawing']['recall'])
        self.assertIsNone(result['drawing']['precision'])
        result = classification_by_class([[4, 0], [2, 0]], ['photo', 'drawing'])
        self.assertEqual(result['drawing']['recall'], 0.)
        self.assertIsNone(result['drawing']['precision'])

    def test_confusion_validation(self):
        for matrix, labels in [([], []), ([[1]], ['a', 'b']),
                               ([[1, -1], [0, 1]], ['a', 'b']),
                               ([[1., 0], [0, 1]], ['a', 'b']),
                               ([[1, 0], [0, 1]], ['a', 'a'])]:
            with self.assertRaises(ValueError):
                classification_by_class(matrix, labels)


    def test_unequal_building_sizes(self):
        ids = ['a'] * 9 + ['b']
        scores = [1] * 9 + [0]
        self.assertEqual(building_macro_mean(ids, scores), .5)
        macro = paired_grouped_bootstrap(ids, scores, [0] * 10, seed=3)
        micro = paired_grouped_bootstrap(ids, scores, [0] * 10,
                                         weighting='image_micro', seed=3)
        self.assertEqual(macro['difference'], .5)
        self.assertEqual(micro['difference'], .9)
        self.assertEqual(macro['n_buildings'], 2)
        self.assertEqual(macro['n_images'], 10)
        self.assertEqual(macro['ci'], [0, 1])

    def test_pairing_seed_and_order(self):
        ids = ['b', 'a', 'a', 'c']
        a, b = [1, 1, 0, 0], [0, 1, 0, 1]
        result = paired_grouped_bootstrap(ids, a, b, n_resamples=101, seed=17)
        self.assertEqual(result, paired_grouped_bootstrap(ids, a, b, n_resamples=101, seed=17))
        self.assertEqual(result, paired_grouped_bootstrap(ids[::-1], a[::-1], b[::-1],
                                                        n_resamples=101, seed=17))
        same = paired_grouped_bootstrap(ids, a, a)
        self.assertEqual(same['ci'], [0, 0])
        reverse = paired_grouped_bootstrap(ids, b, a, n_resamples=101, seed=17)
        self.assertAlmostEqual(reverse['difference'], -result['difference'])
        self.assertAlmostEqual(reverse['ci'][0], -result['ci'][1])
        self.assertAlmostEqual(reverse['ci'][1], -result['ci'][0])

    def test_whole_groups_not_independent_images(self):
        result = paired_grouped_bootstrap(['one'] * 100, [1] * 100, [0] * 100)
        self.assertEqual(result['ci'], [1, 1])
        self.assertEqual(result['n_buildings'], 1)

    def test_bad_inputs(self):
        for ids, a, b in [([], [], []), (['a'], [], [1]),
                          ([''], [1], [0]), (['a'], [float('nan')], [0]),
                          (['a'], [0], [float('inf')])]:
            with self.assertRaises(ValueError):
                paired_grouped_bootstrap(ids, a, b)
        for kwargs in [{'n_resamples': 0}, {'n_resamples': 1.5},
                       {'confidence': 1}, {'weighting': 'unknown'}]:
            with self.assertRaises(ValueError):
                paired_grouped_bootstrap(['a'], [1], [0], **kwargs)
        with self.assertRaises(ValueError):
            building_macro_mean([], [])


if __name__ == '__main__':
    unittest.main()
