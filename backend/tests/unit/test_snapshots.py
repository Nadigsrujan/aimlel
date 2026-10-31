import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from analyze import analyze
from ingest import ROOT
from snapshots import build_snapshot


class SnapshotTests(unittest.TestCase):
    def test_historical_query_uses_parent_and_excludes_seed(self):
        manifest_path = ROOT / 'data/manifests/pallets__flask.json'
        if not manifest_path.exists():
            self.skipTest('Local Flask corpus not installed')
        manifest = json.loads(manifest_path.read_text())
        source = ROOT / 'data/processed/pallets__flask' / manifest['revision'] / 'queries.jsonl'
        with source.open() as stream:
            query = json.loads(next(stream))
        result = analyze('pallets/flask', query['seed'], query['commit'])
        self.assertEqual(result['graph_revision'], query['graph_revision'])
        self.assertNotEqual(result['graph_revision'], query['commit'])
        self.assertNotIn(query['seed'], [item['path'] for item in result['candidates']])

    def test_batch_graph_matches_ingested_graph(self):
        manifest_path = ROOT / 'data/manifests/pallets__flask.json'
        if not manifest_path.exists():
            self.skipTest('Local Flask corpus not installed')
        manifest = json.loads(manifest_path.read_text())
        expected = json.loads((ROOT / 'data/processed/pallets__flask' / manifest['revision'] / 'graph.json').read_text())
        actual = build_snapshot(ROOT / 'data/raw/pallets__flask', manifest['revision'])
        self.assertEqual(actual['nodes'], expected['nodes'])
        self.assertEqual(actual['edges'], expected['edges'])
