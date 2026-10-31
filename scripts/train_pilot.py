"""Small reproducible file-graph experiment on training repositories only.

Uses structural features; does not claim semantic/pretrained embeddings.
"""
import argparse
import hashlib
import json
from pathlib import PurePosixPath
import random
import torch
import numpy as np
from xgboost import XGBClassifier
from analyze import analyze, rank
from ingest import ROOT, write
from learning import ImpactModel
from evaluate import metrics
from structure import resolve_imports


def tensorize(result):
    graph = result['graph']
    paths = sorted(n['path'] for n in graph['nodes'] if n['kind'] == 'file')
    index = {path: i for i, path in enumerate(paths)}
    x = torch.zeros((len(paths), 32))
    for path, i in index.items():
        x[i, 0] = len(PurePosixPath(path).parts) / 10
        x[i, 1] = float('test' in path.lower())
        x[i, 2] = float(path.endswith('__init__.py'))
        for node in graph['nodes']:
            if node['path'] == path:
                slot = {'function': 3, 'class': 4, 'test': 5}.get(node['kind'])
                if slot:
                    x[i, slot] += .01
    links = []
    resolved, _ = resolve_imports(graph)
    for edge in resolved:
        if edge['target'] != edge['source']:
            links.append((index[edge['source']], index[edge['target']]))
    imports = torch.tensor(links, dtype=torch.long).T.contiguous() if links else torch.empty((2, 0), dtype=torch.long)
    edges = {'imports': imports, 'imported_by': imports.flip(0)}
    seed = index[result['seed']]
    ranked = rank(paths, result['seed'])
    candidates = torch.tensor([index[r['path']] for r in ranked])
    proximity = torch.tensor([r['score'] for r in ranked])
    return x, edges, seed, candidates, proximity, [r['path'] for r in ranked]


def dataset(repo, limit):
    key = repo.replace('/', '__')
    manifest = json.loads((ROOT / 'data/manifests' / (key + '.json')).read_text())
    if manifest['split'] != 'train':
        raise ValueError('Pilot training accepts only training projects')
    source = ROOT / 'data/processed' / key / manifest['revision'] / 'queries.jsonl'
    with source.open() as stream:
        rows = [json.loads(line) for line in stream]
    # Whole commits are grouped: no seed from a validation commit appears in train.
    commits = list(dict.fromkeys(row['commit'] for row in rows))
    chosen = set(commits[-limit:])
    rows = [row for row in rows if row['commit'] in chosen]
    examples = []
    used = set()
    for row in rows:
        if row['commit'] in used:
            continue
        used.add(row['commit'])
        result = analyze(repo, row['seed'], row['commit'])
        values = tensorize(result)
        labels = torch.tensor([float(path in row['positives']) for path in values[-1]])
        if labels.sum() and len(labels) > 1:
            examples.append((row['commit'], values, labels))
    return examples


def run(limit, epochs):
    random.seed(17)
    torch.manual_seed(17)
    torch.set_num_threads(2)
    examples = dataset('pallets/flask', limit)
    cutoff = max(1, int(len(examples) * .8))
    train, development = examples[:cutoff], examples[cutoff:]
    if not train or not development:
        raise ValueError('Insufficient commits for training and development')
    model = ImpactModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=.003)
    losses = []
    for epoch in range(epochs):
        model.train()
        total = 0
        for _, values, labels in train:
            x, edges, seed, candidates, proximity, _ = values
            optimizer.zero_grad()
            logits = model(x, edges, seed, candidates, proximity)
            weight = (len(labels) - labels.sum()) / labels.sum().clamp_min(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=weight)
            loss.backward()
            optimizer.step()
            total += float(loss.detach())
        losses.append(total / len(train))
    model.eval()
    def pair_features(values):
        x, _, seed, candidates, proximity, _ = values
        left = x[seed].expand(len(candidates), -1)
        right = x[candidates]
        return torch.cat([left, right, left * right, proximity[:, None]], dim=1).numpy()
    baseline = XGBClassifier(n_estimators=50, max_depth=3, learning_rate=.05,
                             random_state=17, n_jobs=2, eval_metric='logloss')
    baseline.fit(np.concatenate([pair_features(values) for _, values, _ in train]),
                 np.concatenate([labels.numpy() for _, _, labels in train]))
    measurements = []
    with torch.no_grad():
        for commit, values, labels in development:
            x, edges, seed, candidates, proximity, paths = values
            logits = model(x, edges, seed, candidates, proximity)
            ranked = [paths[i] for i in torch.argsort(logits, descending=True).tolist()]
            positives = [p for p, label in zip(paths, labels) if label]
            baseline_scores = baseline.predict_proba(pair_features(values))[:, 1]
            baseline_ranked = [paths[i] for i in np.argsort(-baseline_scores, kind='stable')]
            measurements.append({'commit': commit, 'gnn': metrics(ranked, positives),
                                 'xgboost': metrics(baseline_ranked, positives),
                                 'distance': metrics(paths, positives)})
    output = ROOT / 'artifacts/models'
    output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output / 'file-graph-pilot.pt')
    baseline.save_model(output / 'xgboost-pilot.json')
    report = {'seed': 17, 'epochs': epochs, 'train_commits': len(train),
              'development_commits': len(development), 'losses': losses,
              'results': measurements, 'status': 'pilot-only',
              'limitations': ['Structural features only', 'Single training project',
                              'No model selection or calibration', 'No held-out evaluation',
                              'Exact static imports only', 'Not the complete heterogeneous model']}
    write(ROOT / 'artifacts/reports/graph-learning-pilot.json', report)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commits', type=int, default=30)
    parser.add_argument('--epochs', type=int, default=10)
    args = parser.parse_args()
    run(args.commits, args.epochs)
