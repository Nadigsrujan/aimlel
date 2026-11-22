"""Pre-registered v2 study: scaled development training, one fresh held-out test.

v1 modules are imported, never edited. The protocol in
configs/experiments/protocol-v2.json is written before training, and the five
fresh test projects stay unopened until the v2 freeze verifies.

Stages: pilot -> develop -> freeze -> evaluate. Each refuses to run out of order.
"""

import argparse
import concurrent.futures
import copy
import gc
import hashlib
import json
import random
import statistics
import sys
import time
import uuid
from pathlib import Path

from neural_cartographer.ingest.pipeline import ROOT, VERSION, write
from neural_cartographer.learning.portable_freeze import portable_digest

PROTOCOL = "configs/experiments/protocol-v2.json"
OUTPUT = "artifacts/models/v2"
DEVELOPMENT_REPORT = "artifacts/reports/v2-development.json"
FINAL_REPORT = "artifacts/reports/v2-final.json"
LEARNED = ("full-gnn", "history-gnn", "hybrid", "xgboost", "xgboost-ltr")
GNN_ARMS = ("full-gnn", "history-gnn")
# Files whose code determines a prepared example; other edits keep the cache.
FEATURE_SOURCES = (
    "ingest/pipeline.py",
    "graph/snapshots.py",
    "graph/structure.py",
    "graph/relations.py",
    "features/history.py",
    "features/embeddings.py",
    "candidates/ranking.py",
    "learning/heterogeneous.py",
)


def load_protocol(root=ROOT):
    return json.loads((root / PROTOCOL).read_text())


def manifest_for(repo, root=ROOT):
    return json.loads(
        (root / "data/manifests" / (repo.replace("/", "__") + ".json")).read_text()
    )


def stream_seed(seed, repo, stream):
    text = f"{seed}:{repo}:{stream}".encode()
    return int(hashlib.sha256(text).hexdigest()[:16], 16)


def one_seed_per_commit(queries):
    """Pick each commit's seed file by hash, not by alphabetical position."""
    chosen = {}
    for query in queries:
        rank = hashlib.sha256((query["commit"] + "\0" + query["seed"]).encode())
        best_ = chosen.get(query["commit"])
        if best_ is None or rank.hexdigest() < best_[0]:
            chosen[query["commit"]] = (rank.hexdigest(), query)
    return {commit: pair[1] for commit, pair in chosen.items()}


def sample(manifest, count, stream, seed, root=ROOT):
    """Seeded uniform sample of commits across the whole eligible history."""
    directory = (
        root
        / "data/processed"
        / manifest["repo"].replace("/", "__")
        / manifest["revision"]
    )
    with (directory / "queries.jsonl").open() as source:
        by_commit = one_seed_per_commit(json.loads(line) for line in source)
    commits = sorted(by_commit)
    rng = random.Random(stream_seed(seed, manifest["repo"], stream))
    picked = rng.sample(commits, min(count, len(commits)))
    return [by_commit[commit] for commit in sorted(picked)]


def source_digest():
    package = ROOT / "backend/src/neural_cartographer"
    digest = hashlib.sha256()
    for name in FEATURE_SOURCES:
        digest.update(name.encode() + b"\0" + portable_digest(package / name).encode())
    return digest.hexdigest()


