"""Train typed GraphSAGE/XGBoost on training projects; select on validation only."""

import copy
import gc
import hashlib
import json
import random
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from xgboost import XGBClassifier

from neural_cartographer.candidates.ranking import analyze, rank
from neural_cartographer.contracts.schema import provenance
from neural_cartographer.evaluation.metrics import macro_bootstrap, metrics
from neural_cartographer.features.history import (
    FEATURE_VERSION,
    RANKERS,
    enrich,
    past_events,
    rerank,
)
from neural_cartographer.ingest.pipeline import ROOT, VERSION, write
from neural_cartographer.learning.heterogeneous import (
    PAIR_FEATURES,
    RELATIONS,
    HeterogeneousImpactModel,
    tensorize,
)


def examples(manifest, limit, semantic=False):
    if manifest["split"] == "test":
        from neural_cartographer.learning.research import verify_freeze

        verify_freeze()
    repo = manifest["repo"]
    key = repo.replace("/", "__")
    directory = ROOT / "data/processed" / key / manifest["revision"]
    by_commit = {}
    with (directory / "queries.jsonl").open() as stream:
        for line in stream:
            query = json.loads(line)
            by_commit.setdefault(query["commit"], query)
    # One seed per complete commit. Preserve chronological/topological order.
    selected = list(by_commit.values())[-limit:]
    source_digest = hashlib.sha256()
    for source in sorted(Path(__file__).parents[1].rglob("*.py")):
        source_digest.update(source.read_bytes())
    encoder_configuration = None
    if semantic:
        from neural_cartographer.features.embeddings import configuration

        encoder_configuration = configuration()
    cache_directory = ROOT / "data/interim/learning-examples" / key
    cache_directory.mkdir(parents=True, exist_ok=True)
    for query in selected:
        started = time.monotonic()
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "query": query,
                    "semantic": semantic,
                    "encoder": encoder_configuration,
                    "python": list(sys.version_info[:2]),
                    "pipeline": VERSION,
                    "features": FEATURE_VERSION,
                    "source": source_digest.hexdigest(),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cache_path = cache_directory / (cache_key + ".pt")
        if cache_path.is_file():
            saved = torch.load(cache_path, map_location="cpu", weights_only=True)
            if saved.get("cache_key") != cache_key:
                raise ValueError("Training-example cache identity mismatch")
            print("Loaded features", repo, query["commit"][:10], flush=True)
            yield saved
            continue
        result = analyze(repo, query["seed"], query["commit"])
        paths = [
            node["path"] for node in result["graph"]["nodes"] if node["kind"] == "file"
        ]
        rows, _ = enrich(
            rank(paths, query["seed"]),
            result["graph"],
            query["seed"],
            past_events(
                ROOT / "data/raw" / key,
                result["graph_revision"],
                directory / "events.jsonl",
            ),
        )
        result["candidates"] = rows
        if semantic:
            from neural_cartographer.features.embeddings import attach_vectors, build

            build(repo, result["graph_revision"])
            attach_vectors(result)
        batch = tensorize(result)
        labels = torch.tensor(
            [float(path in query["positives"]) for path in batch["paths"]]
        )
        prepared = {
            "repo": repo,
            "commit": query["commit"],
            "revision": query["graph_revision"],
            "seed": query["seed"],
            "batch": batch,
            "labels": labels,
            "positives": query["positives"],
            "rows": rows,
            "seconds": time.monotonic() - started,
            "cache_key": cache_key,
        }
        temporary = cache_path.with_name(uuid.uuid4().hex + ".pt")
        torch.save(prepared, temporary)
        temporary.replace(cache_path)
        print("Prepared features", repo, query["commit"][:10], flush=True)
        yield prepared


