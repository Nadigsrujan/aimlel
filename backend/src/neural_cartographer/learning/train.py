"""Train typed GraphSAGE/XGBoost on training projects; select on validation only."""
import copy
import hashlib
import json
import random
import time
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from xgboost import XGBClassifier
from neural_cartographer.candidates.ranking import analyze, rank
from neural_cartographer.contracts.schema import provenance
from neural_cartographer.evaluation.metrics import metrics
from neural_cartographer.features.history import FEATURE_VERSION, RANKERS, enrich, past_events, rerank
from neural_cartographer.learning.heterogeneous import HeterogeneousImpactModel, PAIR_FEATURES, RELATIONS, tensorize
from neural_cartographer.ingest.pipeline import ROOT, VERSION, write


def examples(manifest, limit):
    repo = manifest['repo']
    key = repo.replace('/', '__')
    directory = ROOT / 'data/processed' / key / manifest['revision']
    by_commit = {}
    with (directory / 'queries.jsonl').open() as stream:
        for line in stream:
            query = json.loads(line)
            by_commit.setdefault(query['commit'], query)
    # One seed per complete commit. Preserve chronological/topological order.
    selected = list(by_commit.values())[-limit:]
    for query in selected:
        started = time.monotonic()
        result = analyze(repo, query['seed'], query['commit'])
        paths = [node['path'] for node in result['graph']['nodes'] if node['kind'] == 'file']
        rows, _ = enrich(rank(paths, query['seed']), result['graph'], query['seed'],
                         past_events(ROOT / 'data/raw' / key, result['graph_revision'], directory / 'events.jsonl'))
        result['candidates'] = rows
        batch = tensorize(result)
        labels = torch.tensor([float(path in query['positives']) for path in batch['paths']])
        yield {'repo': repo, 'commit': query['commit'], 'revision': query['graph_revision'],
               'seed': query['seed'], 'batch': batch, 'labels': labels,
               'positives': query['positives'], 'rows': rows, 'seconds': time.monotonic() - started}


def sample_indices(example, maximum, seed):
    labels = example['labels']
    positives = torch.where(labels > 0)[0].tolist()
    negatives = torch.where(labels == 0)[0].tolist()
    # First half: hardest fixed directory neighbors; remainder: deterministic random.
    hard = negatives[:maximum // 2]
    rng = random.Random(seed + int(example['commit'][:8], 16))
    rest = negatives[maximum // 2:]
    selected = positives + hard + rng.sample(rest, min(len(rest), maximum - len(hard)))
    return torch.tensor(sorted(selected), dtype=torch.long)


def macro(rows, metric):
    grouped = {}
    for row in rows:
        grouped.setdefault(row['repo'], []).append(row[metric])
    return sum(sum(values) / len(values) for values in grouped.values()) / len(grouped) if grouped else 0


def measure(model, examples_, baseline=None):
    model.eval()
    rows = []
    with torch.inference_mode():
        for example in examples_:
            scores = model(example['batch']).numpy() if baseline is None else baseline.predict_proba(example['batch']['pairs'].numpy())[:, 1]
            indices = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), example['batch']['paths'][i]))
            paths = [example['batch']['paths'][i] for i in indices]
            rows.append({'repo': example['repo'], 'commit': example['commit'],
                         **metrics(paths, example['positives'])})
    return rows