def cache_path(manifest, query, semantic):
    from neural_cartographer.features.history import FEATURE_VERSION

    encoder = None
    if semantic:
        from neural_cartographer.features.embeddings import configuration

        encoder = configuration()
    key = hashlib.sha256(
        json.dumps(
            {
                "query": query,
                "semantic": semantic,
                "encoder": encoder,
                "python": list(sys.version_info[:2]),
                "pipeline": VERSION,
                "features": FEATURE_VERSION,
                "source": source_digest(),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    folder = ROOT / "data/interim/v2-examples" / manifest["repo"].replace("/", "__")
    return folder / (key + ".pt"), key


def prepare(manifest, query, semantic):
    """Build one parent-snapshot example; labels never reach the features."""
    import torch

    from neural_cartographer.candidates.ranking import analyze, rank
    from neural_cartographer.features.history import enrich, past_events
    from neural_cartographer.learning.heterogeneous import tensorize

    path, key = cache_path(manifest, query, semantic)
    if path.is_file():
        saved = torch.load(path, map_location="cpu", weights_only=True)
        if saved.get("cache_key") != key:
            raise ValueError("Example cache identity mismatch")
        return saved
    repo = manifest["repo"]
    folder = repo.replace("/", "__")
    started = time.monotonic()
    result = analyze(repo, query["seed"], query["commit"])
    if result["graph_revision"] != query["graph_revision"]:
        raise ValueError("Parent snapshot mismatch")
    graph_done = time.monotonic()
    files = [node["path"] for node in result["graph"]["nodes"] if node["kind"] == "file"]
    rows, _ = enrich(
        rank(files, query["seed"]),
        result["graph"],
        query["seed"],
        past_events(
            ROOT / "data/raw" / folder,
            result["graph_revision"],
            ROOT / "data/processed" / folder / manifest["revision"] / "events.jsonl",
        ),
    )
    result["candidates"] = rows
    history_done = time.monotonic()
    if semantic:
        from neural_cartographer.features.embeddings import attach_vectors, build

        build(repo, result["graph_revision"])
        attach_vectors(result)
    semantic_done = time.monotonic()
    batch = tensorize(result)
    prepared = {
        "repo": repo,
        "commit": query["commit"],
        "revision": query["graph_revision"],
        "seed": query["seed"],
        "batch": batch,
        "labels": torch.tensor(
            [float(path_ in query["positives"]) for path_ in batch["paths"]]
        ),
        "positives": query["positives"],
        "rows": rows,
        "timings": {
            "graph": graph_done - started,
            "history": history_done - graph_done,
            "semantic": semantic_done - history_done,
            "total": time.monotonic() - started,
        },
        "cache_key": key,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(uuid.uuid4().hex + ".tmp")
    torch.save(prepared, temporary)
    temporary.replace(path)
    return prepared


def prepare_to_cache(manifest, query, semantic):
    """Process-pool worker: build the cache file and return only its path."""
    sys.setrecursionlimit(10000)
    prepare(manifest, query, semantic)
    return str(cache_path(manifest, query, semantic)[0])


def prepare_all(manifest, queries, semantic, workers=1, label=""):
    """Prepare in parallel when possible; results keep the sampled order."""
    missing = [q for q in queries if not cache_path(manifest, q, semantic)[0].is_file()]
    # Each CodeBERT worker would load its own encoder; keep semantic work serial.
    if missing and workers > 1 and not semantic:
        from neural_cartographer.learning import research_v2 as module

        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(module.prepare_to_cache, manifest, q, semantic)
                for q in missing
            ]
            for done, future in enumerate(concurrent.futures.as_completed(futures), 1):
                future.result()
                if done % 10 == 0 or done == len(futures):
                    print(label, manifest["repo"], done, "/", len(futures), flush=True)
    examples = []
    for index, query in enumerate(queries, 1):
        examples.append(prepare(manifest, query, semantic))
        if missing and (workers == 1 or semantic) and index % 10 == 0:
            print(label, manifest["repo"], index, "/", len(queries), flush=True)
    return examples


def rose(rows):
    """ROSE-style association rules (Zimmermann et al. 2004) for one seed file.

    Confidence is support / (changes of the seed), and the seed count is the
    same for every candidate, so ordering by confidence equals ordering by
    support. Candidates without support keep a deterministic path order.
    """
    return [
        row["path"]
        for row in sorted(
            rows, key=lambda row: (-row["features"]["past_cochange_count"], row["path"])
        )
    ]


def fuse(first, second, weight, k=60):
    """Weighted reciprocal-rank fusion of two complete rankings."""
    left = {path: rank for rank, path in enumerate(first, 1)}
    right = {path: rank for rank, path in enumerate(second, 1)}
    if left.keys() != right.keys():
        raise ValueError("Fused rankings must cover the same candidates")
    return sorted(
        left,
        key=lambda path: (
            -((1 - weight) / (k + left[path]) + weight / (k + right[path])),
            path,
        ),
    )


def order(scores, paths):
    return [
        paths[i]
        for i in sorted(range(len(paths)), key=lambda i: (-float(scores[i]), paths[i]))
    ]


def rankings(example, models, hybrid=None):
    """Every system's full ranking for one example, on the same candidate pool."""
    import torch

    from neural_cartographer.features.history import RANKERS, rerank
    from neural_cartographer.learning.train import channel_examples

    batch, paths = example["batch"], example["batch"]["paths"]
    output = {
        name: [row["path"] for row in rerank(example["rows"], name, example["seed"])]
        for name in RANKERS
    }
    output["rose-v1"] = rose(example["rows"])
    with torch.inference_mode():
        output["full-gnn"] = order(models["full-gnn"](batch).numpy(), paths)
        masked = channel_examples([example], {"history"})[0]["batch"]
        output["history-gnn"] = order(models["history-gnn"](masked).numpy(), paths)
    pairs = batch["pairs"].numpy()
    output["xgboost"] = order(models["xgboost"].predict_proba(pairs)[:, 1], paths)
    output["xgboost-ltr"] = order(models["xgboost-ltr"].predict(pairs), paths)
    if hybrid:
        output["hybrid"] = fuse(
            output["cochange-v1"], output[hybrid["gnn"]], hybrid["weight"], hybrid["k"]
        )
    return output


def score(examples, models, hybrid=None):
    from neural_cartographer.evaluation.metrics import metrics

    rows = {}
    for example in examples:
        for name, ranked in rankings(example, models, hybrid).items():
            rows.setdefault(name, []).append(
                {
                    "repo": example["repo"],
                    "commit": example["commit"],
                    **metrics(ranked, example["positives"]),
                }
            )
    return rows


def macro(rows, metric):
    groups = {}
    for row in rows:
        groups.setdefault(row["repo"], []).append(row[metric])
    return statistics.mean(statistics.mean(values) for values in groups.values())


def best(rows, names):
    return max(
        names,
        key=lambda name: (
            macro(rows[name], "recall_at_5"),
            macro(rows[name], "ndcg_at_10"),
            name,
        ),
    )


def select_hybrid(examples, models, protocol):
    """Choose the hybrid's GNN and weight on selection queries only."""
    from neural_cartographer.evaluation.metrics import metrics

    settings = protocol["hybrid"]
    base = [(example, rankings(example, models)) for example in examples]
    trials = []
    for gnn in settings["gnn_choices"]:
        for weight in settings["weights"]:
            rows = [
                {
                    "repo": example["repo"],
                    "commit": example["commit"],
                    **metrics(
                        fuse(ranked["cochange-v1"], ranked[gnn], weight, settings["k"]),
                        example["positives"],
                    ),
                }
                for example, ranked in base
            ]
            trials.append(
                {
                    "gnn": gnn,
                    "weight": weight,
                    "recall_at_5": macro(rows, "recall_at_5"),
                    "ndcg_at_10": macro(rows, "ndcg_at_10"),
                }
            )
    # Ties prefer the smaller GNN weight, then the protocol's GNN order.
    chosen = max(
        trials,
        key=lambda t: (
            t["recall_at_5"],
            t["ndcg_at_10"],
            -t["weight"],
            -settings["gnn_choices"].index(t["gnn"]),
        ),
    )
    return {"gnn": chosen["gnn"], "weight": chosen["weight"], "k": settings["k"]}, trials


def summary(rows):
    keys = ("recall_at_5", "recall_at_10", "ndcg_at_10", "map_at_10", "mrr")
    return {
        "macro": {
            name: {metric: macro(values, metric) for metric in keys}
            for name, values in rows.items()
        },
        "per_repository": {
            name: {
                repo: {
                    metric: statistics.mean(
                        row[metric] for row in values if row["repo"] == repo
                    )
                    for metric in keys
                }
                for repo in sorted({row["repo"] for row in values})
            }
            for name, values in rows.items()
        },
    }


def development_examples(protocol, workers=None):
    sizes, seed = protocol["queries"], protocol["seed"]
    semantic = protocol["use_semantics"]
    workers = protocol["preparation_workers"] if workers is None else workers
    train, selection, calibration = [], [], []
    for repo in protocol["train_repositories"]:
        manifest = manifest_for(repo)
        queries = sample(manifest, sizes["train_per_repository"], "train", seed)
        train += prepare_all(manifest, queries, semantic, workers, "train")
    for repo in protocol["validation_repositories"]:
        manifest = manifest_for(repo)
        count = sizes["selection_per_repository"] + sizes["calibration_per_repository"]
        queries = sample(manifest, count, "validation", seed)
        selection += prepare_all(manifest, queries[::2], semantic, workers, "selection")
        calibration += prepare_all(
            manifest, queries[1::2], semantic, workers, "calibration"
        )
    keys = lambda rows: {(row["repo"], row["commit"]) for row in rows}
    if keys(selection) & keys(calibration):
        raise ValueError("Selection and calibration queries overlap")
    return train, selection, calibration


def query_record(example):
    return {
        key: example[key] for key in ("repo", "commit", "seed", "revision", "positives")
    } | {"candidate_files": len(example["batch"]["paths"])}


def ranking_loss(logits, labels, kind):
    """Pointwise weighted BCE (as in v1) or pairwise BPR over sampled pairs."""
    import torch

    if kind == "bce":
        weight = (len(labels) - labels.sum()) / labels.sum().clamp_min(1)
        return torch.nn.functional.binary_cross_entropy_with_logits(
            logits, labels, pos_weight=weight.clamp_min(1)
        )
    if kind == "bpr":
        positive, negative = logits[labels > 0], logits[labels == 0]
        if not negative.numel():
            return None
        return -torch.nn.functional.logsigmoid(
            positive[:, None] - negative[None, :]
        ).mean()
    raise ValueError("Unknown loss: " + kind)


def fit_ranker(train, selection, config, dimension, directory, name):
    """v1's training loop with a choice of loss and hidden size.

    Early stopping and checkpoint choice use selection queries only. An
    interrupted run resumes from its exact-input checkpoint.
    """
    import torch

    from neural_cartographer.learning.heterogeneous import HeterogeneousImpactModel
    from neural_cartographer.learning.train import fit_fingerprint, measure, sample_indices

    seed = config["seed"]
    torch.manual_seed(seed)
    model = HeterogeneousImpactModel(hidden=config["hidden"], semantic_dimension=dimension)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    best_score, best_state, stalled, history = -1, None, 0, []
    settings = {**config, "code": portable_digest(Path(__file__))}
    directory.mkdir(parents=True, exist_ok=True)
    checkpoint = directory / (
        name + "-" + fit_fingerprint(train, selection, settings, dimension, name) + ".pt"
    )
    if checkpoint.is_file():
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        model.load_state_dict(saved["model"])
        optimizer.load_state_dict(saved["optimizer"])
        best_score, best_state = saved["best"], saved["best_state"]
        stalled, history = saved["stalled"], saved["history"]
        torch.set_rng_state(saved["rng"])
        print("Resuming", name, "after", len(history), "epochs", flush=True)
    for epoch in range(len(history), config["epochs"]):
        if stalled >= config["patience"]:
            break
        model.train()
        losses = []
        for example in train:
            indices = sample_indices(example, config["negative_limit"], seed)
            labels = example["labels"][indices]
            if not labels.numel() or not labels.sum():
                continue
            optimizer.zero_grad()
            loss = ranking_loss(model(example["batch"])[indices], labels, config["loss"])
            if loss is None:
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            losses.append(float(loss.detach()))
        if not losses:
            raise ValueError("No training positives")
        rows = measure(model, selection)
        history.append(
            {
                "epoch": epoch + 1,
                "loss": statistics.mean(losses),
                "validation_macro_recall_at_5": macro(rows, "recall_at_5"),
            }
        )
        print(name, history[-1], flush=True)
        if history[-1]["validation_macro_recall_at_5"] > best_score:
            best_score = history[-1]["validation_macro_recall_at_5"]
            best_state, stalled = copy.deepcopy(model.state_dict()), 0
        else:
            stalled += 1
        temporary = checkpoint.with_name(uuid.uuid4().hex + ".tmp")
        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "best": best_score,
                "best_state": best_state,
                "stalled": stalled,
                "history": history,
                "rng": torch.get_rng_state(),
            },
            temporary,
        )
        temporary.replace(checkpoint)
    model.load_state_dict(best_state)
    model.eval()
    return model, history


def fit_variant(arm, loss, hidden):
    """Process-pool worker: train one GNN configuration from cached examples."""
    sys.setrecursionlimit(10000)
    import torch

    from neural_cartographer.learning.train import channel_examples, measure

    protocol = load_protocol()
    training = protocol["training"]
    torch.set_num_threads(training["training_threads"])
    torch.use_deterministic_algorithms(True)
    train, selection, _ = development_examples(protocol, workers=1)
    if arm == "history-gnn":
        train = channel_examples(train, {"history"})
        selection = channel_examples(selection, {"history"})
    dimension = train[0]["batch"]["semantic"].shape[1]
    config = {**training, "seed": protocol["seed"], "loss": loss, "hidden": hidden}
    name = f"{arm}-{loss}-{hidden}"
    model, trace = fit_ranker(
        train, selection, config, dimension, ROOT / OUTPUT / "progress", name
    )
    rows = measure(model, selection)
    path = ROOT / OUTPUT / "candidates" / (name + ".pt")
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "state_dict": model.state_dict(),
            "metadata": {
                "semantic_dimension": dimension,
                "hidden": hidden,
                "loss": loss,
                "arm": arm,
                "protocol": protocol["version"],
            },
        },
        path,
    )
    return {
        "arm": arm,
        "loss": loss,
        "hidden": hidden,
        "recall_at_5": macro(rows, "recall_at_5"),
        "ndcg_at_10": macro(rows, "ndcg_at_10"),
        "epochs": len(trace),
        "trace": trace,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
    }


