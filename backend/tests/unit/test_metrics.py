import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from evaluate import metrics, bootstrap


class MetricTests(unittest.TestCase):
    def test_known_ranking(self):
        result = metrics(['wrong', 'yes', 'also'], ['yes', 'also'])
        self.assertEqual(result['recall_at_10'], 1)
        self.assertEqual(result['mrr_at_10'], 0.5)
        self.assertAlmostEqual(result['map_at_10'], (0.5 + 2 / 3) / 2)

    def test_miss(self):
        self.assertEqual(metrics(['wrong'], ['yes'])['recall_at_10'], 0)

    def test_ceiling_and_cutoff(self):
        result = metrics(['a', 'b', 'c'], ['b', 'missing'], k=2)
        self.assertEqual(result['candidate_ceiling'], .5)
        self.assertEqual(result['recall_at_2'], .5)
        self.assertLess(result['ndcg_at_2'], 1)

    def test_duplicates_rejected(self):
        with self.assertRaises(ValueError):
            metrics(['a', 'a'], ['a'])

    def test_bootstrap_clusters_commit(self):
        rows = [{'commit': 'a', 'value': 0}, {'commit': 'a', 'value': 1}, {'commit': 'b', 'value': 1}]
        report = bootstrap(rows, 'value')
        self.assertEqual(report['clusters'], 2)
        self.assertEqual(report, bootstrap(rows, 'value'))
