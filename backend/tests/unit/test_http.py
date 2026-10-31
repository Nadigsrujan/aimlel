"""Exercise request validation and serialization through the actual ASGI app."""
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from fastapi.testclient import TestClient
import api


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_model_schema(self):
        response = self.client.get('/api/v1/models')
        self.assertEqual(response.status_code, 200)
        self.assertIn('combined-v1', response.json()['rankers'])
        self.assertFalse(response.json()['score_is_probability'])

    def test_invalid_top_k_and_missing_repo(self):
        self.assertEqual(self.client.post('/api/v1/analysis', json={'repo':'a/b', 'seed':'a.py', 'top_k':0}).status_code, 422)
        with patch.object(api.serve, 'load_manifests', return_value={}):
            self.assertEqual(self.client.post('/api/v1/analysis', json={'repo':'a/b', 'seed':'a.py'}).status_code, 404)

    def test_private_network_submission_rejected(self):
        for url in ['http://127.0.0.1/a/b', 'https://github.com.evil.example/a/b', 'https://user:pass@github.com/a/b']:
            self.assertEqual(self.client.post('/api/v1/jobs', json={'url':url}).status_code, 422)

    def test_openapi_contains_ranker_and_bounds(self):
        document = self.client.get('/openapi.json').json()
        properties = document['components']['schemas']['Analysis']['properties']
        self.assertIn('ranker', properties)
        self.assertEqual(properties['top_k']['maximum'], 100)
