import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.evidence.explain import explain, select_ids


class ExplanationTests(unittest.TestCase):
    def setUp(self):
        self.result = {"repo": "owner/repo", "seed": "a.py", "graph_revision": "a" * 40}
        self.candidate = {
            "path": "b.py",
            "evidence": {"import_path": ["a.py", "b.py"], "past_commits": ["b" * 40]},
        }

    def test_local_explanation_is_cited_and_provider_free(self):
        with patch("neural_cartographer.evidence.explain.urlopen") as network:
            output = explain(self.result, self.candidate)
        network.assert_not_called()
        self.assertEqual(output["mode"], "deterministic")
        self.assertEqual(
            [row["id"] for row in output["statements"]],
            ["snapshot", "imports", "commit-0"],
        )
        self.assertTrue(
            all(
                row["url"].startswith("https://github.com/owner/repo/")
                for row in output["statements"]
            )
        )

    def test_missing_key_falls_back_and_sparse_evidence_is_explicit(self):
        with patch.dict(os.environ, {}, clear=True):
            output = explain(self.result, {"path": "b.py"}, True)
        self.assertEqual(output["mode"], "deterministic")
        self.assertEqual(output["statements"][-1]["id"], "limited")

    def test_provider_cannot_invent_citations_or_prose(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": '["invented"]'}]}}]}
        ).encode()
        with patch(
            "neural_cartographer.evidence.explain.urlopen", return_value=response
        ):
            with self.assertRaisesRegex(ValueError, "Unsupported evidence citation"):
                select_ids([{"id": "snapshot"}], "unused", "test-model")
        with patch.dict(
            os.environ, {"GEMINI_API_KEY": "unused", "GEMINI_MODEL": "test-model"}
        ):
            with patch(
                "neural_cartographer.evidence.explain.select_ids",
                side_effect=ValueError("secret"),
            ):
                output = explain(self.result, self.candidate, True)
        self.assertEqual(output["mode"], "deterministic")
        self.assertNotIn("secret", json.dumps(output))
