#!/usr/bin/env python3
"""Synthetic near-image diagnostics. No real identity judgements or models."""
import csv
import hashlib
import io
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, PngImagePlugin

TRAINING = Path(__file__).resolve().parent/'three-ages/training'
sys.path.insert(0, str(TRAINING))
from near_image_audit import fingerprint, decoded_groups, near_candidates, audit, safe_path
from sequence_metadata import sequence_groups


class NearImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def scene(self, size=(64, 48)):
        image = Image.new('RGB', size)
        image.putdata([((x//5*43+y//7*17)%256, (x*9+y*5)%256, (x*3+y*13)%256)
                       for y in range(size[1]) for x in range(size[0])])
        return image

    def row(self, name, split='train', pole='pub', image=None, **save_options):
        path = self.root/f'{name}.png'
        (image if image is not None else self.scene()).save(path, **save_options)
        return {'_id': f'{pole}/{name}/image.png', '_path': path, '_pole': pole,
                'building_id': name, 'filename': 'image.png', 'split': split,
                'source_filename': name}

    def test_metadata_reencoding_is_decoded_equivalent_not_file_identical(self):
        a = self.row('a')
        info = PngImagePlugin.PngInfo()
        info.add_text('description', 'different file metadata')
        b = self.row('b', 'test', pnginfo=info)
        records = [fingerprint(a), fingerprint(b)]
        self.assertNotEqual(records[0]['file_sha256'], records[1]['file_sha256'])
        self.assertEqual(records[0]['decoded_sha256'], records[1]['decoded_sha256'])
        self.assertEqual(records[0]['model_rgb_sha256'], records[1]['model_rgb_sha256'])
        self.assertTrue(decoded_groups(records)[0]['cross_split'])

    def test_resize_is_only_perceptual_candidate_not_automatic_identity(self):
        a = self.row('a')
        b = self.row('b', 'test', image=self.scene().resize((128, 96), Image.Resampling.NEAREST))
        records = [fingerprint(a), fingerprint(b)]
        self.assertTrue(all(r['near_eligible']=='1' for r in records))
        self.assertNotEqual(records[0]['decoded_sha256'], records[1]['decoded_sha256'])
        result = near_candidates(records)
        self.assertEqual(result['retained_pairs'], 1)
        self.assertIn('no identity', result['candidates'][0]['meaning'])

    def test_raw_model_pixels_and_display_orientation_are_distinct(self):
        plain = self.row('plain')
        exif = Image.Exif()
        exif[274] = 6
        tagged = self.row('tagged', 'test', exif=exif)
        a, b = fingerprint(plain), fingerprint(tagged)
        self.assertEqual(a['model_rgb_sha256'], b['model_rgb_sha256'])
        self.assertNotEqual(a['decoded_sha256'], b['decoded_sha256'])
        rotated = self.row('rotated', image=self.scene().transpose(Image.Transpose.ROTATE_270))
        c = fingerprint(rotated)
        self.assertEqual(b['decoded_sha256'], c['decoded_sha256'])
        self.assertNotEqual(b['model_rgb_sha256'], c['model_rgb_sha256'])

    def test_alpha_difference_not_mistaken_for_display_pixel_identity(self):
        a = self.row('transparent', image=Image.new('RGBA', (20, 20), (255, 0, 0, 0)))
        b = self.row('opaque', 'test', image=Image.new('RGBA', (20, 20), (255, 0, 0, 255)))
        x, y = fingerprint(a), fingerprint(b)
        self.assertEqual(x['model_rgb_sha256'], y['model_rgb_sha256'])
        self.assertNotEqual(x['decoded_sha256'], y['decoded_sha256'])
        self.assertEqual(decoded_groups([x,y]), [])

    def test_failures_limits_and_flat_hashes_are_explicit(self):
        row = self.row('bad')
        row['_path'].write_bytes(b'not an image')
        self.assertEqual(fingerprint(row)['status'], 'decode_error')
        row['_path'].unlink()
        self.assertEqual(fingerprint(row)['status'], 'read_error')
        valid = self.row('valid')
        self.assertEqual(fingerprint(valid, max_bytes=1)['status'], 'byte_limit')
        self.assertEqual(fingerprint(valid, max_pixels=4)['status'], 'pixel_limit')
        flat = fingerprint(self.row('flat', image=Image.new('RGB', (20, 20), 'white')))
        self.assertEqual(flat['status'], 'ok')
        self.assertEqual(flat['near_eligible'], '0')
        self.assertTrue(flat['decoded_sha256'])
        with patch.object(Image, 'MAX_IMAGE_PIXELS', 1000):
            self.assertEqual(fingerprint(valid)['status'], 'decode_error')

    def test_growing_file_read_is_hard_bounded(self):
        row = self.row('growing')
        class GrowingStream(io.BytesIO):
            requested = None
            def read(self, size=-1):
                self.requested = size
                return super().read(size)
        stream = GrowingStream(b'x'*10000)
        with patch.object(Path, 'stat') as stat, patch.object(Path, 'open', return_value=stream):
            stat.return_value.st_size = 1
            result = fingerprint(row, max_bytes=100)
        self.assertEqual(stream.requested, 101)
        self.assertEqual(result['status'], 'byte_limit')
        self.assertEqual(result['file_sha256'], '')

    def test_multiple_frames_are_not_silently_reduced_to_first_frame(self):
        path = self.root/'animated.gif'
        self.scene().save(path, save_all=True, append_images=[Image.new('RGB',(64,48),'black')], format='GIF')
        row = dict(self.row('a'), _path=path)
        result = fingerprint(row)
        self.assertEqual(result['status'], 'unsupported_multiframe')
        self.assertEqual(result['decoded_sha256'], '')

    def fake_records(self, hashes):
        return [{'id': f'{i:04}', 'status': 'ok', 'near_eligible': '1', 'split': 'train' if i%2==0 else 'val',
                 'dhash64': f'{value:016x}', 'decoded_sha256': f'{i:064x}'} for i,value in enumerate(hashes)]

    def test_banded_index_matches_bruteforce_for_every_supported_radius(self):
        rng = random.Random(42)
        values = []
        for _ in range(30):
            value = rng.getrandbits(64)
            values.append(value)
            for distance in range(5):
                change = sum(1 << bit for bit in rng.sample(range(64), distance))
                values.append(value ^ change)
        records = self.fake_records(values)
        for radius in range(5):
            actual = near_candidates(records, radius=radius, max_candidates=100000)
            pairs = {(p['left'],p['right']) for p in actual['candidates']}
            expected = {(a['id'],b['id']) for i,a in enumerate(records) for b in records[i+1:]
                        if a['split'] != b['split'] and (int(a['dhash64'],16)^int(b['dhash64'],16)).bit_count()<=radius}
            self.assertEqual(pairs, expected, radius)
            self.assertTrue(actual['hash_pair_search_complete_for_eligible_images'])

    def test_budgets_are_reported_not_confused_with_absence(self):
        records = self.fake_records([0x5a5a5a5a5a5a5a5a]*8)
        limited = near_candidates(records, max_visits=1)
        self.assertTrue(limited['comparison_budget_exhausted'])
        self.assertFalse(limited['hash_pair_search_complete_for_eligible_images'])
        retained = near_candidates(records, max_candidates=1)
        self.assertTrue(retained['candidate_list_truncated'])
        self.assertEqual(retained['retained_pairs'], 1)
        self.assertEqual(retained['candidate_matches_observed'], 16)

    def test_smoke_scope_never_becomes_full_corpus_or_sequence_proof(self):
        pub = [self.row(f'p{i}', 'train') for i in range(3)]
        mmap = [self.row(f'm{i}', 'val', 'map') for i in range(3)]
        before = [dict(r) for r in pub+mmap]
        report, records = audit(pub, mmap, limit_per_pole=1)
        self.assertEqual(len(records), 2)
        self.assertFalse(report['scope']['complete_image_decode_scan'])
        self.assertEqual(report['overall_isolation'], 'not established by this diagnostic')
        self.assertEqual(report['sequence_evidence'], sequence_groups(mmap))
        self.assertEqual(pub+mmap, before)

    def test_invalid_parameters_refuse_before_decoding(self):
        with patch('near_image_audit.fingerprint') as decode:
            for kwargs in [{'radius':5}, {'max_visits':0}, {'max_pixels':0}, {'limit_per_pole':0}]:
                with self.assertRaises(ValueError):
                    audit([], [], **kwargs)
            decode.assert_not_called()

    def test_path_traversal_and_outside_symlinks_refuse(self):
        with self.assertRaises(ValueError):
            safe_path(self.root, 'a', '../secret')
        outside = self.root.parent/(self.root.name+'-outside')
        outside.mkdir()
        self.addCleanup(outside.rmdir)
        (self.root/'linked').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            safe_path(self.root, 'linked', 'photo.jpg')

    def test_cli_outputs_are_new_and_sources_are_preserved(self):
        manifests=[]
        for pole in ['pub','map']:
            root=self.root/pole
            root.mkdir()
            rows=[]
            for i in range(2):
                bid=str(i)
                (root/bid).mkdir()
                self.scene().save(root/bid/'photo.png')
                rows.append(dict(building_id=bid,filename='photo.png',source_filename=f'{pole}{i}',split='train' if i==0 else 'test'))
            path=self.root/f'{pole}.csv'
            with path.open('w',newline='') as handle:
                writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            manifests.append(path)
        original={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        out=self.root/'audit'
        cmd=[sys.executable,str(TRAINING/'near_image_audit.py'),'--publisher-manifest',str(manifests[0]),
             '--mapillary-manifest',str(manifests[1]),'--publisher-root',str(self.root/'pub'),
             '--mapillary-root',str(self.root/'map'),'--out-dir',str(out)]
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        report=json.loads((out/'audit.json').read_text())
        self.assertEqual(report['decoded_cross_split_groups'],1)
        self.assertEqual({p:p.read_bytes() for p in original},original)
        outputs={p.name:p.read_bytes() for p in out.iterdir()}
        result=subprocess.run(cmd,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},outputs)


if __name__ == '__main__':
    unittest.main()
