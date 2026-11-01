"""Materialize revision-exact semantic indexes without reading held-out labels."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT, write
from neural_cartographer.features.embeddings import build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/experiments/heterogeneous.json").read_text())
    results = []
    for path in sorted((ROOT / "data/manifests").glob("*.json")):
        manifest = json.loads(path.read_text())
        if manifest["split"] not in ("train", "validation"):
            continue
        directory = (
            ROOT
            / "data/processed"
            / manifest["repo"].replace("/", "__")
            / manifest["revision"]
        )
        if not (directory / "summary.json").is_file():
            print("Data not ready:", manifest["repo"], flush=True)
            continue
        limit = (
            config["commits_per_training_repo"]
            if manifest["split"] == "train"
            else config["commits_per_validation_repo"]
        )
        queries = {}
        for line in (directory / "queries.jsonl").open():
            query = json.loads(line)
            queries.setdefault(query["commit"], query)
        revisions = {manifest["revision"]} | {
            q["graph_revision"] for q in list(queries.values())[-limit:]
        }
        for revision in sorted(revisions):
            print("Embedding", manifest["repo"], revision, flush=True)
            index = build(manifest["repo"], revision, args.download)
            results.append(
                {
                    "repo": manifest["repo"],
                    "revision": revision,
                    "files": len(index["paths"]),
                    "vectors_sha256": index["vectors_sha256"],
                }
            )
            write(ROOT / "artifacts/reports/semantic-preparation.json", results)
    print("Prepared", len(results), "revision indexes", flush=True)


if __name__ == "__main__":
    main()