def search(protocol):
    """Train every arm x loss x hidden-size variant in parallel processes."""
    from neural_cartographer.learning import research_v2 as module

    space = protocol["model_search"]
    variants = [
        (arm, loss, hidden)
        for arm in GNN_ARMS
        for loss in space["losses"]
        for hidden in space["hidden"]
    ]
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=min(len(variants), space["parallel_fits"])
    ) as pool:
        futures = [pool.submit(module.fit_variant, *variant) for variant in variants]
        results = [future.result() for future in futures]
    chosen = {}
    for arm in GNN_ARMS:
        # Ties prefer the smaller model, then the protocol's loss order.
        chosen[arm] = max(
            (r for r in results if r["arm"] == arm),
            key=lambda r: (
                r["recall_at_5"],
                r["ndcg_at_10"],
                -r["hidden"],
                -space["losses"].index(r["loss"]),
            ),
        )
    return chosen, results


def load_gnn(path):
    import torch

    from neural_cartographer.learning.heterogeneous import HeterogeneousImpactModel

    saved = torch.load(path, map_location="cpu", weights_only=True)
    metadata = saved["metadata"]
    model = HeterogeneousImpactModel(
        hidden=metadata["hidden"], semantic_dimension=metadata["semantic_dimension"]
    )
    model.load_state_dict(saved["state_dict"])
    model.eval()
    return model, saved


