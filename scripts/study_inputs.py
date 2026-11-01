"""Recover and verify the exact prepared development tensors used by the study."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))


def load():
    import torch
    from neural_cartographer.learning.research import verify_freeze
    from neural_cartographer.learning.train import fit_fingerprint

    verify_freeze()
    directory = ROOT / "artifacts/models/heterogeneous-development"
    metadata = json.loads((directory / "metadata.json").read_text())
    names = ("train_queries", "selection_queries", "calibration_queries")
    requested = {
        (q["repo"], q["commit"], q["seed"]) for name in names for q in metadata[name]
    }
    lookup = {}
    for repo in sorted({q[0] for q in requested}):
        for path in (
            ROOT / "data/interim/learning-examples" / repo.replace("/", "__")
        ).glob("*.pt"):
            if len(path.stem) != 64:
                continue
            value = torch.load(path, map_location="cpu", weights_only=True)
            key = (value["repo"], value["commit"], value["seed"])
            if key not in requested:
                continue
            if key in lookup:
                raise ValueError("Ambiguous prepared input")
            lookup[key] = value
    pools = {
        name: [lookup[(q["repo"], q["commit"], q["seed"])] for q in metadata[name]]
        for name in names
    }
    fingerprint = fit_fingerprint(
        pools["train_queries"],
        pools["selection_queries"],
        metadata["config"],
        metadata["semantic_dimension"],
        "full",
    )
    if not (directory / "progress" / ("full-" + fingerprint + ".pt")).is_file():
        raise ValueError(
            "Development input fingerprint differs from the primary checkpoint"
        )
    return metadata, pools, fingerprint
