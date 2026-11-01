"""Pinned local CodeBERT file embeddings with revision-addressed FAISS indexes."""

import argparse
import hashlib
import json
import re
import uuid
import subprocess
import sys
import os
from functools import lru_cache
from neural_cartographer.ingest.pipeline import (
    ROOT,
    eligible,
    git,
    write,
    public_repo_id,
)
from neural_cartographer.graph.snapshots import blob_reader


def configuration():
    return json.loads((ROOT / "configs/encoder.json").read_text())


def index_directory(repo_id, revision):
    public_repo_id("https://github.com/" + repo_id)
    if not re.fullmatch(
        r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_id
    ) or not re.fullmatch("[0-9a-f]{40}", revision):
        raise ValueError("Expected owner/repository and full revision SHA")
    digest = hashlib.sha256(
        json.dumps(configuration(), sort_keys=True).encode()
    ).hexdigest()[:16]
    return (
        ROOT
        / "data/processed"
        / repo_id.replace("/", "__")
        / revision
        / ("embeddings-" + digest)
    )


@lru_cache(maxsize=1)
def encoder(config_json, download=False):
    from transformers import AutoModel, AutoTokenizer

    config = json.loads(config_json)
    options = {
        "revision": config["revision"],
        "cache_dir": str(ROOT / "artifacts/encoders"),
        "local_files_only": not download,
        "trust_remote_code": False,
    }
    return (
        AutoTokenizer.from_pretrained(config["model"], **options),
        AutoModel.from_pretrained(config["model"], **options).eval(),
    )


def build(repo_id, revision, download=False):
    import numpy as np
    import torch

    config = configuration()
    destination = index_directory(repo_id, revision)
    if (destination / "manifest.json").exists():
        return json.loads((destination / "manifest.json").read_text())
    repo = ROOT / "data/raw" / repo_id.replace("/", "__")
    config_json = json.dumps(config, sort_keys=True)
    tokenizer, model = encoder(config_json, download)
    cache = (
        ROOT
        / "artifacts/encoders/blob-vectors"
        / hashlib.sha256(config_json.encode()).hexdigest()
    )
    cache.mkdir(parents=True, exist_ok=True)
    threads = min(8, os.cpu_count() or 1)
    torch.set_num_threads(threads)
    paths, texts, vectors, pending = [], [], [], []

    def flush():
        if not texts:
            return
        encoded = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=config["max_tokens"],
            return_tensors="pt",
        )
        with torch.inference_mode():
            hidden = model(**encoded).last_hidden_state
            mask = encoded["attention_mask"].unsqueeze(-1)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp_min(1)
        for (position, cache_path), vector in zip(
            pending, pooled.numpy().astype("float32")
        ):
            vector /= max(float(np.linalg.norm(vector)), 1e-12)
            vectors[position] = vector
            temporary = cache_path.with_name(uuid.uuid4().hex + ".npy")
            np.save(temporary, vector, allow_pickle=False)
            temporary.replace(cache_path)
        texts.clear()
        pending.clear()

    with blob_reader(repo) as read:
        for entry in git(repo, "ls-tree", "-r", "-z", revision).split(b"\0"):
            if not entry:
                continue
            metadata, rawpath = entry.split(b"\t", 1)
            mode, kind, blob = metadata.split()
            path = rawpath.decode("utf-8", "surrogateescape")
            if mode == b"120000" or kind != b"blob" or not eligible(path):
                continue
            content = read(blob)
            if content is None:
                continue
            paths.append(path)
            cache_path = cache / (blob.decode("ascii") + ".npy")
            if cache_path.is_file():
                vectors.append(np.load(cache_path, allow_pickle=False))
                continue
            pending.append((len(vectors), cache_path))
            vectors.append(None)
            texts.append(content.decode("utf-8", "replace"))
            if len(texts) == config["batch_size"]:
                flush()
    flush()
    if not paths:
        raise ValueError("Snapshot has no supported files to embed")
    matrix = np.stack(vectors)
    matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    # Publish the manifest last; incomplete writes are never treated as ready.
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / (uuid.uuid4().hex + ".npy")
    np.save(staging, matrix, allow_pickle=False)
    staging.replace(destination / "vectors.npy")
    # macOS FAISS and PyTorch ship incompatible native OpenMP runtimes.
    # Keep them in separate processes rather than disabling runtime checks.
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/vector_index.py"),
            "build",
            str(destination),
        ],
        check=True,
        timeout=120,
    )
    manifest = {
        "repo": repo_id,
        "revision": revision,
        "history_cutoff": revision,
        "encoder": config,
        "paths": paths,
        "dimension": int(matrix.shape[1]),
        'execution_threads':threads,
        "index_sha256": hashlib.sha256(
            (destination / "vectors.index").read_bytes()
        ).hexdigest(),
        "vectors_sha256": hashlib.sha256(
            (destination / "vectors.npy").read_bytes()
        ).hexdigest(),
        "limitations": [
            "First 256 tokens per file",
            "File-level mean pooling",
            "Pretraining corpus overlap has not been audited",
        ],
    }
    write(destination / "manifest.json", manifest)
    return manifest


def load_vectors(repo_id, revision):
    import numpy as np

    directory = index_directory(repo_id, revision)
    metadata = json.loads((directory / "manifest.json").read_text())
    if metadata["revision"] != revision or metadata["history_cutoff"] != revision:
        raise ValueError("Semantic index cutoff mismatch")
    content = (directory / "vectors.npy").read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata.get("vectors_sha256"):
        raise ValueError(
            "Embedding matrix checksum missing or mismatched; rebuild this index"
        )
    matrix = np.load(directory / "vectors.npy", allow_pickle=False)
    if (
        matrix.shape != (len(metadata["paths"]), metadata["dimension"])
        or not np.isfinite(matrix).all()
    ):
        raise ValueError("Invalid semantic matrix shape or values")
    return dict(zip(metadata["paths"], matrix))


def attach_vectors(result):
    vectors = load_vectors(result["repo"], result["graph_revision"])
    seed = vectors[result["seed"]]
    for row in result["candidates"]:
        if row["path"] not in vectors:
            raise ValueError(
                "Semantic index does not cover the complete candidate pool"
            )
        row["features"]["semantic_cosine"] = float(seed @ vectors[row["path"]])
        if "semantic" not in row.setdefault("channels", []):
            row["channels"].append("semantic")
    result["node_embeddings"] = vectors
    return result


def similarities(repo_id, revision, seed):
    directory = index_directory(repo_id, revision)
    metadata = json.loads((directory / "manifest.json").read_text())
    if metadata["revision"] != revision or metadata["history_cutoff"] != revision:
        raise ValueError("Semantic index cutoff mismatch")
    content = (directory / "vectors.index").read_bytes()
    if hashlib.sha256(content).hexdigest() != metadata["index_sha256"]:
        raise ValueError("Semantic index checksum mismatch")
    paths = metadata["paths"]
    if seed not in paths:
        raise ValueError("Seed has no cached semantic embedding")
    output = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "scripts/vector_index.py"),
            "query",
            str(directory),
            str(paths.index(seed)),
        ],
        timeout=120,
    )
    return {paths[i]: score for i, score in json.loads(output) if paths[i] != seed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument(
        "--download", action="store_true", help="Allow pinned public encoder download"
    )
    args = parser.parse_args()
    report = build(args.repo, args.revision, args.download)
    print(json.dumps({k: v for k, v in report.items() if k != "paths"}, indent=2))
