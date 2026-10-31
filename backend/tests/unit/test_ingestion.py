import importlib.util
from pathlib import Path
import unittest
import tempfile
import subprocess
import json

spec = importlib.util.spec_from_file_location("ingest", Path(__file__).resolve().parents[3] / "scripts/ingest.py")
ingest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest)


class IngestionTests(unittest.TestCase):
    def test_nested_entities_have_parent_edges(self):
        nodes, edges, error = ingest.extract("a.py", "class A:\n def method(self):\n  pass\n")
        self.assertIsNone(error)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(edges[1]["source"], nodes[1]["id"])

    def test_unparsable_file_is_audited(self):
        nodes, _, error = ingest.extract("bad.py", "def ???")
        self.assertIsNotNone(error)
        self.assertEqual(nodes[0]["id"], "bad.py")

    def test_filters(self):
        self.assertFalse(ingest.eligible("package/_vendor/a.py"))
        self.assertFalse(ingest.eligible("image.png"))
        self.assertTrue(ingest.eligible("tests/test_api.py"))

    def test_public_url_validation(self):
        self.assertEqual(ingest.public_repo_id("https://github.com/pallets/flask.git"), "pallets/flask")
        for url in ("http://github.com/a/b", "https://github.com.evil.test/a/b",
                    "https://github.com/a/b?x=1", "https://github.com/a/b/c"):
            with self.assertRaises(ValueError):
                ingest.public_repo_id(url)

    def test_relative_import_preserved(self):
        _, edges, _ = ingest.extract("pkg/a.py", "from .utils import helper")
        self.assertEqual(edges[0]["target"], ".utils")

    def test_modern_python_fallback(self):
        if ingest.tree_sitter is None:
            self.skipTest("Tree-sitter is not installed")
        nodes, edges, error = ingest.extract("modern.py", b"def identity[T](value: T) -> T:\n    return value\n")
        self.assertIsNone(error)
        self.assertEqual(nodes[1]["kind"], "function")
        self.assertEqual(edges[0]["relation"], "CONTAINS")

    def test_end_to_end_queries_point_to_parent(self):
        original = ingest.ROOT
        with tempfile.TemporaryDirectory() as temporary:
            ingest.ROOT = Path(temporary)
            repo = ingest.ROOT / "data/raw/example__fixture"
            repo.mkdir(parents=True)
            def command(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args])
            try:
                command("init", "-q")
                command("config", "user.name", "Fixture")
                command("config", "user.email", "fixture@example.invalid")
                command("remote", "add", "origin", "https://github.com/example/fixture.git")
                for filename in ("a.py", "b.py"):
                    (repo / filename).write_text("value = 1\n")
                command("add", ".")
                command("commit", "-qm", "initial")
                parent = command("rev-parse", "HEAD").decode().strip()
                for filename in ("a.py", "b.py"):
                    (repo / filename).write_text("value = 2\n")
                command("commit", "-qam", "change pair")
                for filename in ("a.py", "b.py"):
                    (repo / filename).write_text("value  =  2\n")
                command("commit", "-qam", "format pair")
                result = ingest.process("example/fixture", "train")
                self.assertEqual(result["queries"], 2)
                queries = Path(result["summary"]).with_name("queries.jsonl")
                for line in queries.read_text().splitlines():
                    row = json.loads(line)
                    self.assertEqual(row["graph_revision"], parent)
                    self.assertNotIn(row["seed"], row["positives"])
                    self.assertFalse(row["features_materialized"])
                for filename in ("a.py", "b.py"):
                    (repo / filename).write_text("def f(x):\n if x:\n  x = 2\n return x\n")
                command("commit", "-qam", "blocks")
                for filename in ("a.py", "b.py"):
                    (repo / filename).write_text("def f(x):\n if x:\n  x = 2\n  return x\n")
                command("commit", "-qam", "semantic indentation")
                self.assertEqual(len(list(ingest.history(repo, "HEAD"))[-1]["changes"]), 2)
            finally:
                ingest.ROOT = original


if __name__ == "__main__":
    unittest.main()
