"""Deterministic development evaluation; held-out partitions stay sealed."""
import argparse
import hashlib
import json
import time
from analyze import analyze
from ingest import ROOT, write


def metrics(ranked, positives, k=10):
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
    return {'recall_at_10': hits / len(relevant), 'mrr_at_10': reciprocal_rank,
            'map_at_10': precision_sum / min(k, len(relevant))}


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
