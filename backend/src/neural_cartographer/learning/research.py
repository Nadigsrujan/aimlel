"""Freeze development choices before allowing the held-out evaluation."""

import argparse
import hashlib
import json

from neural_cartographer.ingest.pipeline import ROOT, VERSION, write


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze(root=ROOT):
    output = root / "artifacts/models/heterogeneous-development"
    report = json.loads(
        (root / "artifacts/reports/heterogeneous-development.json").read_text()
    )
    config = json.loads((root / "configs/experiments/heterogeneous.json").read_text())
    split = json.loads((root / "configs/repositories.json").read_text())
    if [len(split[k]) for k in ("train", "validation", "test")] != [7, 2, 3]:
        raise ValueError("The approved split is 7 / 2 / 3")
    projects = [repo for repos in split.values() for repo in repos]
    if len(projects) != len(set(projects)):
        raise ValueError("Repository partitions overlap")
    metadata = report["metadata"]
    if not config.get("use_semantics") or not metadata.get("semantic_dimension"):
        raise ValueError("The full-fusion freeze requires semantic model inputs")
    if report.get("failures") or metadata["config"] != config:
        raise ValueError(
            "Training report is incomplete or uses a different configuration"
        )
    if metadata["provenance"]["parser_version"] != VERSION:
        raise ValueError("Training report uses an obsolete extraction protocol")
    for key, partition in [
        ("train_queries", "train"),
        ("selection_queries", "validation"),
        ("calibration_queries", "validation"),
    ]:
        if not metadata[key] or any(
            row["repo"] not in split[partition] for row in metadata[key]
        ):
            raise ValueError(
                "Training or model selection used an invalid repository partition"
            )
    selection = {(q["repo"], q["commit"]) for q in metadata["selection_queries"]}
    calibration = {(q["repo"], q["commit"]) for q in metadata["calibration_queries"]}
    if selection & calibration:
        raise ValueError("Selection and calibration queries overlap")
    files = [
        "configs/repositories.json",
        "configs/encoder.json",
        "configs/experiments/heterogeneous.json",
        "configs/experiments/protocol.json",
        "artifacts/reports/heterogeneous-development.json",
    ]
    files += [
        "artifacts/models/heterogeneous-development/" + name
        for name in [
            "model.pt",
            "xgboost.json",
            "calibration.json",
            "metadata.json",
            "static-only.pt",
            "history-only.pt",
            "semantic-only.pt",
        ]
    ]
    files += [
        str(path.relative_to(root)).replace("\\", "/")
        for path in sorted((root / "backend/src").rglob("*.py"))
    ]
    files += [
        "data/manifests/" + repo.replace("/", "__") + ".json" for repo in projects
    ]
    encoder_key = hashlib.sha256(
        json.dumps(metadata["encoder"], sort_keys=True).encode()
    ).hexdigest()[:16]
    queries = (
        metadata["train_queries"]
        + metadata["selection_queries"]
        + metadata["calibration_queries"]
    )
    for repo, revision in sorted({(q["repo"], q["revision"]) for q in queries}):
        directory = (
            "data/processed/"
            + repo.replace("/", "__")
            + "/"
            + revision
            + "/embeddings-"
            + encoder_key
            + "/"
        )
        index = json.loads((root / (directory + "manifest.json")).read_text())
        if index["history_cutoff"] != revision:
            raise ValueError("Semantic cutoff mismatch")
        for filename, key in [
            ("vectors.npy", "vectors_sha256"),
            ("vectors.index", "index_sha256"),
        ]:
            if digest(root / (directory + filename)) != index[key]:
                raise ValueError("Semantic feature checksum mismatch")
        files += [
            directory + name
            for name in ("manifest.json", "vectors.npy", "vectors.index")
        ]
    for repo in split["train"] + split["validation"]:
        manifest = json.loads(
            (root / "data/manifests" / (repo.replace("/", "__") + ".json")).read_text()
        )
        directory = (
            "data/processed/"
            + repo.replace("/", "__")
            + "/"
            + manifest["revision"]
            + "/"
        )
        summary = json.loads((root / (directory + "summary.json")).read_text())
        if summary["pipeline_version"] != VERSION:
            raise ValueError("Dataset version is obsolete: " + repo)
        for name, checksum in summary["checksums"].items():
            if digest(root / (directory + name)) != checksum:
                raise ValueError("Dataset checksum mismatch: " + repo + "/" + name)
        files += [directory + "summary.json"] + [
            directory + name for name in summary["checksums"]
        ]
    record = {
        "version": 1,
        "strongest_baseline": report["strongest_baseline"],
        "query_policy": "last eligible commits in pinned topological order; one seed per commit",
        "test_commits_per_repo": 20,
        "classification_threshold": 0.5,
        "hashes": {name: digest(root / name) for name in files},
    }
    destination = output / "freeze.json"
    if destination.exists():
        if json.loads(destination.read_text()) != record:
            raise ValueError("A different model/protocol is already frozen")
        return record
    write(destination, record)
    return record


def verify_freeze(root=ROOT):
    record = json.loads(
        (root / "artifacts/models/heterogeneous-development/freeze.json").read_text()
    )
    for name, checksum in record["hashes"].items():
        if digest(root / name) != checksum:
            raise ValueError("Frozen artifact changed: " + name)
    return record


