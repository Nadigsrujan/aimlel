"""Deterministic development evaluation; held-out partitions stay sealed."""
import argparse
import hashlib
import json
import time
import math
import random
from neural_cartographer.candidates.ranking import analyze
from neural_cartographer.features.history import RANKERS, rerank
from neural_cartographer.ingest.pipeline import ROOT, write


def metrics(ranked, positives, k=10):
    if k < 1 or len(set(ranked)) != len(ranked):
        raise ValueError('Rankings must be unique and k positive')
    relevant = set(positives)
    if not relevant:
        raise ValueError('Evaluation requires positive labels')
    hits = 0
    precision_sum = 0
    reciprocal_rank = 0
    for index, path in enumerate(ranked[:k], 1):
        if path in relevant:
            hits += 1
            precision_sum += hits / index
            if not reciprocal_rank:
                reciprocal_rank = 1 / index
    dcg = sum(1 / math.log2(i + 2) for i, path in enumerate(ranked[:k]) if path in relevant)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    first_five = len(set(ranked[:5]) & relevant)
    return {f'recall_at_{k}': hits / len(relevant), f'mrr_at_{k}': reciprocal_rank,
            f'map_at_{k}': precision_sum / min(k, len(relevant)),
            f'ndcg_at_{k}': dcg / ideal, 'recall_at_5': first_five / len(relevant),
            'precision_at_5': first_five / 5,
            'mrr': next((1 / i for i, path in enumerate(ranked, 1) if path in relevant), 0),
            'candidate_ceiling': len(set(ranked) & relevant) / len(relevant)}


def bootstrap(rows, metric, iterations=1000, seed=17):
    """Cluster by commit so multiple seeds from one change stay together."""
    groups = {}
    for row in rows:
        groups.setdefault(row['commit'], []).append(row[metric])
    clusters = list(groups.values())
    if not clusters:
        return None
    rng = random.Random(seed)
    estimates = []
    for _ in range(iterations):
        values = [v for group in rng.choices(clusters, k=len(clusters)) for v in group]
        estimates.append(sum(values) / len(values))
    estimates.sort()
    return {'lower': estimates[int(.025 * iterations)],
            'upper': estimates[min(iterations - 1, int(.975 * iterations))],
            'clusters': len(clusters), 'iterations': iterations, 'seed': seed}


def evaluate(repo, limit):
    key = repo.replace('/', '__')
    manifest = json.loads((ROOT / 'data/manifests' / (key + '.json')).read_text())
    if manifest['split'] != 'train':
        raise ValueError('Development evaluation accepts training repositories only')
    source = ROOT / 'data/processed' / key / manifest['revision'] / 'queries.jsonl'
    rows, failures = [], []
    with source.open() as stream:
        queries = [json.loads(line) for line in stream]
    queries.sort(key=lambda q: hashlib.sha256((q['commit'] + q['seed']).encode()).hexdigest())
    for query in queries[:limit]:
        start = time.monotonic()
        try:
            result = analyze(repo, query['seed'], query['commit'])
            if result['graph_revision'] != query['graph_revision']:
                raise ValueError('Parent snapshot mismatch')
            ranked = [row['path'] for row in result['candidates']]
            rows.append({'commit': query['commit'], 'seed': query['seed'],
                         'seconds': time.monotonic() - start,
                         **metrics(ranked, query['positives'])})
        except (ValueError, OSError) as exc:
            failures.append({'commit': query['commit'], 'error': str(exc)})
    report = {'repo': repo, 'split': 'train', 'ranker': 'path-distance-v1',
              'sampling': 'sha256(commit+seed) ascending', 'requested': limit,
              'evaluated': len(rows), 'failures': failures, 'queries': rows,
              'means': {name: sum(row[name] for row in rows) / len(rows)
                        for name in ('recall_at_10', 'mrr_at_10', 'map_at_10', 'seconds')} if rows else {}}
    write(ROOT / 'artifacts/reports' / (key + '-baseline-evaluation.json'), report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='pallets/flask')
    parser.add_argument('--limit', type=int, default=25)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error('limit must be between 1 and 10000')
    report = evaluate(args.repo, args.limit)
    print(json.dumps({key: value for key, value in report.items() if key != 'queries'}, indent=2))
