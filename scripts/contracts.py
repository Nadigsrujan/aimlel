"""Versioned artifact identity helpers shared by offline consumers."""
import hashlib
import json

SCHEMA_VERSION = 1


def identity(repo, revision, path, qualified_name='', kind='file'):
    """Snapshot identity is unambiguous even when symbols move or are renamed."""
    payload = [repo, revision, path, qualified_name, kind]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()


def artifact_key(repo, revision, parser_version, feature_version, history_cutoff):
    return hashlib.sha256(json.dumps([repo, revision, parser_version, feature_version,
                                     history_cutoff], separators=(',', ':')).encode()).hexdigest()


def changed_entities(graph, path, start, length):
    """Map parent-side diff spans; ambiguous/deleted boundaries fall back to file."""
    if length <= 0:
        return [path]
    end = start + length - 1
    symbols = [node for node in graph['nodes'] if node['path'] == path
               and node['kind'] != 'file' and node.get('start', end + 1) <= end
               and node.get('end', -1) >= start]
    return sorted({node['id'] for node in symbols}) or [path]
