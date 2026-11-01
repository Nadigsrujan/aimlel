"""Reproduce saved weights, training history and validation rankings by resume."""

import json
from study_inputs import ROOT, load


def main():
    import torch
    from neural_cartographer.learning.train import fit_model, measure
    from neural_cartographer.ingest.pipeline import write

    metadata, pools, fingerprint = load()
    config = metadata["config"]
    torch.set_num_threads(config["training_threads"])
    torch.use_deterministic_algorithms(True)
    directory = ROOT / "artifacts/models/heterogeneous-development"
    model, history = fit_model(
        pools["train_queries"],
        pools["selection_queries"],
        config,
        metadata["semantic_dimension"],
        directory / "progress",
    )
    installed = torch.load(
        directory / "model.pt", map_location="cpu", weights_only=True
    )
    for name, tensor in model.state_dict().items():
        torch.testing.assert_close(
            tensor, installed["state_dict"][name], rtol=0, atol=0
        )
    report = json.loads(
        (ROOT / "artifacts/reports/heterogeneous-development.json").read_text()
    )
    if history != report["history"]:
        raise ValueError("Resumed loss/selection history differs")
    measured = measure(model, pools["selection_queries"])
    for actual, expected in zip(
        measured, report["comparison"]["heterogeneous"], strict=True
    ):
        if {k: v for k, v in actual.items() if k != "inference_seconds"} != {
            k: v for k, v in expected.items() if k != "inference_seconds"
        }:
            raise ValueError("Validation rankings differ from the saved report")
    result = {
        "status": "exact checkpoint, history and validation metric reproduction passed",
        "input_fingerprint": fingerprint,
        "training_queries": len(pools["train_queries"]),
        "validation_selection_queries": len(measured),
        "epochs": len(history),
        "comparison_excludes": "wall-clock latency, which is measured afresh",
    }
    write(ROOT / "artifacts/reports/checkpoint-reproduction.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
