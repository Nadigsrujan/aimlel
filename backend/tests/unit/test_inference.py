"""A serialized local checkpoint reproduces online scores and rejects schema drift."""

import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
import torch
from neural_cartographer.learning import inference
from neural_cartographer.learning.heterogeneous import (
    HeterogeneousImpactModel,
    PAIR_FEATURES,
    RELATIONS,
)
from neural_cartographer.features.history import enrich, FEATURE_VERSION


class InferenceTests(unittest.TestCase):
    def test_checkpoint_roundtrip_and_schema_rejection(self):
        graph = {
            "nodes": [
                {"id": "a.py", "path": "a.py", "kind": "file"},
                {"id": "b.py", "path": "b.py", "kind": "file"},
            ],
            "edges": [],
        }
        rows, _ = enrich([{"path": "b.py", "score": 0}], graph, "a.py", [])
        model = HeterogeneousImpactModel()
        metadata = {
            "feature_names": list(PAIR_FEATURES),
            "relations": list(RELATIONS),
            "provenance": {"feature_version": FEATURE_VERSION},
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "model.pt"
            torch.save({"state_dict": model.state_dict(), "metadata": metadata}, path)
            with patch.object(inference, "checkpoint_path", return_value=path):
                result = inference.score(
                    {"graph": graph, "seed": "a.py", "candidates": rows}
                )
                self.assertGreaterEqual(result["candidates"][0]["score"], 0)
                self.assertLessEqual(result["candidates"][0]["score"], 1)
                first = result["candidates"][0]["score"]
                self.assertEqual(
                    first, inference.score(result)["candidates"][0]["score"]
                )
                metadata["feature_names"] = []
                torch.save(
                    {"state_dict": model.state_dict(), "metadata": metadata}, path
                )
                with self.assertRaisesRegex(ValueError, "incompatible"):
                    inference.score(result)
