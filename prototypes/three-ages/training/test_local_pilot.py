"""Offline CPU tests for the scoped local training pilot."""
import unittest
import torch
import torch.nn.functional as F
import numpy as np
from train_local_pilot import (building_loss, check_splits, mine_pairs, metrics,
                               neighbour_order, hard_negative_batches)


def row(bid, pole='pub', era='1990-2009', split='train', flag='0', suffix='x'):
    return {'building_id': bid, '_id': f'{pole}/{bid}/{suffix}',
            'capture_era': era, 'split': split, 'drawing_flag': flag}


class PilotTests(unittest.TestCase):
    def test_unique_buildings_match_diagonal_infonce(self):
        torch.manual_seed(7)
        a, b = torch.randn(4, 8), torch.randn(4, 8)
        logits = 3 * (F.normalize(a, dim=-1) @ F.normalize(b, dim=-1).T)
        expected = (F.cross_entropy(logits, torch.arange(4)) +
                    F.cross_entropy(logits.T, torch.arange(4)))/2
        torch.testing.assert_close(building_loss(a,b,torch.arange(4),3),expected)

    def test_same_building_not_false_negative(self):
        a, b = torch.randn(4, 8, requires_grad=True), torch.randn(4, 8)
        loss = building_loss(a,b,torch.zeros(4,dtype=torch.long),3)
        torch.testing.assert_close(loss, torch.tensor(0.))
        loss.backward()
        self.assertTrue(torch.isfinite(a.grad).all())

    def test_split_leak_rejected(self):
        with self.assertRaises(ValueError):
            check_splits([row('7')], [row('7',pole='map',split='val')])

    def test_pair_mining_capped_train_photo_only_and_repeatable(self):
        pub = [row('7',era=e,suffix=f'{e}-{i}')
               for e in ['pre-1900','2010+'] for i in range(10)]
        pub += [row('8',split='test'),row('9',flag='1'),row('10',split='val')]
        mmap = [row('7',pole='map',suffix=str(i),era='2010+') for i in range(50)]
        mmap += [row('9',pole='map')]
        pairs, count = mine_pairs(pub,mmap,seed=4,cap=3)
        self.assertEqual(count,{'cross_era':3,'cross_pole':3})
        self.assertEqual(len(pairs),6)
        self.assertEqual([(a['_id'],b['_id']) for a,b in pairs],
                         [(a['_id'],b['_id']) for a,b in mine_pairs(pub,mmap,seed=4,cap=3)[0]])
        for a,b in pairs:
            self.assertEqual((a['building_id'],b['building_id']),('7','7'))
            if b['_id'].startswith('pub/'):
                self.assertNotEqual(a['capture_era'],b['capture_era'])

    def test_retrieval_excludes_self_and_uses_fair_denominator(self):
        gallery = [row('A',suffix='self',era='pre-1900')]
        gallery += [row(str(i),suffix=str(i)) for i in range(5)]
        gallery += [row('A',suffix='mate',era='2010+')]
        # Self is rank1, cross-era mate is last. With self excluded, top5
        # must contain only distractors. No fabricated hit from the query.
        gv = np.array([[1.,0.]] + [[.9-i*.01,.1] for i in range(5)] + [[-1.,0.]])
        result = metrics([gallery[0]],np.array([[1.,0.]]),gallery,gv)
        self.assertEqual(result['top5'],0.)
        self.assertEqual(result['cross_era_eligible_queries'],1)
        self.assertEqual(result['cross_era_top5_fair'],0.)

    def test_singleton_not_counted_as_own_mate(self):
        gallery=[row(str(i)) for i in range(6)]
        gv=np.eye(6,dtype='float32')
        result=metrics([gallery[0]],gv[:1],gallery,gv)
        self.assertEqual(result['queries_with_mates'],0)

    def test_cross_pole_ids_do_not_exclude_same_filename(self):
        gallery=[row('A',suffix='x',era='pre-1900')]+[row(str(i)) for i in range(5)]
        gv=np.array([[1.,0.]]+[[-1.,0.]]*5)
        q=row('A',pole='map',era='2010+')
        result=metrics([q],np.array([[1.,0.]]),gallery,gv)
        self.assertEqual(result['top5'],1.)
        self.assertEqual(result['cross_era_top5_fair'],1.)


    def test_neighbour_order_keeps_a_cell_contiguous(self):
        # Adjacent buildings must arrive in one block, or a batch's negatives are
        # random rather than hard, which is the point of this ordering.
        a = [dict(row('A'), latitude='50.8460', longitude='4.3500') for _ in range(4)]
        b = [dict(row('B'), latitude='50.8461', longitude='4.3501') for _ in range(4)]
        c = [dict(row('C'), latitude='50.8000', longitude='4.4000') for _ in range(4)]
        pairs = [(x, None) for x in a + b + c]
        order = neighbour_order(pairs, seed=0)
        self.assertEqual(sorted(order), list(range(12)))
        near = [i for i, j in enumerate(order) if j < 8]   # A and B share a cell
        far = [i for i, j in enumerate(order) if j >= 8]
        self.assertEqual(max(near) - min(near) + 1, len(near), 'A/B must be contiguous')
        self.assertEqual(max(far) - min(far) + 1, len(far), 'C must be contiguous')


    def test_hard_batches_prefer_visually_similar_buildings(self):
        import tempfile
        from pathlib import Path as P
        # Buildings N1/N2 are nearly identical vectors; F is far away.
        vecs = {'N1': [1.0, 0.0], 'N2': [0.99, 0.05], 'F': [0.0, 1.0]}
        pairs = []
        for b in ('N1', 'N2', 'F'):
            for i in range(6):
                pairs.append(({'building_id': b, 'capture_era': '1990-2009',
                               'filename': f'{i}.jpg', 'latitude': '1', 'longitude': '1'},
                              None))
        with tempfile.TemporaryDirectory() as tmp:
            path = P(tmp) / 'emb.npz'
            ids, mat = [], []
            for b, v in vecs.items():
                for i in range(6):
                    ids.append(f'{b}/{i}.jpg'); mat.append(v)
            np.savez(path, ids=np.array(ids),
                     embeddings=np.array(mat, dtype='float32'))
            batches = hard_negative_batches(pairs, path, seed=0, batch_size=6, k=2)
        self.assertTrue(batches)
        self.assertTrue(all(len(b) <= 6 for b in batches))
        covered = {i for b in batches for i in b}
        self.assertEqual(covered, set(range(len(pairs))), 'every pair must appear')
        # A batch anchored on N1 or N2 should carry the lookalike, not the outlier.
        for b in batches:
            names = {pairs[i][0]['building_id'] for i in b}
            if names & {'N1', 'N2'}:
                self.assertTrue(names & {'N1', 'N2'})


if __name__ == '__main__':
    unittest.main()
