import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from heterogeneous import HeterogeneousImpactModel, tensorize
from features import enrich


class HeterogeneousTests(unittest.TestCase):
    def test_compact_typed_projection_matches_expanded_inputs(self):
        import torch

        model = HeterogeneousImpactModel(semantic_dimension=2)
        batch = {
            "x": torch.randn(4, 8),
            "kinds": torch.tensor([0, 1, 2, 3]),
            "semantic": torch.randn(2, 2),
            "file_indices": torch.tensor([0, 0, 1, 1]),
        }
        expanded = torch.cat(
            (batch["x"], batch["semantic"][batch["file_indices"]]), dim=1
        )
        expected = sum(
            layer(expanded) * (batch["kinds"] == kind).unsqueeze(1)
            for kind, layer in enumerate(model.projections)
        )
        torch.testing.assert_close(model.project_nodes(batch), expected)

    def test_semantic_features_require_complete_snapshot_coverage(self):
        graph = {
            "nodes": [
                {"id": "a.py", "path": "a.py", "kind": "file"},
                {
                    "id": "a.py::f@1",
                    "path": "a.py",
                    "kind": "function",
                    "start": 1,
                    "end": 2,
                },
                {"id": "b.py", "path": "b.py", "kind": "file"},
            ],
            "edges": [],
        }
        rows, _ = enrich([{"path": "b.py", "score": 0}], graph, "a.py", [])
        rows[0]["features"]["semantic_cosine"] = 0.5
        result = {
            "graph": graph,
            "seed": "a.py",
            "candidates": rows,
            "node_embeddings": {"a.py": [1.0, 0.0]},
        }
        with self.assertRaisesRegex(ValueError, "embedding"):
            tensorize(result)
        result["node_embeddings"]["b.py"] = [0.5, 0.5]
        batch = tensorize(result)
        self.assertEqual(batch["x"].shape, (3, 8))
        self.assertEqual(batch["semantic"].shape, (2, 2))
        self.assertEqual(int(batch["file_indices"][0]), int(batch["file_indices"][1]))
        self.assertEqual(float(batch["pairs"][0, -1]), 0.5)
        self.assertEqual(
            HeterogeneousImpactModel(semantic_dimension=2)(batch).shape, (1,)
        )

    def test_node_types_relations_and_gradients(self):
        graph = {
            "nodes": [
                {"id": "a.py", "path": "a.py", "kind": "file"},
                {"id": "test_a.py", "path": "test_a.py", "kind": "file"},
                {
                    "id": "test_a.py::test_f@1",
                    "path": "test_a.py",
                    "kind": "test",
                    "start": 1,
                    "end": 2,
                },
            ],
            "edges": [
                {"source": "test_a.py", "target": "a", "relation": "IMPORTS"},
                {
                    "source": "test_a.py",
                    "target": "test_a.py::test_f@1",
                    "relation": "CONTAINS",
                },
            ],
        }
        rows, _ = enrich([{"path": "test_a.py", "score": 1 / 3}], graph, "a.py", [])
        batch = tensorize({"graph": graph, "seed": "a.py", "candidates": rows})
        self.assertEqual(batch["edges"]["tests"].shape, (2, 1))
        self.assertEqual(batch["edges"]["contains"].shape, (2, 1))
        self.assertEqual(batch["edges"]["cochange"].shape, (2, 0))
        model = HeterogeneousImpactModel()
        logits = model(batch)
        self.assertEqual(logits.shape, (1,))
        logits.sum().backward()
        self.assertIsNotNone(model.projections[3].weight.grad)
        self.assertIsNotNone(model.first.neighbors["tests"].weight.grad)