def sample_indices(example, maximum, seed):
    labels = example["labels"]
    positives = torch.where(labels > 0)[0].tolist()
    negatives = torch.where(labels == 0)[0].tolist()
    # First half: hardest fixed directory neighbors; remainder: deterministic random.
    hard = negatives[: maximum // 2]
    rng = random.Random(seed + int(example["commit"][:8], 16))
    rest = negatives[maximum // 2 :]
    selected = positives + hard + rng.sample(rest, min(len(rest), maximum - len(hard)))
    return torch.tensor(sorted(selected), dtype=torch.long)


def macro(rows, metric):
    grouped = {}
    for row in rows:
        grouped.setdefault(row["repo"], []).append(row[metric])
    return (
        sum(sum(values) / len(values) for values in grouped.values()) / len(grouped)
        if grouped
        else 0
    )


def measure(model, examples_, baseline=None):
    model.eval()
    rows = []
    with torch.inference_mode():
        for example in examples_:
            started = time.monotonic()
            scores = (
                model(example["batch"]).numpy()
                if baseline is None
                else baseline.predict_proba(example["batch"]["pairs"].numpy())[:, 1]
            )
            indices = sorted(
                range(len(scores)),
                key=lambda i: (-float(scores[i]), example["batch"]["paths"][i]),
            )
            paths = [example["batch"]["paths"][i] for i in indices]
            rows.append(
                {
                    "repo": example["repo"],
                    "commit": example["commit"],
                    "inference_seconds": time.monotonic() - started,
                    **metrics(paths, example["positives"]),
                }
            )
    return rows


def channel_examples(examples_, channels):
    """Create isolated ablation inputs without mutating the shared query pool."""
    output = []
    for example in examples_:
        batch = example["batch"]
        masked = {
            **batch,
            "x": batch["x"].clone(),
            "pairs": batch["pairs"].clone(),
            "edges": dict(batch["edges"]),
        }
        if "semantic" in batch:
            masked["semantic"] = batch["semantic"].clone()
        if "static" not in channels:
            masked["x"][:, :8] = 0
            masked["pairs"][:, :2] = 0
            for relation in masked["edges"]:
                if relation != "cochange":
                    masked["edges"][relation] = torch.empty((2, 0), dtype=torch.long)
        if "history" not in channels:
            masked["pairs"][:, 2:6] = 0
            masked["edges"]["cochange"] = torch.empty((2, 0), dtype=torch.long)
        if "semantic" not in channels:
            if "semantic" in masked:
                masked["semantic"].zero_()
            masked["pairs"][:, 6] = 0
        output.append({**example, "batch": masked})
    return output


def fit_fingerprint(train, selection, config, semantic_dimension, name):
    digest = hashlib.sha256()

    def update(value):
        if torch.is_tensor(value):
            digest.update(str((value.dtype, tuple(value.shape))).encode())
            digest.update(value.detach().cpu().contiguous().numpy().tobytes())
        elif isinstance(value, dict):
            for key in sorted(value):
                update(key)
                update(value[key])
        elif isinstance(value, (list, tuple)):
            for item in value:
                update(item)
        else:
            digest.update(json.dumps(value, sort_keys=True).encode())
        digest.update(b"\0")

    update([config, semantic_dimension, name, str(torch.__version__)])
    for file in (
        Path(__file__),
        Path(__file__).with_name("heterogeneous.py"),
        Path(__file__).with_name("layers.py"),
    ):
        digest.update(file.read_bytes())
    for examples_ in (train, selection):
        for example in examples_:
            update(
                {
                    key: example[key]
                    for key in (
                        "repo",
                        "commit",
                        "seed",
                        "batch",
                        "labels",
                        "positives",
                    )
                }
            )
    return digest.hexdigest()


def fit_model(
    train, selection, config, semantic_dimension, checkpoint_directory=None, name="full"
):
    seed = config["seed"]
    torch.manual_seed(seed)
    model = HeterogeneousImpactModel(semantic_dimension=semantic_dimension)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"])
    best, best_state, stalled, history = -1, None, 0, []
    checkpoint = None
    if checkpoint_directory is not None:
        fingerprint = fit_fingerprint(
            train, selection, config, semantic_dimension, name
        )
        checkpoint_directory.mkdir(parents=True, exist_ok=True)
        checkpoint = checkpoint_directory / (name + "-" + fingerprint + ".pt")
        if checkpoint.is_file():
            saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
            model.load_state_dict(saved["model"])
            optimizer.load_state_dict(saved["optimizer"])
            best, best_state, stalled, history = (
                saved["best"],
                saved["best_state"],
                saved["stalled"],
                saved["history"],
            )
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
            logits = model(example["batch"])[indices]
            weight = (len(labels) - labels.sum()) / labels.sum().clamp_min(1)
            loss = torch.nn.functional.binary_cross_entropy_with_logits(
                logits, labels, pos_weight=weight.clamp_min(1)
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5)
            optimizer.step()
            losses.append(float(loss.detach()))
        if not losses:
            raise ValueError("No training positives")
        score = macro(measure(model, selection), "recall_at_5")
        history.append(
            {
                "epoch": epoch + 1,
                "loss": sum(losses) / len(losses),
                "validation_macro_recall_at_5": score,
            }
        )
        print(history[-1], flush=True)
        if score > best:
            best, best_state, stalled = score, copy.deepcopy(model.state_dict()), 0
        else:
            stalled += 1
        if checkpoint is not None:
            temporary = checkpoint.with_name(uuid.uuid4().hex + ".pt")
            torch.save(
                {
                    "model": model.state_dict(),
                    "optimizer": optimizer.state_dict(),
                    "best": best,
                    "best_state": best_state,
                    "stalled": stalled,
                    "history": history,
                    "rng": torch.get_rng_state(),
                },
                temporary,
            )
            temporary.replace(checkpoint)
        if stalled >= config["patience"]:
            break
    model.load_state_dict(best_state)
    model.eval()
    return model, history


def run():
    config = json.loads((ROOT / "configs/experiments/heterogeneous.json").read_text())
    seed = config["seed"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config.get("training_threads", 2))
    torch.use_deterministic_algorithms(True)
    manifests = [
        json.loads(path.read_text())
        for path in sorted((ROOT / "data/manifests").glob("*.json"))
    ]
    train, validation = [], []
    failures = []
    for manifest in manifests:
        if manifest["split"] not in ("train", "validation"):
            continue
        limit = (
            config["commits_per_training_repo"]
            if manifest["split"] == "train"
            else config["commits_per_validation_repo"]
        )
        print("Preparing", manifest["repo"], flush=True)
        try:
            rows = list(examples(manifest, limit, config.get("use_semantics", False)))
            (train if manifest["split"] == "train" else validation).extend(rows)
        except (OSError, ValueError) as exc:
            failures.append({"repo": manifest["repo"], "error": str(exc)})
    if failures or not train or len(validation) < 4:
        write(
            ROOT / "artifacts/reports/heterogeneous-preparation-failures.json", failures
        )
        raise ValueError(
            "Incomplete training/validation corpus; refusing to select a model"
        )
    selection, calibration = validation[::2], validation[1::2]
    if config.get("use_semantics"):
        from neural_cartographer.features.embeddings import encoder

        encoder.cache_clear()
        gc.collect()
    torch.set_num_threads(config.get("training_threads", 2))
    semantic_dimension = train[0]["batch"]["semantic"].shape[1]
    checkpoint_directory = ROOT / "artifacts/models/heterogeneous-development/progress"
    model, history = fit_model(
        train, selection, config, semantic_dimension, checkpoint_directory
    )
    x, y = [], []
    for example in train:
        indices = sample_indices(example, config["negative_limit"], seed)
        x.append(example["batch"]["pairs"][indices].numpy())
        y.append(example["labels"][indices].numpy())
    baseline = XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.05,
        random_state=seed,
        n_jobs=2,
        eval_metric="logloss",
    )
    baseline.fit(np.concatenate(x), np.concatenate(y))
    comparison = {
        "heterogeneous": measure(model, selection),
        "xgboost": measure(model, selection, baseline),
    }
    ablation_history, ablation_states = {}, {}
    for channel in config.get("ablations", []):
        print("Training ablation", channel, flush=True)
        masked_train = channel_examples(train, {channel})
        masked_selection = channel_examples(selection, {channel})
        ablated, trace = fit_model(
            masked_train,
            masked_selection,
            config,
            semantic_dimension,
            checkpoint_directory,
            channel,
        )
        comparison[channel + "-only"] = measure(ablated, masked_selection)
        ablation_history[channel] = trace
        ablation_states[channel] = copy.deepcopy(ablated.state_dict())
        del masked_train, masked_selection, ablated
    for name in RANKERS:
        comparison[name] = [
            {
                "repo": example["repo"],
                "commit": example["commit"],
                **metrics(
                    [
                        row["path"]
                        for row in rerank(example["rows"], name, example["seed"])
                    ],
                    example["positives"],
                ),
            }
            for example in selection
        ]
    if config.get("use_semantics"):
        comparison["semantic-v1"] = [
            {
                "repo": example["repo"],
                "commit": example["commit"],
                **metrics(
                    [
                        row["path"]
                        for row in sorted(
                            example["rows"],
                            key=lambda row: (
                                -row["features"]["semantic_cosine"],
                                row["path"],
                            ),
                        )
                    ],
                    example["positives"],
                ),
            }
            for example in selection
        ]
    scores, labels = [], []
    with torch.inference_mode():
        for example in calibration:
            scores.extend(model(example["batch"]).tolist())
            labels.extend(example["labels"].tolist())
    calibrator = LogisticRegression(random_state=seed, solver="liblinear").fit(
        np.array(scores).reshape(-1, 1), labels
    )
    probabilities = calibrator.predict_proba(np.array(scores).reshape(-1, 1))[:, 1]
    metadata = {
        "config": config,
        "semantic_dimension": semantic_dimension,
        "feature_names": list(PAIR_FEATURES),
        "relations": list(RELATIONS),
        "provenance": provenance(manifests, config, VERSION, FEATURE_VERSION, seed),
        "train_queries": [
            {
                "repo": row["repo"],
                "commit": row["commit"],
                "seed": row["seed"],
                "revision": row["revision"],
            }
            for row in train
        ],
        "selection_queries": [
            {
                "repo": row["repo"],
                "commit": row["commit"],
                "seed": row["seed"],
                "revision": row["revision"],
            }
            for row in selection
        ],
        "calibration_queries": [
            {
                "repo": row["repo"],
                "commit": row["commit"],
                "seed": row["seed"],
                "revision": row["revision"],
            }
            for row in calibration
        ],
    }
    if semantic_dimension:
        from neural_cartographer.features.embeddings import configuration

        metadata["encoder"] = configuration()
    output = ROOT / "artifacts/models/heterogeneous-development"
    output.mkdir(parents=True, exist_ok=True)
    # Publish the online checkpoint last, after its companion artifacts/report.
    # Readers always see a complete file, including during a development rerun.
    temporary_model = output / ("model-" + uuid.uuid4().hex + ".tmp")
    torch.save(
        {"state_dict": model.state_dict(), "metadata": metadata}, temporary_model
    )
    for channel, state in ablation_states.items():
        torch.save(
            {"state_dict": state, "metadata": {**metadata, "channels": [channel]}},
            output / (channel + "-only.pt"),
        )
    baseline.save_model(output / "xgboost.json")
    write(
        output / "calibration.json",
        {
            "coefficient": calibrator.coef_.tolist(),
            "intercept": calibrator.intercept_.tolist(),
            "status": "validation-fit-only; not a held-out calibration estimate",
        },
    )
    write(output / "metadata.json", metadata)
    report = {
        "status": "development; not frozen for final testing",
        "history": history,
        "ablation_history": ablation_history,
        "comparison": comparison,
        "macro_recall_at_5": {
            name: macro(rows, "recall_at_5") for name, rows in comparison.items()
        },
        "calibration_fit": {
            "brier": brier_score_loss(labels, probabilities),
            "average_precision": average_precision_score(labels, probabilities),
            "pairs": len(labels),
        },
        "metadata": metadata,
        "failures": failures,
    }
    report["confidence_intervals"] = {
        name: {
            metric: macro_bootstrap(rows, metric)
            for metric in ("recall_at_5", "ndcg_at_10")
        }
        for name, rows in comparison.items()
    }
    report["per_repository"] = {
        name: {
            repo: {
                metric: sum(row[metric] for row in rows if row["repo"] == repo)
                / sum(row["repo"] == repo for row in rows)
                for metric in (
                    "recall_at_5",
                    "recall_at_10",
                    "precision_at_5",
                    "map_at_10",
                    "ndcg_at_10",
                    "mrr",
                    "candidate_ceiling",
                )
            }
            for repo in sorted({row["repo"] for row in rows})
        }
        for name, rows in comparison.items()
    }
    baselines = [
        name
        for name in comparison
        if name != "heterogeneous" and not name.endswith("-only")
    ]
    report["strongest_baseline"] = max(
        baselines,
        key=lambda name: (
            macro(comparison[name], "recall_at_5"),
            macro(comparison[name], "ndcg_at_10"),
            name,
        ),
    )
    write(ROOT / "artifacts/reports/heterogeneous-development.json", report)
    temporary_model.replace(output / "model.pt")
    print(
        json.dumps(
            {
                "status": report["status"],
                "macro_recall_at_5": report["macro_recall_at_5"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
