import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from map_changes import map_changes


class MappingTests(unittest.TestCase):
    def test_nested_modification_and_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', '-C', directory, *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init')
            git('config', 'user.name', 'Fixture')
            git('config', 'user.email', 'fixture@example.invalid')
            (repo / 'old.py').write_text('class Example:\n    def method(self):\n        return 1\n')
            git('add', '.')
            git('commit', '-m', 'initial')
            (repo / 'old.py').rename(repo / 'new.py')
            git('add', '-A')
            git('commit', '-m', 'rename')
            renamed = map_changes(repo, git('rev-parse', 'HEAD'))
            self.assertEqual(renamed['files'][0]['alias']['to'], 'new.py')
            self.assertEqual(renamed['files'][0]['alias']['similarity_percent'], 100)
            (repo / 'new.py').write_text('class Example:\n    def method(self):\n        return 2\n')
            git('add', '.')
            git('commit', '-m', 'modify')
            mapped = map_changes(repo, git('rev-parse', 'HEAD'))
            self.assertEqual(mapped['coverage']['symbol_mapped'], 1)
            self.assertTrue(any('method' in entity for entity in mapped['files'][0]['parent_entities']))

    def test_insertion_and_deletion_fall_back_safely(self):
        from contracts import changed_entities
        graph = {'nodes': [{'id':'a.py::f@2', 'path':'a.py', 'kind':'function', 'start':2, 'end':4}]}
        self.assertEqual(changed_entities(graph, 'a.py', 0, 0), ['a.py'])
        self.assertEqual(changed_entities(graph, 'a.py', 5, 1), ['a.py'])
