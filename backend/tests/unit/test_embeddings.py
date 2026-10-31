import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from embeddings import index_directory


class EmbeddingTests(unittest.TestCase):
    def test_cutoff_changes_index_directory(self):
        self.assertNotEqual(index_directory('a/b', 'a'*40), index_directory('a/b', 'b'*40))
        with self.assertRaises(ValueError):
            index_directory('../outside', 'a'*40)

    def test_isolated_index_search_matches_cosine(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            np.save(root / 'vectors.npy', np.array([[1,0], [0,1], [.8,.6]], dtype='float32'))
            script = Path(__file__).resolve().parents[3] / 'scripts/vector_index.py'
            subprocess.run([sys.executable, str(script), 'build', directory], check=True)
            result = json.loads(subprocess.check_output([sys.executable, str(script), 'query', directory, '0']))
            self.assertEqual([item[0] for item in result], [0, 2, 1])
            self.assertAlmostEqual(result[1][1], .8, places=6)