def develop():
    """Train every pre-registered system and choose the primary on validation."""
    import numpy as np
    import torch
    from sklearn.linear_model import LogisticRegression
    from xgboost import XGBClassifier, XGBRanker

    from neural_cartographer.evaluation.significance import slices
    from neural_cartographer.learning.train import sample_indices

    protocol = load_protocol()
    if (ROOT / OUTPUT / "freeze.json").exists():
        raise ValueError("v2 is frozen; development cannot change it")
    if protocol["use_semantics"]:
        raise ValueError("The pilot rule excluded CodeBERT; protocol must agree")
    seed, training = protocol["seed"], protocol["training"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    train, selection, calibration = development_examples(protocol)
    gc.collect()
    print("Prepared", len(train), "train,", len(selection), "selection,",
          len(calibration), "calibration queries", flush=True)
    chosen, results = search(protocol)
    models = {arm: load_gnn(ROOT / chosen[arm]["path"])[0] for arm in GNN_ARMS}
    torch.set_num_threads(training["training_threads"])
    torch.use_deterministic_algorithms(True)
    x, y, groups = [], [], []
    for example in train:
        indices = sample_indices(example, training["negative_limit"], seed)
        x.append(example["batch"]["pairs"][indices].numpy())
        y.append(example["labels"][indices].numpy())
        groups.append(len(indices))
    common = {
        "n_estimators": 100,
        "max_depth": 3,
        "learning_rate": 0.05,
        "random_state": seed,
        "n_jobs": 2,
    }
    booster = XGBClassifier(eval_metric="logloss", **common)
    booster.fit(np.concatenate(x), np.concatenate(y))
    ranker = XGBRanker(objective="rank:ndcg", **common)
    ranker.fit(np.concatenate(x), np.concatenate(y), group=groups)
    models["xgboost"], models["xgboost-ltr"] = booster, ranker
    hybrid, trials = select_hybrid(selection, models, protocol)
    rows = score(selection, models, hybrid)
    baselines = [name for name in rows if name not in LEARNED]
    choice = {
        "primary": best(rows, LEARNED),
        "baseline": best(rows, baselines),
        "hybrid": hybrid,
        "gnn_variants": {
            arm: {key: chosen[arm][key] for key in ("loss", "hidden")} for arm in GNN_ARMS
        },
        "rule": protocol["selection_rule"],
    }
    logits, labels = [], []
    with torch.inference_mode():
        for example in calibration:
            logits += models["full-gnn"](example["batch"]).tolist()
            labels += example["labels"].tolist()
    calibrator = LogisticRegression(random_state=seed, solver="liblinear").fit(
        np.array(logits).reshape(-1, 1), labels
    )
    output = ROOT / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for arm, filename in (("full-gnn", "full.pt"), ("history-gnn", "history.pt")):
        torch.save(load_gnn(ROOT / chosen[arm]["path"])[1], output / filename)
    booster.save_model(output / "xgboost.json")
    ranker.save_model(output / "xgboost-ltr.json")
    write(
        output / "calibration.json",
        {
            "coefficient": calibrator.coef_.tolist(),
            "intercept": calibrator.intercept_.tolist(),
            "system": "full-gnn",
        },
    )
    write(output / "selection.json", choice)
    audit = [{**query_record(e), "positive_paths": e["positives"]} for e in selection]
    timings = [example["timings"] for example in train + selection + calibration]
    report = {
        "status": "v2 development; every choice made on validation selection queries",
        "choice": choice,
        "model_search": [
            {key: value for key, value in r.items() if key != "trace"} for r in results
        ],
        "training_history": {f"{r['arm']}-{r['loss']}-{r['hidden']}": r["trace"] for r in results},
        "hybrid_trials": trials,
        **summary(rows),
        "selection_slices": {
            metric: slices(rows[choice["primary"]], rows[choice["baseline"]], audit, metric)
            for metric in ("recall_at_5", "ndcg_at_10")
        },
        "selection_rows": rows,
        "queries": {
            "train": [query_record(e) for e in train],
            "selection": [query_record(e) for e in selection],
            "calibration": [query_record(e) for e in calibration],
        },
        "mean_preparation_seconds": {
            stage: statistics.mean(t[stage] for t in timings) for stage in timings[0]
        },
    }
    write(ROOT / DEVELOPMENT_REPORT, report)
    print(json.dumps({"choice": choice, "macro": report["macro"]}, indent=2))
    return report


def frozen_files(protocol, root=ROOT):
    files = [
        PROTOCOL,
        "configs/repositories.json",
        "configs/encoder.json",
        DEVELOPMENT_REPORT,
        "scripts/research_v2.py",
    ] + [
        OUTPUT + "/" + name
        for name in (
            "full.pt",
            "history.pt",
            "xgboost.json",
            "xgboost-ltr.json",
            "calibration.json",
            "selection.json",
        )
    ]
    files += sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in (root / "backend/src").rglob("*.py")
    )
    for repo in protocol["train_repositories"] + protocol["validation_repositories"]:
        manifest = manifest_for(repo, root)
        folder = f"data/processed/{repo.replace('/', '__')}/{manifest['revision']}/"
        summary_ = json.loads((root / (folder + "summary.json")).read_text())
        files += ["data/manifests/" + repo.replace("/", "__") + ".json"]
        files += [folder + "summary.json"] + [folder + name for name in summary_["checksums"]]
    return files


