import sys
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
try:
    import api
    from fastapi import HTTPException
except ImportError:
    api = None


@unittest.skipIf(api is None, 'API dependencies not installed')
class ApiTests(unittest.TestCase):
    def test_top_k_rejected(self):
        with self.assertRaises(ValueError):
            api.Analysis(repo='a/b', seed='a.py', top_k=101)

    def test_unavailable_repository(self):
        with patch.object(api.serve, 'load_manifests', return_value={}):
            with self.assertRaises(HTTPException) as context:
                api.analysis(api.Analysis(repo='a/b', seed='a.py'))
            self.assertEqual(context.exception.status_code, 404)

    def test_archive_is_recoverable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / 'data/manifests'
            manifests.mkdir(parents=True)
            manifest = manifests / 'a__b.json'
            manifest.write_text(json.dumps({'repo': 'a/b', 'split': 'submitted'}))
            raw = root / 'data/raw/a__b'
            raw.mkdir(parents=True)
            (raw / 'marker').write_text('preserve me')
            with patch.object(api, 'ROOT', root), patch.object(api.serve, 'JOBS', {}):
                result = api.delete_repository('a', 'b')
            self.assertFalse(manifest.exists())
            archived = root / result['recovery_path']
            self.assertEqual((archived / 'raw/marker').read_text(), 'preserve me')
            self.assertTrue((archived / 'manifest.json').exists())

    def test_catalog_deletion_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifests = root / 'data/manifests'
            manifests.mkdir(parents=True)
            (manifests / 'a__b.json').write_text(json.dumps({'repo': 'a/b', 'split': 'train'}))
            with patch.object(api, 'ROOT', root), self.assertRaises(HTTPException) as context:
                api.delete_repository('a', 'b')
            self.assertEqual(context.exception.status_code, 409)
