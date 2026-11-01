"""Online scoring from a locally trained, schema-compatible checkpoint."""

from neural_cartographer.ingest.pipeline import ROOT
from neural_cartographer.features.history import FEATURE_VERSION


def checkpoint_path():
    return ROOT / "artifacts/models/heterogeneous-development/model.pt"


def score(result):
    import torch
    from neural_cartographer.learning.heterogeneous import (
        HeterogeneousImpactModel,
        PAIR_FEATURES,
        RELATIONS,
        tensorize,
    )

    if not checkpoint_path().is_file():
        raise ValueError(
            "No learned checkpoint installed. Run the training pipeline first."
        )
    checkpoint = torch.load(checkpoint_path(), map_location="cpu", weights_only=True)
    metadata = checkpoint["metadata"]
    torch.set_num_threads(metadata.get("config", {}).get("training_threads", 2))
    if (
        metadata["feature_names"] != list(PAIR_FEATURES)
        or metadata["relations"] != list(RELATIONS)
        or metadata["provenance"]["feature_version"] != FEATURE_VERSION
    ):
        raise ValueError(
            "Checkpoint feature schema is incompatible with this application"
        )
    semantic_dimension = metadata.get("semantic_dimension", 0)
    if semantic_dimension:
        from neural_cartographer.features.embeddings import (
            attach_vectors,
            configuration,
        )

        if metadata.get("encoder") != configuration():
            raise ValueError("Checkpoint encoder configuration is incompatible")
        attach_vectors(result)
    model = HeterogeneousImpactModel(semantic_dimension=semantic_dimension)
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    batch = tensorize(result)
    with torch.inference_mode():
        scores = dict(zip(batch["paths"], torch.sigmoid(model(batch)).tolist()))
    for row in result["candidates"]:
        row["score"] = scores[row["path"]]
    result["candidates"].sort(key=lambda row: (-row["score"], row["path"]))
    result["model_provenance"] = metadata["provenance"]
    import hashlib
    import json

    freeze_path = checkpoint_path().with_name("freeze.json")
    frozen = False
    if freeze_path.is_file():
        record = json.loads(freeze_path.read_text())
        expected = record.get("hashes", {}).get(
            "artifacts/models/heterogeneous-development/model.pt"
        )
        frozen = expected == hashlib.sha256(checkpoint_path().read_bytes()).hexdigest()
    result["model_status"] = (
        "frozen checkpoint"
        if frozen
        else "development; not frozen for held-out evaluation"
    )
    result["score_kind"] = "uncalibrated_sigmoid"
    result.pop("node_embeddings", None)
    return result