def freeze(root=ROOT):
    """Bind protocol, code, data and models before any fresh project is opened."""
    protocol = load_protocol(root)
    opened = [
        repo
        for repo in protocol["test_repositories"]
        if (root / "data/raw" / repo.replace("/", "__")).exists()
        or (root / "data/manifests" / (repo.replace("/", "__") + ".json")).exists()
    ]
    if opened:
        raise ValueError("Fresh test projects were opened before the freeze: " + ", ".join(opened))
    record = {
        "version": protocol["version"],
        "test_repositories": protocol["test_repositories"],
        "test_per_repository": protocol["queries"]["test_per_repository"],
        "choice": json.loads((root / OUTPUT / "selection.json").read_text()),
        "hashes": {
            name: portable_digest(root / name) for name in frozen_files(protocol, root)
        },
    }
    destination = root / OUTPUT / "freeze.json"
    if destination.exists():
        if json.loads(destination.read_text()) != record:
            raise ValueError("A different v2 protocol is already frozen")
        return record
    write(destination, record)
    return record


def verify_freeze(root=ROOT):
    record = json.loads((root / OUTPUT / "freeze.json").read_text())
    for name, checksum in record["hashes"].items():
        if portable_digest(root / name) != checksum:
            raise ValueError("Frozen v2 artifact changed: " + name)
    return record


