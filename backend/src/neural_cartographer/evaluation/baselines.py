"""Compare all heuristics on identical complete pools in training projects."""
import argparse
import hashlib
import json
import time
from neural_cartographer.candidates.ranking import analyze, rank
from neural_cartographer.evaluation.metrics import bootstrap, metrics
from neural_cartographer.features.history import RANKERS, FEATURE_VERSION, enrich, past_events, rerank
from neural_cartographer.ingest.pipeline import ROOT, write


def compare(repo, limit):
    key = repo.replace('/', '__')
    manifest = json.loads((ROOT / 'data/manifests' / (key + '.json')).read_text())
    if manifest['split'] != 'train':
        raise ValueError('Baseline development is restricted to training repositories')
    directory = ROOT / 'data/processed' / key / manifest['revision']
    queries = [json.loads(line) for line in (directory / 'queries.jsonl').open()]
    queries.sort(key=lambda row: hashlib.sha256((row['commit'] + row['seed']).encode()).hexdigest())
    results, failures = {name: [] for name in RANKERS}, []
    for query in queries[:limit]:
        started = time.monotonic()
        try:
            result = analyze(repo, query['seed'], query['commit'])
            assert result['graph_revision'] == query['graph_revision']
            paths = [node['path'] for node in result['graph']['nodes'] if node['kind'] == 'file']
            rows, _ = enrich(rank(paths, query['seed']), result['graph'], query['seed'],
                             past_events(ROOT / 'data/raw' / key, result['graph_revision'], directory / 'events.jsonl'))
            feature_seconds = time.monotonic() - started
            for name in RANKERS:
                ranked = rerank(rows, name, query['seed'])
                results[name].append({'commit': query['commit'], 'seed': query['seed'],
                                      'seconds': feature_seconds,
                                      **metrics([r['path'] for r in ranked], query['positives'])})
        except (ValueError, OSError) as exc:
            failures.append({'commit': query['commit'], 'seed': query['seed'], 'error': str(exc)})
    summaries = {}
    for name, rows in results.items():
        summaries[name] = {'evaluated': len(rows), 'means': {
            metric: sum(r[metric] for r in rows) / len(rows)
            for metric in rows[0] if metric not in ('commit', 'seed')} if rows else {},
            'recall_at_5_ci': bootstrap(rows, 'recall_at_5'),
            'ndcg_at_10_ci': bootstrap(rows, 'ndcg_at_10')}
    report = {'repo': repo, 'split': manifest['split'], 'revision': manifest['revision'],
              'feature_version': FEATURE_VERSION, 'candidate_policy': 'all-eligible-files-excluding-seed-v1',
              'sampling': 'sha256(commit+seed) ascending', 'requested': limit,
              'summaries': summaries, 'queries': results, 'failures': failures}
    write(ROOT / 'artifacts/reports' / (key + '-baseline-comparison.json'), report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', default='pallets/flask')
    parser.add_argument('--limit', type=int, default=25)
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error('limit must be between 1 and 10000')
    report = compare(args.repo, args.limit)
    print(json.dumps({k: v for k, v in report.items() if k != 'queries'}, indent=2))
