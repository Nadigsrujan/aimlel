"""Static import resolution with explicit unresolved evidence."""
from pathlib import PurePosixPath


def resolve_imports(graph):
    paths = {n['path'] for n in graph['nodes'] if n['kind'] == 'file'}
    modules = {}
    for path in sorted(paths):
        name = path[:-3].replace('/', '.')
        if name.endswith('.__init__'):
            name = name[:-9]
        modules.setdefault(name, []).append(path)
    resolved, unresolved = [], []
    for edge in graph['edges']:
        if edge['relation'] != 'IMPORTS':
            continue
        source, target = edge['source'], edge['target']
        if edge.get('resolution') == 'statement_text':
            unresolved.append(edge)
            continue
        if target.startswith('.'):
            level = len(target) - len(target.lstrip('.'))
            package = list(PurePosixPath(source).parent.parts)
            if level > len(package):
                unresolved.append(edge)
                continue
            package = package[:len(package) - level + 1]
            suffix = target[level:]
            target = '.'.join(package + ([suffix] if suffix else []))
        matches = modules.get(target, [])
        if len(matches) == 1:
            resolved.append({**edge, 'target': matches[0], 'module': edge['target'],
                             'resolution': 'exact-static-module'})
        else:
            unresolved.append(edge)
    return resolved, unresolved
