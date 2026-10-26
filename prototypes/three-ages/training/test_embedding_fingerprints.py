"""Synthetic CPU cache-builder test: fake encoder, real temporary image bytes."""
import csv
import hashlib
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image


class EmbeddingFingerprintTests(unittest.TestCase):
    def test_hashes_align_with_encoded_ids_across_skips_and_batches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, out = root/'manifest.csv', root/'embeddings.npz'
            rows = []
            expected = {}
            for i in range(4):
                path = root/str(i)/'image.png'
                path.parent.mkdir()
                if i == 1:
                    path.write_bytes(b'not a decodable image')
                else:
                    Image.new('RGB', (3, 3), color=(i * 20, 0, 0)).save(path)
                    expected[f'{i}/image.png'] = hashlib.sha256(path.read_bytes()).hexdigest()
                rows.append(dict(building_id=str(i), filename='image.png', split='train'))
            with manifest.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            class Encoder:
                def eval(self):
                    return self
                def encode_image(self, batch):
                    return torch.column_stack([batch[:, 0], torch.ones(len(batch))])
            def preprocess(image):
                return torch.tensor([float(image.getpixel((0, 0))[0])])
            fake_clip = types.SimpleNamespace(create_model_and_transforms=lambda *a, **k: (Encoder(), None, preprocess))
            script = Path(__file__).resolve().parents[1]/'build_embeddings.py'
            argv = [str(script), '--manifest', str(manifest), '--image-root', str(root),
                    '--out', str(out), '--batch-size', '2', '--device', 'cpu']
            with patch.dict(sys.modules, {'open_clip': fake_clip,
                                          'torchvision': types.SimpleNamespace(__version__='fixture')}), \
                    patch.object(sys, 'argv', argv):
                runpy.run_path(str(script), run_name='__main__')
            with np.load(out, allow_pickle=False) as cache:
                self.assertEqual(dict(zip(cache['ids'].tolist(), cache['image_sha256'].tolist())), expected)
                self.assertEqual(len(cache['embeddings']), 3)
                self.assertEqual(str(cache['manifest_sha256']), hashlib.sha256(manifest.read_bytes()).hexdigest())
                self.assertIn('torchvisionfixture', str(cache['toolchain']))


if __name__ == '__main__':
    unittest.main()
