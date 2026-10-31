import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from evaluate import metrics


class MetricTests(unittest.TestCase):
    def test_known_ranking(self):
        result = metrics(['wrong', 'yes', 'also'], ['yes', 'also'])
        self.assertEqual(result['recall_at_10'], 1)
        self.assertEqual(result['mrr_at_10'], 0.5)
        self.assertAlmostEqual(result['map_at_10'], (0.5 + 2 / 3) / 2)

    def test_miss(self):
        self.assertEqual(metrics(['wrong'], ['yes'])['recall_at_10'], 0)
