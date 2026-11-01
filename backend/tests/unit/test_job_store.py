import concurrent.futures
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.jobs.store import JobStore, JobError


class JobStoreTests(unittest.TestCase):
    def test_shared_records_cancellation_and_terminal_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            first = JobStore(Path(folder) / "jobs.sqlite")
            second = JobStore(first.path)
            identifier, _ = first.create("a/b")
            self.assertEqual(second.get(identifier)["repo"], "a/b")
            self.assertEqual(second.cancel(identifier)["status"], "cancelling")
            self.assertTrue(first.running("A/B"))
            # A just-completed subprocess cannot overwrite cancellation.
            first.update(identifier, status="processed")
            self.assertEqual(second.get(identifier)["status"], "cancelled")
            first.update(identifier, status="failed")
            self.assertEqual(second.get(identifier)["status"], "cancelled")
            self.assertFalse(first.running("a/b"))

    def test_concurrent_workers_share_global_admission_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "jobs.sqlite"

            def create(index):
                try:
                    JobStore(path).create("owner/repo" + str(index))
                    return 202
                except JobError as error:
                    return error.status

            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                statuses = list(pool.map(create, range(4)))
            self.assertEqual(sorted(statuses), [202, 202, 429, 429])
            with self.assertRaises(JobError) as error:
                JobStore(path).create("OWNER/REPO0")
            self.assertIn(error.exception.status, (409, 429))

    def test_expired_heartbeat_is_failed_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            store = JobStore(Path(folder) / "jobs.sqlite")
            identifier, _ = store.create("a/b")
            with store.transaction() as connection:
                connection.execute(
                    "UPDATE jobs SET updated=0 WHERE id=?", (identifier,)
                )
            result = JobStore(store.path).get(identifier)
            self.assertEqual(result["status"], "failed")
            self.assertIn("heartbeat", result["error"])
