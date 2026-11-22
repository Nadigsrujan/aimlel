"""Paired statistics and portable freeze checks on synthetic inputs."""

import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.evaluation.significance import (
    compare,
    holm,
    paired,
    required_queries,
    sign_flip,
)
from neural_cartographer.learning.portable_freeze import classify


def rows(values):
    return [
        {"repo": repo, "commit": f"{repo}-{index}", "score": value}
        for repo, scores in values.items()
        for index, value in enumerate(scores)
    ]


class PairedTests(unittest.TestCase):
    def test_mismatched_queries_rejected(self):
        with self.assertRaises(ValueError):
            paired(rows({"a": [1, 0]}), rows({"a": [1]}), "score")

    def test_identical_systems_have_no_difference(self):
        data = rows({"a": [0.2, 0.5, 1.0], "b": [0.0, 0.3]})
        result = compare(data, data, "score", iterations=200)
        self.assertEqual(result["difference"], 0)
        self.assertEqual(result["ties"], 5)
        self.assertEqual(result["sign_flip_p"], 1.0)

    def test_macro_weights_repositories_equally(self):
        first = rows({"a": [1, 1, 1, 1], "b": [0]})
        second = rows({"a": [0, 0, 0, 0], "b": [0]})
        self.assertEqual(compare(first, second, "score", 200)["difference"], 0.5)

    def test_consistent_improvement_is_significant(self):
        first = rows({repo: [0.6] * 20 for repo in "abc"})
        second = rows({repo: [0.4] * 20 for repo in "abc"})
        groups = paired(first, second, "score")
        self.assertLess(sign_flip(groups, iterations=2000), 0.01)
        self.assertEqual(sign_flip(groups, 500), sign_flip(groups, 500))

    def test_holm_adjustment(self):
        adjusted = holm({"x": 0.01, "y": 0.04, "z": 0.03})
        self.assertAlmostEqual(adjusted["x"], 0.03)
        self.assertAlmostEqual(adjusted["z"], 0.06)
        self.assertAlmostEqual(adjusted["y"], 0.06)

    def test_required_queries(self):
        # (1.95996 + 0.84162)^2 * (0.3 / 0.05)^2 = 282.5 -> 283
        self.assertEqual(required_queries(0.3, 0.05), 283)


class PortableFreezeTests(unittest.TestCase):
    def test_classifies_line_endings_missing_and_changes(self):
        digest = lambda data: hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "src/a.py").write_bytes(b"x = 1\r\ny = 2\r\n")
            (root / "src/b.py").write_bytes(b"x = 3\n")
            (root / "src/c.pt").write_bytes(b"\x00\r\n")
            (root / "local.json").write_bytes(b"{}\n")
            status = classify(
                {
                    "src/a.py": digest(b"x = 1\ny = 2\n"),
                    "src/b.py": digest(b"x = 1\n"),
                    "src/c.pt": digest(b"\x00\n"),
                    "src/missing.py": digest(b""),
                    "local.json": digest(b"{}\n"),
                },
                root,
                root,
            )
        self.assertEqual(status["line_endings"], ["src/a.py"])
        self.assertEqual(status["changed"], ["src/b.py", "src/c.pt"])
        self.assertEqual(status["missing"], ["src/missing.py"])
        self.assertEqual(status["exact"], ["local.json"])
