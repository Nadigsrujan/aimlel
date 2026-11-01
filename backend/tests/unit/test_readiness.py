"""Readiness and source endpoint acceptance checks."""

import sys
from pathlib import Path
import unittest
import json
import tempfile
import subprocess
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from fastapi.testclient import TestClient
import api


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)

    def test_model_lab_withholds_obsolete_experiment_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / "artifacts/reports"
            reports.mkdir(parents=True)
            (reports / "heterogeneous-development.json").write_text(
                json.dumps(
                    {
                        "metadata": {"provenance": {"parser_version": "obsolete"}},
                        "macro_recall_at_5": {"heterogeneous": 0.99},
                    }
                )
            )
            with (
                patch.object(api, "ROOT", root),
                patch.object(api, "catalog", return_value=[]),
            ):
                response = self.client.get("/api/v1/research")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["experiment_compatible"])
                self.assertEqual(response.json()["metrics"], {})

    def test_manifest_without_materialized_graph_remains_visible(self):
        manifest = {"repo": "example/missing", "revision": "a" * 40, "split": "train"}
        with patch.object(
            api.serve, "load_manifests", return_value={"example/missing": manifest}
        ):
            row = self.client.get("/api/v1/catalog").json()[0]
            self.assertFalse(row["available"])
            self.assertEqual(row["summary"], {})

    def test_source_rejects_traversal_invalid_revision_and_unbounded_ranges(self):
        manifest = {"revision": "a" * 40}
        with patch.object(
            api.serve, "load_manifests", return_value={"example/repo": manifest}
        ):
            for extra in [
                {"path": "../secret.py"},
                {"revision": "HEAD"},
                {"lines": 201},
                {"start": 0},
            ]:
                params = {
                    "repo": "example/repo",
                    "revision": "a" * 40,
                    "path": "safe.py",
                    **extra,
                }
                self.assertEqual(
                    self.client.get("/api/v1/source", params=params).status_code, 422
                )

    def test_source_rejects_unknown_repository(self):
        with patch.object(api.serve, "load_manifests", return_value={}):
            self.assertEqual(
                self.client.get(
                    "/api/v1/source",
                    params={"repo": "x/y", "revision": "a" * 40, "path": "x.py"},
                ).status_code,
                404,
            )

    def test_source_checks_size_before_reading_blob(self):
        with (
            patch.object(
                api.serve,
                "load_manifests",
                return_value={"a/b": {"revision": "a" * 40}},
            ),
            patch.object(
                api.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)
            ),
            patch.object(api, "git", return_value=b"3000000") as git,
        ):
            response = self.client.get(
                "/api/v1/source",
                params={"repo": "a/b", "revision": "a" * 40, "path": "large.py"},
            )
        self.assertEqual(response.status_code, 413)
        self.assertEqual(git.call_count, 1)
        self.assertEqual(git.call_args.args[1:3], ("cat-file", "-s"))
