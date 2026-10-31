import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
try:
    import torch
    from learning import RelationSAGE, ImpactModel
except ImportError:
    torch = None


@unittest.skipIf(torch is None, 'Optional ML environment is not installed')
class GraphLearningTests(unittest.TestCase):
    def test_mean_aggregation_direction(self):
        layer = RelationSAGE(1, 1, ['imports'])
        with torch.no_grad():
            layer.self_linear.weight.zero_()
            layer.self_linear.bias.zero_()
            layer.neighbors['imports'].weight.fill_(1)
        x = torch.tensor([[2.], [4.], [0.]])
        output = layer(x, {'imports': torch.tensor([[0, 1], [2, 2]])})
        self.assertEqual(output.tolist(), [[0.], [0.], [3.]])

    def test_pair_scorer_gradients(self):
        torch.manual_seed(7)
        model = ImpactModel(inputs=2)
        x = torch.tensor([[1., 0.], [0., 1.], [1., 1.]])
        edges = {'imports': torch.tensor([[0], [1]]), 'imported_by': torch.tensor([[1], [0]])}
        logits = model(x, edges, 0, torch.tensor([1, 2]), torch.tensor([.5, .2]))
        self.assertEqual(tuple(logits.shape), (2,))
        loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, torch.tensor([1., 0.]))
        loss.backward()
        self.assertTrue(torch.isfinite(loss))
        self.assertIsNotNone(model.pair[0].weight.grad)
