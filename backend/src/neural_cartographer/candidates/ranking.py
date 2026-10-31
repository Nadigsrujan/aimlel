"""Past-only path-distance baseline; target repository code is never executed."""
import argparse
import json
from pathlib import PurePosixPath
import re
import subprocess
from neural_cartographer.ingest.pipeline import ROOT, VERSION, eligible, extract, git, write
from neural_cartographer.contracts.schema import entity_records, provenance
from neural_cartographer.graph.snapshots import build_snapshot
from neural_cartographer.features.history import FEATURE_VERSION, RANKERS, enrich, past_events, rerank


def rank(files, seed):
    if seed not in files:
        raise ValueError('Seed must exist in the selected snapshot')
    a = PurePosixPath(seed).parts
    results = []
    for path in sorted(set(files) - {seed}):
        b = PurePosixPath(path).parts
        common = 0
        for left, right in zip(a, b):
            if left != right:
                break
            common += 1
        distance = len(a) + len(b) - 2 * common
        results.append({'path': path, 'distance': distance, 'score': 1 / (1 + distance)})
    return sorted(results, key=lambda row: (row['distance'], row['path']))


def analyze(repo_id, seed, target=None, top_k=10, include_evidence=False, ranker='path-distance-v1'):
    if not isinstance(top_k, int) or not 1 <= top_k <= 1000:
        raise ValueError('top_k must be between 1 and 1000')
    if ranker not in RANKERS + ('semantic-v1',):
        raise ValueError('Unknown ranker: ' + ranker)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo_id):
        raise ValueError('Expected owner/repository')
    key = repo_id.replace('/', '__')
    manifest = json.loads((ROOT / 'data/manifests' / (key + '.json')).read_text())
    repo = ROOT / 'data/raw' / key
    revision = manifest['revision']
    if target:
        if not re.fullmatch(r'[0-9a-f]{40}', target):
            raise ValueError('Target must be a full commit SHA')
        ancestry = subprocess.run(['git', '-C', str(repo), 'merge-base', '--is-ancestor', target, revision],
                                  capture_output=True, timeout=60)
        if ancestry.returncode:
            raise ValueError('Target is outside pinned history')
        parents = git(repo, 'rev-list', '--parents', '-n', '1', target).decode().split()
        if len(parents) != 2:
            raise ValueError('Target must have exactly one parent')
        revision = parents[1]
    nodes, edges, failures, files = [], [], [], []
    snapshot = ROOT / 'data/processed' / key / revision / 'graph.json'
    if not target and snapshot.exists():
        graph = json.loads(snapshot.read_text())
        summary = json.loads(snapshot.with_name('summary.json').read_text())
        files = [node['path'] for node in graph['nodes'] if node['kind'] == 'file']
        result = {'schema_version': 1, 'repo': repo_id, 'graph_revision': revision,
                'target_commit': None, 'seed': seed, 'ranker': 'path-distance-v1',
                'score_is_probability': False, 'candidates': rank(files, seed),
                'graph': graph, 'parse_failures': summary['parse_failures']}
        return finalize(result, repo, manifest, include_evidence, ranker, top_k)
    graph = build_snapshot(repo, revision)
    nodes, edges, failures = graph['nodes'], graph['edges'], graph['parse_failures']
    files = [node['path'] for node in nodes if node['kind'] == 'file']
    ranked = rank(files, seed)
    result = {'schema_version': 1, 'repo': repo_id, 'graph_revision': revision,
            'target_commit': target, 'seed': seed, 'ranker': 'path-distance-v1',
            'score_is_probability': False, 'candidates': ranked,
            'graph': {'nodes': nodes, 'edges': edges}, 'parse_failures': failures}
    return finalize(result, repo, manifest, include_evidence, ranker, top_k)


def finalize(result, repo, manifest, include_evidence, ranker, top_k):
    result['provenance'] = provenance(manifest, {'ranker': ranker, 'top_k': top_k}, VERSION, FEATURE_VERSION)
    result['entities'] = entity_records(result['graph'], result['repo'], result['graph_revision'])
    result['candidate_count'] = len(result['candidates'])
    result['candidate_policy'] = 'all-eligible-files-excluding-seed-v1'
    if include_evidence or ranker != 'path-distance-v1':
        result = add_evidence(result, repo, manifest)
        if ranker == 'semantic-v1':
            from neural_cartographer.features.embeddings import similarities
            try:
                scores = similarities(result['repo'], result['graph_revision'], result['seed'])
            except (FileNotFoundError, ImportError) as exc:
                raise ValueError('Semantic index unavailable for this exact revision; build it with scripts/embeddings.py') from exc
            for row in result['candidates']:
                if row['path'] not in scores:
                    raise ValueError('Semantic index does not cover the complete candidate pool')
                row['score'] = scores[row['path']]
                row['features']['semantic_cosine'] = scores[row['path']]
                row['channels'].append('semantic')
            result['candidates'].sort(key=lambda row: (-row['score'], row['path']))
        else:
            result['candidates'] = rerank(result['candidates'], ranker, result['seed'])
        result['feature_version'] = FEATURE_VERSION
    result['ranker'] = ranker
    result['candidates'] = result['candidates'][:top_k]
    return result


def add_evidence(result, repo, manifest):
    event_file = ROOT / 'data/processed' / result['repo'].replace('/', '__') / manifest['revision'] / 'events.jsonl'
    events = past_events(repo, result['graph_revision'], event_file)
    result['candidates'], result['resolution'] = enrich(
        result['candidates'], result['graph'], result['seed'], events)
    result['evidence_cutoff'] = result['graph_revision']
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--seed', required=True)
    parser.add_argument('--target-commit')
    parser.add_argument('--top-k', type=int, default=10)
    parser.add_argument('--ranker', choices=RANKERS + ('semantic-v1',), default='path-distance-v1')
    parser.add_argument('--evidence', action='store_true')
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error('--top-k must be positive')
    result = analyze(args.repo, args.seed, args.target_commit, args.top_k,
                     include_evidence=args.evidence, ranker=args.ranker)
    output = ROOT / 'artifacts/reports' / (args.repo.replace('/', '__') + '-analysis.json')
    write(output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('graph', 'entities')}, indent=2))
    print('Report:', output)
