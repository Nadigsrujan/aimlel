import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from heterogeneous import HeterogeneousImpactModel, tensorize
from features import enrich


class HeterogeneousTests(unittest.TestCase):
    def test_node_types_relations_and_gradients(self):
        graph = {'nodes': [{'id':'a.py', 'path':'a.py', 'kind':'file'},
                           {'id':'test_a.py', 'path':'test_a.py', 'kind':'file'},
                           {'id':'test_a.py::test_f@1', 'path':'test_a.py', 'kind':'test', 'start':1, 'end':2}],
                 'edges': [{'source':'test_a.py', 'target':'a', 'relation':'IMPORTS'},
                           {'source':'test_a.py', 'target':'test_a.py::test_f@1', 'relation':'CONTAINS'}]}
        rows, _ = enrich([{'path':'test_a.py', 'score':1/3}], graph, 'a.py', [])
        batch = tensorize({'graph':graph, 'seed':'a.py', 'candidates':rows})
        self.assertEqual(batch['edges']['tests'].shape, (2, 1))
        self.assertEqual(batch['edges']['contains'].shape, (2, 1))
        self.assertEqual(batch['edges']['cochange'].shape, (2, 0))
        model = HeterogeneousImpactModel()
        logits = model(batch)
        self.assertEqual(logits.shape, (1,))
        logits.sum().backward()
        self.assertIsNotNone(model.projections[3].weight.grad)
        self.assertIsNotNone(model.first.neighbors['tests'].weight.grad)
