import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from contracts import identity, artifact_key, changed_entities


class ContractTests(unittest.TestCase):
    def test_rename_and_revision_do_not_collide(self):
        original = identity('a/b', 'sha1', 'a.py', 'f', 'function')
        self.assertNotEqual(original, identity('a/b', 'sha1', 'b.py', 'f', 'function'))
        self.assertNotEqual(original, identity('a/b', 'sha2', 'a.py', 'f', 'function'))

    def test_cutoff_changes_cache_key(self):
        self.assertNotEqual(artifact_key('a/b', 'sha', 1, 1, 'old'), artifact_key('a/b', 'sha', 1, 1, 'new'))

    def test_span_and_file_fallback(self):
        graph = {'nodes': [{'path': 'a.py', 'id': 'f', 'kind': 'function', 'start': 2, 'end': 4}]}
        self.assertEqual(changed_entities(graph, 'a.py', 3, 1), ['f'])
        self.assertEqual(changed_entities(graph, 'a.py', 9, 1), ['a.py'])
        self.assertEqual(changed_entities(graph, 'a.py', 3, 0), ['a.py'])