def run():
    config = json.loads((ROOT / 'configs/experiments/heterogeneous.json').read_text())
    seed = config['seed']
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    manifests = [json.loads(path.read_text()) for path in sorted((ROOT / 'data/manifests').glob('*.json'))]
    train, validation = [], []
    failures = []
    for manifest in manifests:
        if manifest['split'] not in ('train', 'validation'):
            continue
        limit = config['commits_per_training_repo'] if manifest['split'] == 'train' else config['commits_per_validation_repo']
        print('Preparing', manifest['repo'], flush=True)
        try:
            rows = list(examples(manifest, limit))
            (train if manifest['split'] == 'train' else validation).extend(rows)
        except (OSError, ValueError) as exc:
            failures.append({'repo': manifest['repo'], 'error': str(exc)})
    if failures or not train or len(validation) < 4:
        write(ROOT / 'artifacts/reports/heterogeneous-preparation-failures.json', failures)
        raise ValueError('Incomplete training/validation corpus; refusing to select a model')
    selection, calibration = validation[::2], validation[1::2]
    model = HeterogeneousImpactModel()
    optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
    best, best_state, stalled, history = -1, None, 0, []
    for epoch in range(config['epochs']):
        model.train()
        losses = []
        for example in train:
            indices = sample_indices(example, config['negative_limit'], seed)
            labels = example['labels'][indices]
            if not labels.numel() or not labels.sum():
                continue
            optimizer.zero_grad()
            logits = model(example['batch'])[indices]
            weight = (len(labels) - labels.sum()) / labels.sum().clamp_min(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=weight.clamp_min(1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            losses.append(float(loss.detach()))
        if not losses:
            raise ValueError('No training positives')
        score = macro(measure(model, selection), 'recall_at_5')
        history.append({'epoch': epoch + 1, 'loss': sum(losses) / len(losses), 'validation_macro_recall_at_5': score})
        print(history[-1], flush=True)
        if score > best:
            best, best_state, stalled = score, copy.deepcopy(model.state_dict()), 0
        else:
            stalled += 1
        if stalled >= config['patience']:
            break
    model.load_state_dict(best_state)
    model.eval()
    x, y = [], []
    for example in train:
        indices = sample_indices(example, config['negative_limit'], seed)
        x.append(example['batch']['pairs'][indices].numpy())
        y.append(example['labels'][indices].numpy())
    baseline = XGBClassifier(n_estimators=100, max_depth=3, learning_rate=.05,
                             random_state=seed, n_jobs=2, eval_metric='logloss')
    baseline.fit(np.concatenate(x), np.concatenate(y))
    comparison = {'heterogeneous': measure(model, selection), 'xgboost': measure(model, selection, baseline)}
    for name in RANKERS:
        comparison[name] = [{'repo': example['repo'], 'commit': example['commit'],
                             **metrics([row['path'] for row in rerank(example['rows'], name, example['seed'])], example['positives'])}
                            for example in selection]
    scores, labels = [], []
    with torch.inference_mode():
        for example in calibration:
            scores.extend(model(example['batch']).tolist())
            labels.extend(example['labels'].tolist())
    calibrator = LogisticRegression(random_state=seed, solver='liblinear').fit(np.array(scores).reshape(-1, 1), labels)
    probabilities = calibrator.predict_proba(np.array(scores).reshape(-1, 1))[:, 1]
    metadata = {'config': config, 'feature_names': list(PAIR_FEATURES), 'relations': list(RELATIONS),
                'provenance': provenance(manifests, config, VERSION, FEATURE_VERSION, seed),
                'train_queries': [{'repo': row['repo'], 'commit': row['commit'], 'seed': row['seed']} for row in train],
                'selection_queries': [{'repo': row['repo'], 'commit': row['commit']} for row in selection],
                'calibration_queries': [{'repo': row['repo'], 'commit': row['commit']} for row in calibration]}
    output = ROOT / 'artifacts/models/heterogeneous-development'
    output.mkdir(parents=True, exist_ok=True)
    torch.save({'state_dict': best_state, 'metadata': metadata}, output / 'model.pt')
    baseline.save_model(output / 'xgboost.json')
    write(output / 'calibration.json', {'coefficient': calibrator.coef_.tolist(), 'intercept': calibrator.intercept_.tolist(),
                                      'status': 'validation-fit-only; not a held-out calibration estimate'})
    write(output / 'metadata.json', metadata)
    report = {'status': 'development; not frozen for final testing', 'history': history,
              'comparison': comparison, 'macro_recall_at_5': {name: macro(rows, 'recall_at_5') for name, rows in comparison.items()},
              'calibration_fit': {'brier': brier_score_loss(labels, probabilities),
                                  'average_precision': average_precision_score(labels, probabilities),
                                  'pairs': len(labels)}, 'metadata': metadata, 'failures': failures}
    write(ROOT / 'artifacts/reports/heterogeneous-development.json', report)
    print(json.dumps({'status':report['status'], 'macro_recall_at_5':report['macro_recall_at_5']}, indent=2))


if __name__ == '__main__':
    run()
