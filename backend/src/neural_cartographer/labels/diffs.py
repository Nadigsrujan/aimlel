"""Map parent-side Git hunks to stored entities without running repository code."""
import argparse
import json
import re
from neural_cartographer.contracts.schema import changed_entities
from neural_cartographer.ingest.pipeline import ROOT, eligible, git, write
from neural_cartographer.graph.snapshots import build_snapshot

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@', re.MULTILINE)


def map_changes(repo, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Expected full commit SHA')
    parents = git(repo, 'rev-list', '--parents', '-n', '1', commit).decode().split()
    if len(parents) != 2:
        raise ValueError('Mapping requires a single-parent commit')
    parent = parents[1]
    graph = build_snapshot(repo, parent)
    fields = iter(git(repo, 'diff', '--name-status', '-z', '--find-renames', parent, commit).decode('utf-8', 'surrogateescape').split('\0'))
    files = []
    for status in fields:
        if not status:
            continue
        old = next(fields)
        new = next(fields) if status.startswith(('R', 'C')) else old
        if not (eligible(old) or eligible(new)):
            continue
        patch = git(repo, 'diff', '--no-ext-diff', '--no-textconv', '--unified=0',
                    '--find-renames', parent, commit, '--', old, new).decode('utf-8', 'replace')
        hunks = [(int(start), int(length) if length else 1) for start, length in HUNK.findall(patch)]
        entities = sorted({entity for start, length in hunks
                           for entity in changed_entities(graph, old, start, length)})
        if not entities:
            entities = [old]
        fallback = old in entities or status.startswith('A')
        files.append({'old_path': old, 'new_path': new, 'status': status,
                      'parent_entities': [] if status.startswith('A') else entities,
                      'file_fallback': fallback, 'hunks': hunks,
                      'alias': {'from': old, 'to': new, 'method': 'git-rename',
                                'similarity_percent': int(status[1:])} if status.startswith('R') else None})
    total = len(files)
    return {'schema_version': 1, 'commit': commit, 'parent': parent, 'files': files,
            'coverage': {'changed_files': total, 'symbol_mapped': sum(not f['file_fallback'] for f in files),
                         'fallback_files': sum(f['file_fallback'] for f in files)},
            'parse_failures': graph['parse_failures']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', args.repo):
        parser.error('Expected owner/repository')
    key = args.repo.replace('/', '__')
    report = map_changes(ROOT / 'data/raw' / key, args.commit)
    write(ROOT / 'artifacts/reports' / (key + '-mapping.json'), report)
    print(json.dumps(report, indent=2))
