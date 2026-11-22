"""v2 sampling, baselines, fusion and freeze guards on synthetic inputs."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.learning import research_v2
from neural_cartographer.learning.research_v2 import (
    fuse,
    one_seed_per_commit,
    rose,
    sample,
)


def write_queries(root, repo, commits):
    folder = root / "data/processed" / repo.replace("/", "__") / "rev"
    folder.mkdir(parents=True)
    with (folder / "queries.jsonl").open("w") as stream:
        for commit in commits:
            for seed in ("a.py", "b.py"):
                stream.write(json.dumps({"commit": commit, "seed": seed}) + "\n")
    return {"repo": repo, "revision": "rev"}


class SamplingTests(unittest.TestCase):
    def test_sample_is_seeded_and_stream_specific(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = write_queries(root, "o/r", [f"{i:040x}" for i in range(200)])
            first = sample(manifest, 20, "train", 17, root)
            self.assertEqual(first, sample(manifest, 20, "train", 17, root))
            self.assertNotEqual(first, sample(manifest, 20, "test", 17, root))
            self.assertEqual(len({q["commit"] for q in first}), 20)
            self.assertEqual(len(sample(manifest, 999, "train", 17, root)), 200)

    def test_one_seed_per_commit(self):
        queries = [{"commit": "c", "seed": s} for s in ("x.py", "y.py", "z.py")]
        chosen = one_seed_per_commit(queries)
        self.assertEqual(list(chosen), ["c"])
        self.assertEqual(chosen, one_seed_per_commit(reversed(queries)))


class RankingTests(unittest.TestCase):
    def test_rose_orders_by_support(self):
        rows = [
            {"path": "b", "features": {"past_cochange_count": 2}},
            {"path": "a", "features": {"past_cochange_count": 0}},
            {"path": "c", "features": {"past_cochange_count": 5}},
            {"path": "d", "features": {"past_cochange_count": 2}},
        ]
        self.assertEqual(rose(rows), ["c", "b", "d", "a"])

    def test_fusion_endpoints_and_mismatch(self):
        first, second = ["a", "b", "c"], ["c", "b", "a"]
        self.assertEqual(fuse(first, second, 0.0), first)
        self.assertEqual(fuse(first, second, 1.0), second)
        self.assertEqual(sorted(fuse(first, second, 0.5)), ["a", "b", "c"])
        with self.assertRaises(ValueError):
            fuse(first, ["a", "b"], 0.5)


class LossTests(unittest.TestCase):
    def test_bpr_prefers_positives_ranked_above_negatives(self):
        import torch

        labels = torch.tensor([1.0, 0.0, 0.0])
        good = research_v2.ranking_loss(torch.tensor([3.0, 0.0, -1.0]), labels, "bpr")
        bad = research_v2.ranking_loss(torch.tensor([-1.0, 0.0, 3.0]), labels, "bpr")
        self.assertLess(float(good), float(bad))
        self.assertIsNone(research_v2.ranking_loss(torch.tensor([1.0]), torch.tensor([1.0]), "bpr"))

    def test_bce_and_unknown_loss(self):
        import torch

        labels = torch.tensor([1.0, 0.0])
        self.assertGreater(float(research_v2.ranking_loss(torch.zeros(2), labels, "bce")), 0)
        with self.assertRaises(ValueError):
            research_v2.ranking_loss(torch.zeros(2), labels, "hinge")


class FreezeGuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "configs/experiments").mkdir(parents=True)
        protocol = {
            "version": "test",
            "train_repositories": [],
            "validation_repositories": [],
            "test_repositories": ["fresh/project"],
            "queries": {"test_per_repository": 1},
        }
        (self.root / research_v2.PROTOCOL).write_text(json.dumps(protocol))
        self.files = ["configs/experiments/protocol-v2.json"]

    def tearDown(self):
        self.directory.cleanup()

    def freeze(self):
        output = self.root / research_v2.OUTPUT
        output.mkdir(parents=True, exist_ok=True)
        (output / "selection.json").write_text('{"primary": "hybrid"}')
        original = research_v2.frozen_files
        research_v2.frozen_files = lambda protocol, root: self.files
        try:
            return research_v2.freeze(self.root)
        finally:
            research_v2.frozen_files = original

    def test_freeze_refuses_after_test_project_opened(self):
        (self.root / "data/raw/fresh__project").mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.freeze()

    def test_verify_detects_change_but_not_line_endings(self):
        self.freeze()
        path = self.root / research_v2.PROTOCOL
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n") or b"")
        research_v2.verify_freeze(self.root)
        path.write_text('{"version": "changed"}')
        with self.assertRaises(ValueError):
            research_v2.verify_freeze(self.root)

    def test_evaluate_requires_freeze_and_runs_once(self):
        with self.assertRaises(FileNotFoundError):
            research_v2.evaluate(self.root)
        self.freeze()
        report = self.root / research_v2.FINAL_REPORT
        report.parent.mkdir(parents=True)
        report.write_text("{}")
        with self.assertRaises(ValueError):
            research_v2.evaluate(self.root)
