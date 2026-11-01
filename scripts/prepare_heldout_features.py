"""Prepare frozen test examples for completed repositories; compute no metrics."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT, write
from neural_cartographer.learning.research import verify_freeze
from neural_cartographer.learning.train import examples


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", required=True)
    args = parser.parse_args()
    freeze = verify_freeze()
    split = json.loads((ROOT / "configs/repositories.json").read_text())
    checkpoint = json.loads(
        (ROOT / "artifacts/models/heterogeneous-development/metadata.json").read_text()
    )
    results = []
    for repo in args.repo:
        if repo not in split["test"]:
            raise ValueError("Only predeclared held-out repositories are accepted")
        manifest = json.loads(
            (ROOT / "data/manifests" / (repo.replace("/", "__") + ".json")).read_text()
        )
        count = 0
        for example in examples(
            manifest,
            freeze["test_commits_per_repo"],
            checkpoint["config"]["use_semantics"],
        ):
            count += 1
            del example
        results.append({"repo": repo, "examples": count, "metrics_computed": False})
        write(ROOT / "artifacts/reports/heldout-preparation.json", results)
    verify_freeze()
    print(
        "Frozen held-out features prepared; no metrics computed:", results, flush=True
    )


if __name__ == "__main__":
    main()
