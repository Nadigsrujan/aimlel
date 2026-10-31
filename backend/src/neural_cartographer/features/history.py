"""Evidence-bearing structural and past-only co-change features."""
from collections import defaultdict, deque
import json
import hashlib
import math
from neural_cartographer.ingest.pipeline import git
from neural_cartographer.graph.structure import resolve_imports

FEATURE_VERSION = 'structural-history-v3'
RANKERS = ('path-distance-v1', 'random-v1', 'popularity-v1', 'imports-v1',
           'cochange-v1', 'combined-v1')


def rerank(rows, ranker, seed):
    """Score the same complete pool for every baseline, with stable tie breaks."""
    if ranker not in RANKERS:
        raise ValueError('Unknown ranker: ' + ranker)
    def score(row):
        values = row['features']
        proximity = values['directory_proximity']
        structural = 1 / (1 + values['structural_hops']) if values['structural_hops'] is not None else 0
        history = values['cochange_jaccard']
        return {'path-distance-v1': proximity,
                'random-v1': int(hashlib.sha256((seed + '\0' + row['path']).encode()).hexdigest()[:13], 16) / 16**13,
                'popularity-v1': math.log1p(values['past_change_count']),
                'imports-v1': structural, 'cochange-v1': history,
                'combined-v1': (proximity + structural + history) / 3}[ranker]
    return sorted(({**row, 'score': score(row)} for row in rows),
                  key=lambda row: (-row['score'], row['path']))


def past_events(repo, revision, event_file):
    # Reachability, rather than timestamps, handles parallel branches correctly.
    ancestors = set(git(repo, 'rev-list', revision).decode().splitlines())
    with event_file.open() as stream:
        for line in stream:
            event = json.loads(line)
            if event['commit'] in ancestors and len(event['changes']) <= 50:
                yield event


def enrich(candidates, graph, seed, events):
    resolved, unresolved = resolve_imports(graph)
    adjacency = defaultdict(set)
    for edge in resolved:
        adjacency[edge['source']].add(edge['target'])
        adjacency[edge['target']].add(edge['source'])
    paths = {seed: [seed]}
    queue = deque([seed])
    while queue:
        current = queue.popleft()
        if len(paths[current]) > 3:
            continue
        for neighbor in sorted(adjacency[current]):
            if neighbor not in paths:
                paths[neighbor] = paths[current] + [neighbor]
                queue.append(neighbor)
    counts, commits = defaultdict(int), defaultdict(list)
    frequency, last_changed = defaultdict(int), {}
    event_count = 0
    for event in events:
        event_count += 1
        changed = {change['path'] for change in event['changes'] if change['status'] == 'M'}
        for path in changed:
            frequency[path] += 1
            last_changed[path] = event_count
        if seed not in changed:
            continue
        for path in changed - {seed}:
            counts[path] += 1
            commits[path].append(event['commit'])
    output = []
    for row in candidates:
        path = row['path']
        structural = paths.get(path)
        output.append({**row, 'features': {'directory_proximity': row['score'],
                       'structural_hops': len(structural)-1 if structural else None,
                       'past_cochange_count': counts[path],
                       'past_change_count': frequency[path],
                       'commits_since_change': event_count - last_changed[path] if path in last_changed else None,
                       'cochange_jaccard': counts[path] / max(1, frequency[seed] + frequency[path] - counts[path])},
                       'evidence': {'import_path': structural or [],
                                    'past_commits': commits[path][-5:]},
                       'channels': ['directory'] + (['structural'] if structural else [])
                                   + (['history'] if counts[path] else [])})
    return output, {'resolved_imports': len(resolved), 'unresolved_imports': len(unresolved)}
