"""Typed graph tensors and relation-aware GraphSAGE pair scoring.

Labels are deliberately absent from this module. Static resolution is
conservative: unresolved calls and inheritance are not invented as edges.
"""
import math
import torch
from torch import nn
from neural_cartographer.learning.layers import RelationSAGE
from neural_cartographer.graph.structure import resolve_imports

KINDS = ('file', 'class', 'function', 'test')
RELATIONS = ('contains', 'contained_by', 'imports', 'imported_by', 'tests', 'tested_by', 'cochange')
PAIR_FEATURES = ('directory_proximity', 'structural_proximity', 'cochange_jaccard',
                 'past_change_count_log', 'past_cochange_count_log', 'recency')


def tensorize(result):
    graph = result['graph']
    nodes = sorted(graph['nodes'], key=lambda node: node['id'])
    index = {node['id']: i for i, node in enumerate(nodes)}
    file_ids = {node['path']: node['id'] for node in nodes if node['kind'] == 'file'}
    if len(index) != len(nodes):
        raise ValueError('Graph contains duplicate entity IDs')
    x = torch.zeros((len(nodes), 8), dtype=torch.float32)
    kinds = torch.tensor([KINDS.index(node['kind']) for node in nodes], dtype=torch.long)
    for i, node in enumerate(nodes):
        x[i, KINDS.index(node['kind'])] = 1
        x[i, 4] = len(node['path'].split('/')) / 10
        x[i, 5] = math.log1p(max(0, node.get('end', 0) - node.get('start', 0))) / 10
        x[i, 6] = float(node['path'].endswith('__init__.py'))
        x[i, 7] = float('/tests/' in '/' + node['path'] or node['path'].split('/')[-1].startswith('test_'))
    links = {name: set() for name in RELATIONS}
    for edge in graph['edges']:
        if edge['relation'] == 'CONTAINS' and edge['source'] in index and edge['target'] in index:
            a, b = index[edge['source']], index[edge['target']]
            links['contains'].add((a, b))
            links['contained_by'].add((b, a))
    resolved, unresolved = resolve_imports(graph)
    test_files = {node['path'] for node in nodes if node['kind'] == 'test'}
    for edge in resolved:
        a, b = index[file_ids[edge['source']]], index[file_ids[edge['target']]]
        links['imports'].add((a, b))
        links['imported_by'].add((b, a))
        # Explicit import from a file containing test functions is evidence
        # of a test/source relationship, not proof of runtime coverage.
        if edge['source'] in test_files and edge['target'] not in test_files:
            links['tests'].add((a, b))
            links['tested_by'].add((b, a))
    seed = index[file_ids[result['seed']]]
    candidates, pairs, paths = [], [], []
    for row in result['candidates']:
        candidate = index[file_ids[row['path']]]
        features = row['features']
        hops = features['structural_hops']
        age = features['commits_since_change']
        pairs.append([features['directory_proximity'], 1 / (1 + hops) if hops is not None else 0,
                      features['cochange_jaccard'], math.log1p(features['past_change_count']),
                      math.log1p(features['past_cochange_count']), 1 / (1 + age) if age is not None else 0])
        if features['past_cochange_count']:
            links['cochange'].update(((seed, candidate), (candidate, seed)))
        candidates.append(candidate)
        paths.append(row['path'])
    edges = {name: torch.tensor(sorted(values), dtype=torch.long).T.contiguous()
             if values else torch.empty((2, 0), dtype=torch.long) for name, values in links.items()}
    return {'x': x, 'kinds': kinds, 'edges': edges, 'seed': seed,
            'candidates': torch.tensor(candidates, dtype=torch.long),
            'pairs': torch.tensor(pairs, dtype=torch.float32).reshape(-1, len(PAIR_FEATURES)),
            'paths': paths, 'unresolved_imports': len(unresolved)}


class HeterogeneousImpactModel(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.projections = nn.ModuleList([nn.Linear(8, hidden) for _ in KINDS])
        self.first = RelationSAGE(hidden, hidden, RELATIONS)
        self.second = RelationSAGE(hidden, hidden, RELATIONS)
        self.dropout = nn.Dropout(.1)
        self.pair = nn.Sequential(nn.Linear(hidden * 3 + len(PAIR_FEATURES), hidden),
                                  nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, batch):
        x, kinds = batch['x'], batch['kinds']
        projected = sum(layer(x) * (kinds == i).unsqueeze(1) for i, layer in enumerate(self.projections))
        encoded = self.second(self.dropout(self.first(projected.relu(), batch['edges'])), batch['edges'])
        right = encoded[batch['candidates']]
        left = encoded[batch['seed']].expand(len(right), -1)
        return self.pair(torch.cat((left, right, left * right, batch['pairs']), dim=1)).squeeze(1)
