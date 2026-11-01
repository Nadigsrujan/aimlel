"""Complete leave-one-channel-out checks without changing the primary freeze.

Additional models use the original training tensors, validation-selection pool
and hyperparameters. Their hashes are fixed before held-out metric access.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.ingest.pipeline import write
from neural_cartographer.learning.research import verify_freeze

OUTPUT = ROOT / "artifacts/models/leave-one-out"
CHANNELS = {
    "without-static": ["history", "semantic"],
    "without-history": ["static", "semantic"],
    "without-semantic": ["static", "history"],
}


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train():
    import torch
    from neural_cartographer.learning.train import (
        fit_fingerprint,
        fit_model,
        channel_examples,
        measure,
        macro,
    )

    verify_freeze()
    destination = OUTPUT / "freeze.json"
    if destination.is_file():
        raise ValueError("Additional ablations are already frozen")
    if (ROOT / "artifacts/reports/final-heldout.json").exists():
        raise ValueError(
            "Additional ablation training must precede primary held-out results"
        )
    metadata = json.loads(
        (ROOT / "artifacts/models/heterogeneous-development/metadata.json").read_text()
    )
    protocol = {
        "declared_at_unix": time.time(),
        "channels": CHANNELS,
        "selection": "original validation-selection commits only",
        "configuration": metadata["config"],
        "primary_freeze_sha256": checksum(
            ROOT / "artifacts/models/heterogeneous-development/freeze.json"
        ),
        "rule": "Do not change the primary checkpoint, baseline, hyperparameters or query pools; retain all results",
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write(OUTPUT / "protocol.json", protocol)
    lookup = {}
    requested = metadata["train_queries"] + metadata["selection_queries"]
    for repo in sorted({row["repo"] for row in requested}):
        for path in (
            ROOT / "data/interim/learning-examples" / repo.replace("/", "__")
        ).glob("*.pt"):
            if len(path.stem) != 64:
                continue
            value = torch.load(path, map_location="cpu", weights_only=True)
            key = (value["repo"], value["commit"], value["seed"])
            if key in lookup:
                raise ValueError(
                    "Ambiguous prepared example; refusing to choose a dataset silently"
                )
            lookup[key] = value

    def pool(name):
        return [
            lookup[(row["repo"], row["commit"], row["seed"])] for row in metadata[name]
        ]

    training, selection = pool("train_queries"), pool("selection_queries")
    config, dimension = metadata["config"], metadata["semantic_dimension"]
    fingerprint = fit_fingerprint(training, selection, config, dimension, "full")
    if not (
        ROOT
        / "artifacts/models/heterogeneous-development/progress"
        / ("full-" + fingerprint + ".pt")
    ).is_file():
        raise ValueError(
            "Prepared tensors do not reproduce the primary training-input fingerprint"
        )
    torch.set_num_threads(config.get("training_threads", 2))
    torch.use_deterministic_algorithms(True)
    traces, comparisons, hashes = {}, {}, {}
    for name, channels in CHANNELS.items():
        print("Training predeclared additional ablation", name, flush=True)
        train_masked, selection_masked = (
            channel_examples(training, set(channels)),
            channel_examples(selection, set(channels)),
        )
        model, history = fit_model(
            train_masked, selection_masked, config, dimension, OUTPUT / "progress", name
        )
        comparisons[name] = measure(model, selection_masked)
        traces[name] = history
        temporary = OUTPUT / (name + ".tmp")
        torch.save(
            {
                "state_dict": model.state_dict(),
                "metadata": metadata,
                "channels": channels,
            },
            temporary,
        )
        path = OUTPUT / (name + ".pt")
        temporary.replace(path)
        hashes[path.name] = checksum(path)
        del model, train_masked, selection_masked
    hashes["protocol.json"] = checksum(OUTPUT / "protocol.json")
    write(
        OUTPUT / "freeze.json",
        {
            "hashes": hashes,
            "primary_input_fingerprint": fingerprint,
            "frozen_at_unix": time.time(),
            "primary_freeze_sha256": protocol["primary_freeze_sha256"],
        },
    )
    write(
        ROOT / "artifacts/reports/leave-one-out-validation.json",
        {
            "protocol": protocol,
            "history": traces,
            "comparison": comparisons,
            "macro_recall_at_5": {
                name: macro(rows, "recall_at_5") for name, rows in comparisons.items()
            },
        },
    )
    verify_freeze()
    print("Additional ablations frozen before primary held-out results", flush=True)


def evaluate():
    import torch
    from neural_cartographer.learning.heterogeneous import HeterogeneousImpactModel
    from neural_cartographer.learning.train import measure, channel_examples, macro
    from neural_cartographer.evaluation.metrics import macro_bootstrap

    verify_freeze()
    destination = ROOT / "artifacts/reports/leave-one-out-heldout.json"
    if destination.exists():
        raise ValueError("Additional held-out ablation results already exist")
    frozen = json.loads((OUTPUT / "freeze.json").read_text())
    for filename, expected in frozen["hashes"].items():
        if checksum(OUTPUT / filename) != expected:
            raise ValueError("Additional frozen ablation artifact changed")
    if (
        checksum(ROOT / "artifacts/models/heterogeneous-development/freeze.json")
        != frozen["primary_freeze_sha256"]
    ):
        raise ValueError("Primary freeze changed")
    audit = json.loads((ROOT / "artifacts/reports/final-study-audit.json").read_text())
    test = []
    for query in audit["queries"]:
        path = (
            ROOT
            / "data/interim/learning-examples"
            / query["repo"].replace("/", "__")
            / (query["example_cache_key"] + ".pt")
        )
        if checksum(path) != query["example_sha256"]:
            raise ValueError("Held-out input differs from primary evaluation")
        test.append(torch.load(path, map_location="cpu", weights_only=True))
    torch.set_num_threads(2)
    comparison = {}
    for name in CHANNELS:
        checkpoint = torch.load(
            OUTPUT / (name + ".pt"), map_location="cpu", weights_only=True
        )
        model = HeterogeneousImpactModel(
            semantic_dimension=checkpoint["metadata"]["semantic_dimension"]
        )
        model.load_state_dict(checkpoint["state_dict"])
        masked = channel_examples(test, set(checkpoint["channels"]))
        comparison[name] = measure(model, masked)
        del model, masked
    report = {
        "status": "predeclared additional leave-one-out models, frozen before primary held-out scores",
        "freeze": frozen,
        "comparison": comparison,
        "macro": {
            name: {
                metric: macro(rows, metric)
                for metric in ("recall_at_5", "ndcg_at_10", "candidate_ceiling")
            }
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
    verify_freeze()
    write(destination, report)
    print(json.dumps(report["macro"], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["train", "evaluate"])
    args = parser.parse_args()
    train() if args.action == "train" else evaluate()
