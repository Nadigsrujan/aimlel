import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from structure import resolve_imports


class ImportTests(unittest.TestCase):
    def test_relative_and_absolute(self):
        graph = {'nodes': [{'kind': 'file', 'path': p} for p in ['pkg/a.py', 'pkg/b.py']],
                 'edges': [{'source': 'pkg/a.py', 'target': target, 'relation': 'IMPORTS'}
                           for target in ['.b', 'pkg.b', 'external']]}
        resolved, unresolved = resolve_imports(graph)
        self.assertEqual([e['target'] for e in resolved], ['pkg/b.py', 'pkg/b.py'])
        self.assertEqual(unresolved[0]['target'], 'external')

    def test_cannot_traverse_above_package(self):
        graph = {'nodes': [{'kind': 'file', 'path': 'pkg/a.py'}],
                 'edges': [{'source': 'pkg/a.py', 'target': '...other', 'relation': 'IMPORTS'}]}
        self.assertEqual(resolve_imports(graph)[0], [])
    def test_src_layout_and_ambiguous_modules(self):
        graph = {'nodes': [{'kind':'file', 'path':p} for p in ['tests/test_a.py', 'src/pkg/a.py']],
                 'edges': [{'source':'tests/test_a.py', 'target':'pkg.a', 'relation':'IMPORTS'}]}
        resolved, unresolved = resolve_imports(graph)
        self.assertEqual(resolved[0]['target'], 'src/pkg/a.py')
        graph['nodes'].append({'kind':'file', 'path':'pkg/a.py'})
        resolved, unresolved = resolve_imports(graph)
        self.assertEqual(resolved, [])
        self.assertEqual(len(unresolved), 1)
