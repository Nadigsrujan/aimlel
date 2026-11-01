import subprocess
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.jobs.store import JobStore
from neural_cartographer.jobs import worker


class JobWorkerTests(unittest.TestCase):
    def test_installed_model_adds_exact_revision_semantics_before_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = JobStore(root / "jobs.sqlite")
            identifier, _ = store.create("a/b")
            model = root / "artifacts/models/heterogeneous-development/model.pt"
            model.parent.mkdir(parents=True)
            model.write_bytes(b"not loaded by this worker")
            manifests = root / "data/manifests"
            manifests.mkdir(parents=True)
            (manifests / "a__b.json").write_text(json.dumps({"revision": "a" * 40}))
            process = MagicMock()
            process.returncode = 0
            process.poll.return_value = 0
            process.communicate.return_value = ("", "")
            with (
                patch.object(worker, "STORE", store),
                patch.object(worker, "ROOT", root),
                patch.object(worker.subprocess, "Popen", return_value=process) as spawn,
            ):
                worker.run(identifier, "https://github.com/a/b", "a/b")
            self.assertEqual(spawn.call_count, 2)
            command = spawn.call_args_list[1].args[0]
            self.assertEqual(command[-2:], ["--revision", "a" * 40])
            self.assertNotIn("--download", command)
            value = store.get(identifier)
            self.assertEqual(value["status"], "processed")
            self.assertTrue(value["semantic_ready"])

    def test_cancellation_from_another_store_stops_the_owned_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = JobStore(root / "jobs.sqlite")
            identifier, _ = store.create("a/b")
            process = MagicMock()
            calls = 0

            def communicate(**kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    JobStore(store.path).cancel(identifier)
                    raise subprocess.TimeoutExpired(
                        "ingest",
                        2,
                        output=b'{"stage":"history","commits_scanned":1000,"queries":4}\n',
                    )
                return "", ""

            process.communicate.side_effect = communicate
            process.poll.return_value = 0
            with (
                patch.object(worker, "STORE", store),
                patch.object(worker, "ROOT", root),
                patch.object(worker.subprocess, "Popen", return_value=process),
                patch.object(worker, "stop_process_tree") as stop,
            ):
                worker.run(identifier, "https://github.com/a/b", "a/b")
            stop.assert_called_once_with(process)
            self.assertEqual(store.get(identifier)["status"], "cancelled")
            self.assertEqual(store.get(identifier)["progress"]["commits_scanned"], 1000)

    def test_quota_failure_records_error_and_stops_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = JobStore(root / "jobs.sqlite")
            identifier, _ = store.create("a/b")
            process = MagicMock()
            process.communicate.side_effect = [
                subprocess.TimeoutExpired("ingest", 2),
                ("", ""),
            ]
            process.poll.return_value = None
            with (
                patch.object(worker, "STORE", store),
                patch.object(worker, "ROOT", root),
                patch.object(worker, "MAX_REPOSITORY_BYTES", -1),
                patch.object(worker.subprocess, "Popen", return_value=process),
                patch.object(worker, "stop_process_tree") as stop,
            ):
                worker.run(identifier, "https://github.com/a/b", "a/b")
            stop.assert_called_once_with(process)
            value = store.get(identifier)
            self.assertEqual(value["status"], "failed")
            self.assertIn("limit", value["error"])
