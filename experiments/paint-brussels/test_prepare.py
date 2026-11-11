import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from prepare import fetch_reference

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('prepare_batch', ROOT / 'prepare-batch.py')
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


class PrepareTests(unittest.TestCase):
    def test_catalog_matches_local_approved_sources(self):
        self.assertEqual(len(batch.load_catalog(ROOT / 'batch-catalog.json')), 3)

    def test_changed_reference_is_preserved_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'image.jpg'
            path.write_bytes(b'personal replacement')
            with patch('prepare.urllib.request.urlopen') as request:
                with self.assertRaises(SystemExit):
                    fetch_reference(path, 'https://example.invalid/', '0' * 64)
                request.assert_not_called()
            self.assertEqual(path.read_bytes(), b'personal replacement')

    def test_download_must_match_hash_before_any_file_is_created(self):
        data = b'fixture pixels'
        digest = hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / 'nested' / 'source.jpg'
            with patch('prepare.urllib.request.urlopen', return_value=io.BytesIO(b'wrong pixels')):
                with self.assertRaises(SystemExit):
                    fetch_reference(destination, 'https://example.invalid/', digest)
            self.assertFalse(destination.exists())
            with patch('prepare.urllib.request.urlopen', return_value=io.BytesIO(data)):
                fetch_reference(destination, 'https://example.invalid/', digest)
            self.assertEqual(destination.read_bytes(), data)
            with patch('prepare.urllib.request.urlopen') as request:
                fetch_reference(destination, 'https://example.invalid/', digest)
                request.assert_not_called()

    def test_catalog_rejects_unsafe_sources_before_downloading(self):
        original = json.loads((ROOT / 'batch-catalog.json').read_text())
        for key, value in [('file', '../secret.jpg'), ('scene', '../secret.json'),
                           ('image', 'https://evil.example/picture.jpg'),
                           ('image', 'https://user:password@64.media.tumblr.com/picture.jpg'),
                           ('id', None)]:
            data = json.loads(json.dumps(original))
            data['items'][0][key] = value
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'catalog.json'
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    batch.load_catalog(path)


if __name__ == '__main__':
    unittest.main()
