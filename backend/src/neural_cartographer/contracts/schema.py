"""Versioned artifact identity helpers shared by offline consumers."""
import hashlib
import json

SCHEMA_VERSION = 1


def provenance(manifest, configuration, parser_version, feature_version, seed=17):
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return {'schema_version': SCHEMA_VERSION, 'manifest_sha256': digest(manifest),
            'configuration_sha256': digest(configuration), 'random_seed': seed,
            'parser_version': parser_version, 'feature_version': feature_version}


def entity_records(graph, repo, revision):
    """Revision identities omit line numbers; repeated definitions get ordinals.

    Legacy IDs remain only as an explicit compatibility key. Cross-revision
    continuity is represented separately by aliases, never guessed from an ID.
    """
    import re
    occurrences, records = {}, []
    for node in graph['nodes']:
        qualified = re.sub(r'@\d+(?=::|$)', '', node['id'][len(node['path']):]).lstrip(':')
        key = (node['path'], qualified, node['kind'])
        ordinal = occurrences.get(key, 0)
        occurrences[key] = ordinal + 1
        records.append({**node, 'legacy_id': node['id'],
                        'id': identity(repo, revision, node['path'], qualified + '#' + str(ordinal), node['kind']),
                        'qualified_name': qualified, 'occurrence': ordinal,
                        'repo': repo, 'revision': revision})
    return records


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
