"""Pinned local CodeBERT file embeddings with revision-addressed FAISS indexes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid
import subprocess
import sys
from neural_cartographer.ingest.pipeline import ROOT, eligible, git, write, public_repo_id
from neural_cartographer.graph.snapshots import blob_reader


def configuration():
    return json.loads((ROOT / 'configs/encoder.json').read_text())


def index_directory(repo_id, revision):
    public_repo_id('https://github.com/' + repo_id)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo_id) or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Expected owner/repository and full revision SHA')
    digest = hashlib.sha256(json.dumps(configuration(), sort_keys=True).encode()).hexdigest()[:16]
    return ROOT / 'data/processed' / repo_id.replace('/', '__') / revision / ('embeddings-' + digest)


def build(repo_id, revision, download=False):
    import numpy as np
    import torch
    from transformers import AutoModel, AutoTokenizer
    config = configuration()
    destination = index_directory(repo_id, revision)
    if (destination / 'manifest.json').exists():
        return json.loads((destination / 'manifest.json').read_text())
    repo = ROOT / 'data/raw' / repo_id.replace('/', '__')
    cache = ROOT / 'artifacts/encoders'
    options = {'revision': config['revision'], 'cache_dir': str(cache),
               'local_files_only': not download, 'trust_remote_code': False}
    tokenizer = AutoTokenizer.from_pretrained(config['model'], **options)
    model = AutoModel.from_pretrained(config['model'], **options).eval()
    torch.set_num_threads(2)
    paths, texts, vectors = [], [], []
    def flush():
        if not texts:
            return
        encoded = tokenizer(texts, padding=True, truncation=True,
                            max_length=config['max_tokens'], return_tensors='pt')
        with torch.inference_mode():
            hidden = model(**encoded).last_hidden_state
            mask = encoded['attention_mask'].unsqueeze(-1)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
        vectors.append(pooled.numpy().astype('float32'))
        texts.clear()
    with blob_reader(repo) as read:
        for entry in git(repo, 'ls-tree', '-r', '-z', revision).split(b'\0'):
            if not entry:
                continue
            metadata, rawpath = entry.split(b'\t', 1)
            mode, kind, blob = metadata.split()
            path = rawpath.decode('utf-8', 'surrogateescape')
            if mode == b'120000' or kind != b'blob' or not eligible(path):
                continue
            content = read(blob)
            if content is None:
                continue
            paths.append(path)
            texts.append(content.decode('utf-8', 'replace'))
            if len(texts) == config['batch_size']:
                flush()
    flush()
    if not paths:
        raise ValueError('Snapshot has no supported files to embed')
    matrix = np.concatenate(vectors)
    matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    # Publish the manifest last; incomplete writes are never treated as ready.
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / (uuid.uuid4().hex + '.npy')
    np.save(staging, matrix, allow_pickle=False)
    staging.replace(destination / 'vectors.npy')
    # macOS FAISS and PyTorch ship incompatible native OpenMP runtimes.
    # Keep them in separate processes rather than disabling runtime checks.
    subprocess.run([sys.executable, str(ROOT / 'scripts/vector_index.py'), 'build',
                    str(destination)], check=True, timeout=120)
    manifest = {'repo': repo_id, 'revision': revision, 'history_cutoff': revision,
                'encoder': config, 'paths': paths, 'dimension': int(matrix.shape[1]),
                'index_sha256': hashlib.sha256((destination / 'vectors.index').read_bytes()).hexdigest(),
                'limitations': ['First 256 tokens per file', 'File-level mean pooling',
                                'Pretraining corpus overlap has not been audited']}
    write(destination / 'manifest.json', manifest)
    return manifest


def similarities(repo_id, revision, seed):
    directory = index_directory(repo_id, revision)
    metadata = json.loads((directory / 'manifest.json').read_text())
    if metadata['revision'] != revision or metadata['history_cutoff'] != revision:
        raise ValueError('Semantic index cutoff mismatch')
    content = (directory / 'vectors.index').read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata['index_sha256']:
        raise ValueError('Semantic index checksum mismatch')
    paths = metadata['paths']
    if seed not in paths:
        raise ValueError('Seed has no cached semantic embedding')
    output = subprocess.check_output([sys.executable, str(ROOT / 'scripts/vector_index.py'),
                                      'query', str(directory), str(paths.index(seed))], timeout=120)
    return {paths[i]: score for i, score in json.loads(output) if paths[i] != seed}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--download', action='store_true', help='Allow pinned public encoder download')
    args = parser.parse_args()
    report = build(args.repo, args.revision, args.download)
    print(json.dumps({k: v for k, v in report.items() if k != 'paths'}, indent=2))
