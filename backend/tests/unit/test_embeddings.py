import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import hashlib
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from embeddings import index_directory
from neural_cartographer.features import embeddings


class EmbeddingTests(unittest.TestCase):
    def test_unchanged_blob_reuses_vector_across_revisions(self):
        import torch

        class Tokenizer:
            def __call__(self, texts, **kwargs):
                return {"attention_mask": torch.ones((len(texts), 2), dtype=torch.long)}

        class Encoder:
            calls = 0

            def __call__(self, attention_mask):
                self.calls += 1
                return SimpleNamespace(
                    last_hidden_state=torch.ones((*attention_mask.shape, 3))
                )

        model = Encoder()
        config = {
            "model": "fixture",
            "revision": "a" * 40,
            "max_tokens": 2,
            "batch_size": 2,
        }
        with tempfile.TemporaryDirectory() as folder:

            def make_index(command, **kwargs):
                (Path(command[-1]) / "vectors.index").write_bytes(b"fixture-index")

            with (
                patch.object(embeddings, "ROOT", Path(folder)),
                patch.object(embeddings, "configuration", return_value=config),
                patch.object(embeddings, "encoder", return_value=(Tokenizer(), model)),
                patch.object(
                    embeddings,
                    "git",
                    return_value=b"100644 blob " + b"a" * 40 + b"\tone.py\0",
                ),
                patch.object(
                    embeddings,
                    "blob_reader",
                    side_effect=lambda repo: nullcontext(lambda blob: b"x=1"),
                ),
                patch.object(embeddings.subprocess, "run", side_effect=make_index),
            ):
                first = embeddings.build("a/b", "a" * 40)
                second = embeddings.build("a/b", "b" * 40)
                self.assertEqual(model.calls, 1)
                self.assertEqual(first["vectors_sha256"], second["vectors_sha256"])
                self.assertEqual(
                    embeddings.load_vectors("a/b", "b" * 40)["one.py"].shape, (3,)
                )

    def test_matrix_checksum_and_revision_are_required(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            matrix = root / "vectors.npy"
            np.save(matrix, np.array([[1.0, 0.0]], dtype="float32"))
            metadata = {
                "revision": "a" * 40,
                "history_cutoff": "a" * 40,
                "paths": ["a.py"],
                "dimension": 2,
                "vectors_sha256": hashlib.sha256(matrix.read_bytes()).hexdigest(),
            }
            (root / "manifest.json").write_text(json.dumps(metadata))
            with patch.object(embeddings, "index_directory", return_value=root):
                self.assertEqual(
                    embeddings.load_vectors("a/b", "a" * 40)["a.py"].tolist(),
                    [1.0, 0.0],
                )
                with self.assertRaisesRegex(ValueError, "cutoff"):
                    embeddings.load_vectors("a/b", "b" * 40)
                matrix.write_bytes(b"corrupt")
                with self.assertRaisesRegex(ValueError, "checksum"):
                    embeddings.load_vectors("a/b", "a" * 40)

    def test_cutoff_changes_index_directory(self):
        self.assertNotEqual(
            index_directory("a/b", "a" * 40), index_directory("a/b", "b" * 40)
        )
        with self.assertRaises(ValueError):
            index_directory("../outside", "a" * 40)

    def test_isolated_index_search_matches_cosine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            np.save(
                root / "vectors.npy",
                np.array([[1, 0], [0, 1], [0.8, 0.6]], dtype="float32"),
            )
            script = Path(__file__).resolve().parents[3] / "scripts/vector_index.py"
            subprocess.run(
                [sys.executable, str(script), "build", directory], check=True
            )
            result = json.loads(
                subprocess.check_output(
                    [sys.executable, str(script), "query", directory, "0"]
                )
            )
            self.assertEqual([item[0] for item in result], [0, 2, 1])
            self.assertAlmostEqual(result[1][1], 0.8, places=6)
