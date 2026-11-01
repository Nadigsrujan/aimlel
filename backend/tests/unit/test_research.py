"""Frozen protocol guards must fail before held-out data is opened."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.learning.research import verify_freeze, evaluate
from neural_cartographer.evaluation.metrics import macro_bootstrap


class ResearchProtocolTests(unittest.TestCase):
    def test_frozen_evaluator_records_all_outputs_once(self):
        import torch
        from neural_cartographer.learning.heterogeneous import (
            HeterogeneousImpactModel,
            tensorize,
        )
        from neural_cartographer.features.history import enrich

        graph = {
            "nodes": [
                {"id": p, "path": p, "kind": "file"} for p in ("a.py", "b.py", "c.py")
            ],
            "edges": [],
        }
        rows, _ = enrich(
            [{"path": p, "score": 0} for p in ("b.py", "c.py")], graph, "a.py", []
        )
        batch = tensorize(
            {
                "graph": graph,
                "seed": "a.py",
                "candidates": rows,
                "node_embeddings": {
                    "a.py": [1.0, 0.0],
                    "b.py": [1.0, 0.0],
                    "c.py": [0.0, 1.0],
                },
            }
        )
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / "artifacts/models/heterogeneous-development"
            output.mkdir(parents=True)
            manifests = root / "data/manifests"
            manifests.mkdir(parents=True)
            config = root / "configs"
            config.mkdir()
            repos = ["test/one", "test/two", "test/three"]
            (config / "repositories.json").write_text(json.dumps({"test": repos}))
            for repo in repos:
                (manifests / (repo.replace("/", "__") + ".json")).write_text(
                    json.dumps({"repo": repo, "split": "test"})
                )
            state = {
                "state_dict": HeterogeneousImpactModel(
                    semantic_dimension=2
                ).state_dict(),
                "metadata": {
                    "semantic_dimension": 2,
                    "config": {"use_semantics": True, "training_threads": 2},
                },
            }
            for name in ("model", "static-only", "history-only", "semantic-only"):
                torch.save(state, output / (name + ".pt"))
            (output / "calibration.json").write_text(
                json.dumps({"coefficient": [[1.0]], "intercept": [-2.0]})
            )
            (output / "freeze.json").write_text(
                json.dumps(
                    {
                        "hashes": {
                            "artifacts/models/heterogeneous-development/model.pt": hashlib.sha256(
                                (output / "model.pt").read_bytes()
                            ).hexdigest()
                        },
                        "strongest_baseline": "cochange-v1",
                        "test_commits_per_repo": 1,
                        "classification_threshold": 0.5,
                    }
                )
            )

            def examples(manifest, limit, semantic):
                self.assertTrue(semantic)
                self.assertEqual(limit, 1)
                yield {
                    "repo": manifest["repo"],
                    "commit": "a" * 40,
                    "seed": "a.py",
                    "batch": batch,
                    "rows": rows,
                    "positives": ["b.py"],
                    "labels": torch.tensor([1.0, 0.0]),
                }

            with patch(
                "neural_cartographer.learning.train.examples", side_effect=examples
            ):
                report = evaluate(root)
            self.assertEqual(len(report["comparison"]["heterogeneous"]), 3)
            self.assertEqual(len(report["calibration"]["reliability_bins"]), 10)
            self.assertEqual(len(report["per_repository"]["heterogeneous"]), 3)
            self.assertEqual(report["macro"]["heterogeneous"]["candidate_ceiling"], 1)
            self.assertIsInstance(report["success_gate_met"], bool)
            self.assertTrue((root / "artifacts/reports/final-heldout.json").is_file())
            with self.assertRaisesRegex(ValueError, "already exist"):
                evaluate(root)

    def test_missing_or_changed_freeze_blocks_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(FileNotFoundError):
                evaluate(root)
            output = root / "artifacts/models/heterogeneous-development"
            output.mkdir(parents=True)
            model = root / "model.pt"
            model.write_bytes(b"original")
            (output / "freeze.json").write_text(
                json.dumps(
                    {
                        "hashes": {
                            "model.pt": hashlib.sha256(model.read_bytes()).hexdigest()
                        }
                    }
                )
            )
            self.assertIn("hashes", verify_freeze(root))
            model.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "Frozen artifact changed"):
                evaluate(root)

    def test_macro_interval_weights_projects_equally(self):
        rows = [{"repo": "small", "commit": "a", "metric": 1}] + [
            {"repo": "large", "commit": str(i), "metric": 0} for i in range(100)
        ]
        result = macro_bootstrap(rows, "metric", iterations=100)
        self.assertEqual(result["estimate"], 0.5)
        self.assertEqual(result["repositories"], 2)
