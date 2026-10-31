import sys
from pathlib import Path
import unittest
import tempfile
import json
from unittest.mock import patch
import serve

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from serve import validate_submission, load_manifests


class SubmissionTests(unittest.TestCase):
    def test_restart_marks_running_jobs_failed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text(json.dumps({'one': {'status': 'running', 'repo': 'a/b'}}))
            with patch.object(serve, 'JOB_FILE', path), patch.object(serve, 'JOBS', {}):
                serve.restore_jobs()
                self.assertEqual(serve.JOBS['one']['status'], 'failed')
                self.assertEqual(json.loads(path.read_text())['one']['status'], 'failed')

    def test_invalid_shapes(self):
        for payload in (None, [], 'url', {}, {'url': 3}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                validate_submission(payload)

    def test_public_url(self):
        self.assertEqual(validate_submission({'url': ' https://github.com/a/b.git '})[1], 'a/b')

    def test_held_out_not_exposed(self):
        self.assertTrue(all(m['split'] != 'test' for m in load_manifests().values()))
