"""Offline tests for the retrieval utility's ranking rules.

No index, no model, no files: synthetic vectors and metadata only, so the
invariants the CLI relies on are checked in well under a second.
"""
import unittest

import numpy as np

from three_ages import query


def row(bid, era='1990-2009', filename='x.jpg'):
    return {'building_id': bid, 'capture_era': era, 'filename': filename}


class QueryTests(unittest.TestCase):
    def setUp(self):
        # Three buildings, two pictures each; eras chosen so cross-era is possible.
        self.ids = ['A/a1.jpg', 'A/a2.jpg', 'B/b1.jpg', 'C/c1.jpg']
        self.rows = [row('A', '1990-2009'), row('A', '1900-1929'),
                     row('B', '1990-2009'), row('C', '2010+')]
        # a1 is closest to a2, then to b1, then to c1.
        self.matrix = np.array([[1.0, 0.0], [0.9, 0.1], [0.5, 0.5], [0.0, 1.0]],
                               dtype='float32')
        self.matrix /= np.linalg.norm(self.matrix, axis=1, keepdims=True)

    def run_query(self, **kw):
        return query([self.matrix[0]], ['A/a1.jpg'], [self.rows[0]], self.ids,
                     self.matrix, self.rows, kw.get('k', 3),
                     kw.get('cross_era', False), kw.get('min_score', 0.0))

    def test_query_never_returns_itself(self):
        hits = self.run_query(k=4)
        self.assertNotIn('A/a1.jpg', [h['match'] for h in hits])

    def test_cross_era_filter_excludes_same_era_and_undated(self):
        hits = self.run_query(k=4, cross_era=True)
        eras = {h['match_era'] for h in hits}
        self.assertNotIn('1990-2009', eras)
        self.assertNotIn('', eras)
        self.assertEqual([h['match'] for h in hits][0], 'A/a2.jpg')

    def test_same_building_flag(self):
        hits = {h['match']: h for h in self.run_query(k=3)}
        self.assertTrue(hits['A/a2.jpg']['same_building'])
        self.assertFalse(hits['B/b1.jpg']['same_building'])

    def test_external_query_reports_unknown_identity(self):
        hits = query([self.matrix[0]], ['<photo.jpg>'],
                     [{'building_id': '<external>', 'capture_era': '',
                       'filename': 'photo.jpg'}],
                     self.ids, self.matrix, self.rows, 2, False, 0.0)
        self.assertTrue(hits)
        self.assertTrue(all(h['same_building'] is None for h in hits))

    def test_min_score_cuts_tail(self):
        hits = self.run_query(k=4, min_score=0.99)
        self.assertEqual([h['match'] for h in hits], ['A/a2.jpg'])

    def test_misaligned_metadata_is_refused(self):
        with self.assertRaises(SystemExit):
            query([self.matrix[0]], ['A/a1.jpg'], [], self.ids, self.matrix,
                  self.rows, 3, False, 0.0)

    def test_identity_follows_the_query_not_the_first_row(self):
        # Regression: querying a building other than rows[0] once reported
        # nodes against rows[0]'s metadata, so every flag was wrong.
        ids = ['A/a1.jpg', 'A/a2.jpg', 'B/b1.jpg', 'B/b2.jpg', 'C/c1.jpg']
        rows = [row('A', '1990-2009'), row('A', '1900-1929'),
                row('B', '1990-2009'), row('B', '1900-1929'), row('C', '2010+')]
        matrix = np.array([[1., 0.], [.9, .1], [.2, 1.], [.1, .9], [0., 1.]],
                          dtype='float32')
        matrix /= np.linalg.norm(matrix, axis=1, keepdims=True)
        hits = query([matrix[2]], ['B/b1.jpg'], [rows[2]], ids, matrix, rows,
                     4, False, 0.0)
        flags = {h['match']: h['same_building'] for h in hits}
        self.assertTrue(flags['B/b2.jpg'], 'same building must be recognised')
        self.assertFalse(flags['A/a2.jpg'], 'another building must not be')
        # And the era filter must use the query's era (1990-2009), not rows[0]'s.
        cross = query([matrix[2]], ['B/b1.jpg'], [rows[2]], ids, matrix, rows,
                      4, True, 0.0)
        self.assertEqual([h['match'] for h in cross][0], 'B/b2.jpg')
        self.assertTrue(all(h['match_era'] != '1990-2009' for h in cross))


if __name__ == '__main__':
    unittest.main()
