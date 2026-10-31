import sys
from pathlib import Path
import unittest
import torch
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'scripts'))
from train_heterogeneous import sample_indices, macro


class TrainingTests(unittest.TestCase):
    def test_sampling_keeps_all_positives_and_bounds_negatives(self):
        example = {'commit':'a' * 40, 'labels':torch.tensor([0.] * 20 + [1., 1.])}
        indices = sample_indices(example, 6, 17).tolist()
        self.assertEqual(len(indices), 8)
        self.assertTrue({20, 21}.issubset(indices))
        self.assertTrue({0, 1, 2}.issubset(indices))
        self.assertEqual(indices, sample_indices(example, 6, 17).tolist())

    def test_macro_weights_projects_equally(self):
        rows = [{'repo':'a', 'score':1}, {'repo':'a', 'score':1}, {'repo':'b', 'score':0}]
        self.assertEqual(macro(rows, 'score'), .5)
