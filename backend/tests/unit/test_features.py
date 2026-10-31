import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import tempfile
import json
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from features import enrich, past_events, rerank, RANKERS


class FeatureTests(unittest.TestCase):
    def test_unreachable_future_commits_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'events.jsonl'
            path.write_text('\n'.join(json.dumps({'commit': sha, 'changes': []}) for sha in ['past', 'future']))
            with patch('features.git', return_value=b'past\n'):
                self.assertEqual([e['commit'] for e in past_events(None, 'cutoff', path)], ['past'])

    def test_evidence_channels(self):
        graph = {'nodes': [{'kind': 'file', 'path': p} for p in ['a.py', 'b.py']],
                 'edges': [{'source': 'a.py', 'target': 'b', 'relation': 'IMPORTS'}]}
        events = [{'commit': 'past', 'changes': [{'path': p, 'status': 'M'} for p in ['a.py', 'b.py']]}]
        rows, _ = enrich([{'path': 'b.py', 'distance': 2, 'score': 1/3}], graph, 'a.py', events)
        self.assertEqual(rows[0]['evidence']['import_path'], ['a.py', 'b.py'])
        self.assertEqual(rows[0]['features']['past_cochange_count'], 1)
        self.assertEqual(rows[0]['evidence']['past_commits'], ['past'])

    def test_history_ranks_before_top_k_and_preserves_pool(self):
        graph = {'nodes': [{'kind': 'file', 'path': p} for p in ['a.py', 'b.py', 'far/c.py']], 'edges': []}
        events = [{'commit': 'past', 'changes': [{'path': p, 'status': 'M'} for p in ['a.py', 'far/c.py']]}]
        rows, _ = enrich([{'path': 'b.py', 'score': 1/3}, {'path': 'far/c.py', 'score': 1/4}], graph, 'a.py', events)
        self.assertEqual(rerank(rows, 'cochange-v1', 'a.py')[0]['path'], 'far/c.py')
        for name in RANKERS:
            self.assertEqual({r['path'] for r in rerank(rows, name, 'a.py')}, {'b.py', 'far/c.py'})
        self.assertEqual(rows[1]['features']['cochange_jaccard'], 1)
        self.assertEqual(rows[0]['features']['commits_since_change'], None)

    def test_unknown_ranker_rejected(self):
        with self.assertRaises(ValueError):
            rerank([], 'imaginary-model', 'a.py')
