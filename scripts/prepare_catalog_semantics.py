"""Prepare current pinned catalog indexes without reading query labels."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT
from neural_cartographer.features.embeddings import build
from neural_cartographer.learning.research import verify_freeze


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split",
        action="append",
        choices=["train", "validation", "test", "submitted"],
        required=True,
    )
    args = parser.parse_args()
    if "test" in args.split:
        verify_freeze()
    for path in sorted((ROOT / "data/manifests").glob("*.json")):
        manifest = json.loads(path.read_text())
        if manifest["split"] in args.split:
            print("Preparing catalog semantics:", manifest["repo"], flush=True)
            result = build(manifest["repo"], manifest["revision"])
            print("Ready:", manifest["repo"], len(result["paths"]), "files", flush=True)


if __name__ == "__main__":
    main()
