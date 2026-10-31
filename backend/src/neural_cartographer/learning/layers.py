"""Two-layer relation-aware GraphSAGE and seed/candidate pair scorer.

File-node pilot model. Expanding to function/test node types and pretrained code
embeddings is required before claiming the full planned heterogeneous model.
"""
import torch
from torch import nn


class RelationSAGE(nn.Module):
    def __init__(self, inputs, hidden, relations):
        super().__init__()
        self.self_linear = nn.Linear(inputs, hidden)
        self.neighbors = nn.ModuleDict({name: nn.Linear(inputs, hidden, bias=False)
                                        for name in relations})

    def forward(self, x, edges):
        result = self.self_linear(x)
        for name, linear in self.neighbors.items():
            indices = edges[name]
            if indices.numel() == 0:
                continue
            source, target = indices
            aggregate = torch.zeros_like(x)
            counts = torch.zeros(x.shape[0], device=x.device)
            aggregate.index_add_(0, target, x[source])
            counts.index_add_(0, target, torch.ones_like(target, dtype=x.dtype))
            result = result + linear(aggregate / counts.clamp_min(1).unsqueeze(1))
        return result.relu()


class ImpactModel(nn.Module):
    def __init__(self, inputs=32, hidden=32, relations=('imports', 'imported_by')):
        super().__init__()
        self.first = RelationSAGE(inputs, hidden, relations)
        self.second = RelationSAGE(hidden, hidden, relations)
        self.dropout = nn.Dropout(0.1)
        self.pair = nn.Sequential(nn.Linear(hidden * 3 + 1, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, x, edges, seed, candidates, proximity):
        encoded = self.second(self.dropout(self.first(x, edges)), edges)
        left = encoded[seed].expand(len(candidates), -1)
        right = encoded[candidates]
        return self.pair(torch.cat([left, right, left * right, proximity[:, None]], dim=1)).squeeze(1)