def evaluate(root=ROOT):
    record = verify_freeze(root)
    destination = root / "artifacts/reports/final-heldout.json"
    if destination.exists():
        raise ValueError(
            "Held-out results already exist; do not repeat model selection against them"
        )
    import torch
    from xgboost import XGBClassifier

    from neural_cartographer.evaluation.metrics import macro_bootstrap, metrics
    from neural_cartographer.features.history import rerank
    from neural_cartographer.learning.heterogeneous import HeterogeneousImpactModel
    from neural_cartographer.learning.train import (
        channel_examples,
        examples,
        macro,
        measure,
    )

    torch.set_num_threads(2)
    output = root / "artifacts/models/heterogeneous-development"
    checkpoint = torch.load(output / "model.pt", map_location="cpu", weights_only=True)
    metadata = checkpoint["metadata"]
    model = HeterogeneousImpactModel(
        semantic_dimension=metadata.get("semantic_dimension", 0)
    )
    model.load_state_dict(checkpoint["state_dict"])
    test = []
    split = json.loads((root / "configs/repositories.json").read_text())
    for repo in split["test"]:
        manifest = json.loads(
            (root / "data/manifests" / (repo.replace("/", "__") + ".json")).read_text()
        )
        if manifest["split"] != "test":
            raise ValueError("Held-out manifest partition mismatch")
        print("Preparing frozen held-out query pool:", repo, flush=True)
        test.extend(
            examples(
                manifest,
                record["test_commits_per_repo"],
                metadata["config"].get("use_semantics", False),
            )
        )
    # Index construction uses more threads and retains an encoder. Release it
    # before timing rankers and use the declared inference thread count.
    from neural_cartographer.features.embeddings import encoder
    import gc

    encoder.cache_clear()
    gc.collect()
    torch.set_num_threads(metadata["config"].get("training_threads", 2))
    torch.use_deterministic_algorithms(True)
    comparison = {"heterogeneous": measure(model, test)}
    name = record["strongest_baseline"]
    if name == "xgboost":
        baseline = XGBClassifier()
        baseline.load_model(output / "xgboost.json")
        comparison[name] = measure(model, test, baseline)
    else:

        def paths(example):
            rows = example["rows"]
            if name == "semantic-v1":
                rows = sorted(
                    rows,
                    key=lambda row: (-row["features"]["semantic_cosine"], row["path"]),
                )
            else:
                rows = rerank(rows, name, example["seed"])
            return [row["path"] for row in rows]

        comparison[name] = [
            {
                "repo": e["repo"],
                "commit": e["commit"],
                **metrics(paths(e), e["positives"]),
            }
            for e in test
        ]
    for channel in ("static", "history", "semantic"):
        state = torch.load(
            output / (channel + "-only.pt"), map_location="cpu", weights_only=True
        )
        ablated = HeterogeneousImpactModel(
            semantic_dimension=metadata.get("semantic_dimension", 0)
        )
        ablated.load_state_dict(state["state_dict"])
        masked = channel_examples(test, {channel})
        comparison[channel + "-only"] = measure(ablated, masked)
        del masked, ablated
    keys = (
        "recall_at_5",
        "recall_at_10",
        "precision_at_5",
        "map_at_10",
        "ndcg_at_10",
        "mrr",
        "candidate_ceiling",
    )
    report = {
        "status": "frozen held-out evaluation",
        "freeze": record,
        "comparison": comparison,
        "macro": {
            name: {metric: macro(rows, metric) for metric in keys}
            for name, rows in comparison.items()
        },
        "confidence_intervals": {
            name: {
                metric: macro_bootstrap(rows, metric)
                for metric in ("recall_at_5", "ndcg_at_10")
            }
            for name, rows in comparison.items()
        },
    }
    report["per_repository"] = {
        name: {
            repo: {
                metric: sum(row[metric] for row in rows if row["repo"] == repo)
                / sum(row["repo"] == repo for row in rows)
                for metric in keys
            }
            for repo in sorted({row["repo"] for row in rows})
        }
        for name, rows in comparison.items()
    }
    import numpy as np
    from sklearn.metrics import average_precision_score, brier_score_loss, f1_score

    calibration = json.loads((output / "calibration.json").read_text())
    probabilities, labels = [], []
    model.eval()
    with torch.inference_mode():
        for example in test:
            logits = model(example["batch"]).numpy()
            scaled = (
                logits * calibration["coefficient"][0][0] + calibration["intercept"][0]
            )
            probabilities.extend((1 / (1 + np.exp(-np.clip(scaled, -60, 60)))).tolist())
            labels.extend(example["labels"].tolist())
    probabilities = np.asarray(probabilities)
    labels = np.asarray(labels)
    bins = []
    for index in range(10):
        selected = (probabilities >= index / 10) & (
            probabilities < (index + 1) / 10 if index < 9 else probabilities <= 1
        )
        bins.append(
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "pairs": int(selected.sum()),
                "mean_probability": float(probabilities[selected].mean())
                if selected.any()
                else None,
                "observed_frequency": float(labels[selected].mean())
                if selected.any()
                else None,
            }
        )
    report["calibration"] = {
        "brier": float(brier_score_loss(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "f1": float(
            f1_score(
                labels,
                probabilities >= record["classification_threshold"],
                zero_division=0,
            )
        ),
        "threshold": record["classification_threshold"],
        "reliability_bins": bins,
    }
    report["success_gate_met"] = all(
        report["macro"]["heterogeneous"][metric]
        > report["macro"][record["strongest_baseline"]][metric]
        for metric in ("recall_at_5", "ndcg_at_10")
    )
    verify_freeze(root)
    write(destination, report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "evaluate"])
    args = parser.parse_args()
    result = freeze() if args.action == "freeze" else evaluate()
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "comparison"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
