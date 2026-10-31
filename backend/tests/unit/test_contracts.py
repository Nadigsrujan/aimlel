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
from contracts import entity_records, provenance


class RevisionContractTests(unittest.TestCase):
    def test_line_shift_and_duplicate_symbols(self):
        graph = {'nodes': [{'id': 'a.py::f@2', 'path': 'a.py', 'kind': 'function'},
                           {'id': 'a.py::f@7', 'path': 'a.py', 'kind': 'function'}]}
        rows = entity_records(graph, 'a/b', 'revision')
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        graph['nodes'][0]['id'] = 'a.py::f@3'
        self.assertEqual(rows[0]['id'], entity_records(graph, 'a/b', 'revision')[0]['id'])

    def test_configuration_digest_is_order_independent(self):
        self.assertEqual(provenance({}, {'a':1, 'b':2}, '1', '1'),
                         provenance({}, {'b':2, 'a':1}, '1', '1'))
