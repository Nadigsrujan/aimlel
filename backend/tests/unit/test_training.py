import sys
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from train_heterogeneous import sample_indices, macro, channel_examples
from neural_cartographer.learning import train as training
from neural_cartographer.learning.heterogeneous import tensorize
from neural_cartographer.features.history import enrich


class TrainingTests(unittest.TestCase):
    def test_interrupted_training_resumes_identically(self):
        torch.set_num_threads(2)
        graph = {
            "nodes": [
                {"id": p, "path": p, "kind": "file"} for p in ("a.py", "b.py", "c.py")
            ],
            "edges": [],
        }
        rows, _ = enrich(
            [{"path": p, "score": 0} for p in ("b.py", "c.py")], graph, "a.py", []
        )
        example = {
            "repo": "test/repo",
            "commit": "a" * 40,
            "seed": "a.py",
            "positives": ["b.py"],
            "labels": torch.tensor([1.0, 0.0]),
            "batch": tensorize({"graph": graph, "seed": "a.py", "candidates": rows}),
        }
        config = {
            "seed": 17,
            "epochs": 2,
            "learning_rate": 0.003,
            "negative_limit": 2,
            "patience": 3,
        }
        expected, expected_history = training.fit_model([example], [example], config, 0)
        original_measure = training.measure
        calls = 0

        def interrupted(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated interruption")
            return original_measure(*args, **kwargs)

        with tempfile.TemporaryDirectory() as folder:
            with patch.object(training, "measure", side_effect=interrupted):
                with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                    training.fit_model([example], [example], config, 0, Path(folder))
            actual, actual_history = training.fit_model(
                [example], [example], config, 0, Path(folder)
            )
        self.assertEqual(actual_history, expected_history)
        for key, value in expected.state_dict().items():
            torch.testing.assert_close(value, actual.state_dict()[key], rtol=0, atol=0)

    def test_ablation_masks_channels_without_mutating_shared_inputs(self):
        batch = {
            "x": torch.ones((2, 8)),
            "semantic": torch.ones((2, 2)),
            "pairs": torch.ones((1, 7)),
            "edges": {
                "cochange": torch.tensor([[0], [1]]),
                "contains": torch.tensor([[0], [1]]),
            },
        }
        masked = channel_examples([{"batch": batch}], {"semantic"})[0]["batch"]
        self.assertEqual(float(masked["x"][:, :8].sum()), 0)
        self.assertEqual(float(masked["semantic"].sum()), 4)
        self.assertEqual(float(masked["pairs"][:, :6].sum()), 0)
        self.assertEqual(float(masked["pairs"][:, 6].sum()), 1)
        self.assertEqual(masked["edges"]["cochange"].numel(), 0)
        self.assertEqual(masked["edges"]["contains"].numel(), 0)
        self.assertEqual(float(batch["pairs"].sum()), 7)
        self.assertEqual(batch["edges"]["cochange"].numel(), 2)
        history = channel_examples([{"batch": batch}], {"history"})[0]["batch"]
        self.assertEqual(float(history["semantic"].sum()), 0)
        self.assertEqual(float(batch["semantic"].sum()), 4)

    def test_sampling_keeps_all_positives_and_bounds_negatives(self):
        example = {"commit": "a" * 40, "labels": torch.tensor([0.0] * 20 + [1.0, 1.0])}
        indices = sample_indices(example, 6, 17).tolist()
        self.assertEqual(len(indices), 8)
        self.assertTrue({20, 21}.issubset(indices))
        self.assertTrue({0, 1, 2}.issubset(indices))
        self.assertEqual(indices, sample_indices(example, 6, 17).tolist())

    def test_macro_weights_projects_equally(self):
        rows = [
            {"repo": "a", "score": 1},
            {"repo": "a", "score": 1},
            {"repo": "b", "score": 0},
        ]
        self.assertEqual(macro(rows, "score"), 0.5)
