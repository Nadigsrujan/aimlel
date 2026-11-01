import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.ingest.pipeline import extract
from neural_cartographer.graph.relations import lexical_edges


class LexicalRelationsTests(unittest.TestCase):
    def edges(self, source):
        nodes, _, error = extract("a.py", source)
        self.assertIsNone(error)
        return lexical_edges("a.py", source, nodes)

    def test_direct_calls_and_inheritance(self):
        edges, audit = self.edges(
            "def target(): pass\ndef caller(): return target()\nclass Base: pass\nclass Child(Base): pass\n"
        )
        self.assertEqual({e["relation"] for e in edges}, {"CALLS", "INHERITS"})
        self.assertTrue(
            any(
                e["source"].startswith("a.py::caller@")
                and e["target"].startswith("a.py::target@")
                for e in edges
            )
        )
        self.assertEqual(audit["resolved_calls"], 1)

    def test_shadowing_dynamic_calls_and_closures_remain_unresolved(self):
        source = "def target(): pass\ndef caller(target): return target()\ndef outer():\n target=lambda: 1\n def inner(): return target()\n return inner\nclass C:\n target=lambda: 1\n value=target()\nx=lambda target: target()\nobj.target()\n"
        edges, audit = self.edges(source)
        self.assertEqual(edges, [])
        self.assertGreater(audit["calls"], 0)

    def test_class_namespace_does_not_shadow_a_method_global(self):
        edges, _ = self.edges(
            "def target(): pass\nclass C:\n target=1\n def method(self): return target()\n"
        )
        self.assertEqual(len(edges), 1)
        self.assertIn("::method@", edges[0]["source"])

    def test_rebound_deleted_or_decorated_symbols_are_not_claimed(self):
        for source in [
            "def target(): pass\ntarget=lambda:1\ntarget()\n",
            "def target(): pass\ndel target\ntarget()\n",
            "@decorator\ndef target(): pass\ntarget()\n",
        ]:
            edges, _ = self.edges(source)
            self.assertEqual(edges, [])