def load_models(root=ROOT):
    from xgboost import XGBClassifier, XGBRanker

    models = {
        "full-gnn": load_gnn(root / OUTPUT / "full.pt")[0],
        "history-gnn": load_gnn(root / OUTPUT / "history.pt")[0],
    }
    booster = XGBClassifier()
    booster.load_model(root / OUTPUT / "xgboost.json")
    ranker = XGBRanker()
    ranker.load_model(root / OUTPUT / "xgboost-ltr.json")
    models["xgboost"], models["xgboost-ltr"] = booster, ranker
    return models


def calibration_report(examples, model, root=ROOT):
    import numpy as np
    import torch
    from sklearn.metrics import average_precision_score, brier_score_loss

    saved = json.loads((root / OUTPUT / "calibration.json").read_text())
    probabilities, labels = [], []
    with torch.inference_mode():
        for example in examples:
            logits = model(example["batch"]).numpy()
            scaled = logits * saved["coefficient"][0][0] + saved["intercept"][0]
            probabilities += (1 / (1 + np.exp(-np.clip(scaled, -60, 60)))).tolist()
            labels += example["labels"].tolist()
    return {
        "system": saved["system"],
        "brier": float(brier_score_loss(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "pairs": len(labels),
    }


def evaluate(root=ROOT):
    """The single fresh test. It refuses to run twice or without the freeze."""
    import torch

    from neural_cartographer.evaluation.significance import compare, holm, slices
    from neural_cartographer.ingest.pipeline import process

    record = verify_freeze(root)
    destination = root / FINAL_REPORT
    if destination.exists():
        raise ValueError("v2 results already exist; the fresh test runs once")
    protocol = load_protocol(root)
    torch.set_num_threads(protocol["training"]["training_threads"])
    torch.use_deterministic_algorithms(True)
    models = load_models(root)
    choice = record["choice"]
    examples, pins = [], {}
    for repo in protocol["test_repositories"]:
        print("Ingesting fresh test project", repo, flush=True)
        result = process(repo, protocol["test_split_name"], clone=True, reuse=True)
        if result["status"] != "processed":
            raise ValueError("Ingestion failed: " + repo)
        manifest = manifest_for(repo, root)
        pins[repo] = manifest["revision"]
        queries = sample(
            manifest, record["test_per_repository"], "test", protocol["seed"], root
        )
        examples += prepare_all(
            manifest,
            queries,
            protocol["use_semantics"],
            protocol["preparation_workers"],
            "test",
        )
    verify_freeze(root)
    rows = score(examples, models, choice["hybrid"])
    primary, baseline = choice["primary"], choice["baseline"]
    audit = [{**query_record(e), "positive_paths": e["positives"]} for e in examples]
    comparisons = {}
    for metric in ("recall_at_5", "ndcg_at_10"):
        results = {
            other: compare(rows[primary], rows[other], metric)
            for other in sorted(rows)
            if other != primary
        }
        adjusted = holm({name: row["sign_flip_p"] for name, row in results.items()})
        for name, row in results.items():
            row["holm_p"] = adjusted[name]
        comparisons[metric] = results
    gate = comparisons["recall_at_5"][baseline]
    report = {
        "status": "v2 frozen fresh-project evaluation; reported whatever the outcome",
        "freeze_sha256": portable_digest(root / OUTPUT / "freeze.json"),
        "pinned_revisions": pins,
        "choice": choice,
        **summary(rows),
        "comparisons": comparisons,
        "pre_registered_gate": {
            "rule": protocol["success_gate"],
            "difference": gate["difference"],
            "sign_flip_p": gate["sign_flip_p"],
            "met": gate["difference"] > 0 and gate["sign_flip_p"] < 0.05,
        },
        "slices": {
            metric: slices(rows[primary], rows[baseline], audit, metric)
            for metric in ("recall_at_5", "ndcg_at_10")
        },
        "calibration": calibration_report(examples, models["full-gnn"], root),
        "rows": rows,
        "queries": audit,
    }
    write(destination, report)
    print(json.dumps({"gate": report["pre_registered_gate"], "macro": report["macro"]}, indent=2))
    return report


def pilot(per_repository=20, semantic_per_repository=3):
    """Measure preparation cost per stage on development projects only."""
    protocol = load_protocol()
    repos = protocol["train_repositories"] + protocol["validation_repositories"]
    report = {"status": "development cost pilot", "repositories": {}}
    for repo in repos:
        manifest = manifest_for(repo)
        queries = sample(manifest, per_repository, "pilot", protocol["seed"])
        plain = prepare_all(manifest, queries, False, protocol["preparation_workers"], "pilot")
        semantic = []
        for query in queries[:semantic_per_repository]:
            try:
                semantic.append(prepare(manifest, query, True)["timings"])
            except (OSError, ValueError) as exc:
                report.setdefault("semantic_failures", []).append(
                    {"repo": repo, "error": str(exc)}
                )
        report["repositories"][repo] = {
            "queries": len(plain),
            "mean_graph_seconds": statistics.mean(e["timings"]["graph"] for e in plain),
            "mean_history_seconds": statistics.mean(e["timings"]["history"] for e in plain),
            "mean_candidates": statistics.mean(len(e["batch"]["paths"]) for e in plain),
            "semantic_samples": len(semantic),
            "mean_semantic_seconds": statistics.mean(t["semantic"] for t in semantic)
            if semantic
            else None,
        }
        print(repo, report["repositories"][repo], flush=True)
    write(ROOT / "artifacts/reports/v2-pilot.json", report)
    return report


def main():
    sys.setrecursionlimit(10000)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["pilot", "develop", "freeze", "verify", "evaluate"])
    args = parser.parse_args()
    if args.stage == "pilot":
        pilot()
    elif args.stage == "develop":
        develop()
    elif args.stage == "freeze":
        print("Frozen", len(freeze()["hashes"]), "v2 artifacts")
    elif args.stage == "verify":
        print("Verified", len(verify_freeze()["hashes"]), "v2 artifacts")
    else:
        evaluate()


if __name__ == "__main__":
    main()
