import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend/src"))
from neural_cartographer.ingest.signatures import SignatureCache


class SignatureCacheTests(unittest.TestCase):
    def test_digests_and_uncertain_blobs_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "data/raw/a__b"
            repo.mkdir(parents=True)
            with SignatureCache(repo, "5") as cache:
                cache.put(b"a" * 40, b"x" * 32)
                cache.put(b"b" * 40, None)
            with SignatureCache(repo, "5") as cache:
                self.assertEqual(cache.get(b"a" * 40), b"x" * 32)
                self.assertIsNone(cache.get(b"b" * 40))
            with SignatureCache(repo, "6") as cache:
                with self.assertRaises(KeyError):
                    cache.get(b"a" * 40)
