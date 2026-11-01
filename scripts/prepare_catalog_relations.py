"""Warm resolved static-relation caches for first-visit catalog analysis."""

import json
from pathlib import Path
import sys

sys.setrecursionlimit(10000)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT, write
from neural_cartographer.graph.relations import enrich_relations
from neural_cartographer.learning.research import verify_freeze


def main():
    verify_freeze()
    rows = []
    for path in sorted((ROOT / "data/manifests").glob("*.json")):
        manifest = json.loads(path.read_text())
        source = (
            ROOT
            / "data/processed"
            / manifest["repo"].replace("/", "__")
            / manifest["revision"]
            / "graph.json"
        )
        print("Warming catalog relations:", manifest["repo"], flush=True)
        graph, audit = enrich_relations(
            manifest["repo"], manifest["revision"], json.loads(source.read_text())
        )
        rows.append(
            {
                "repo": manifest["repo"],
                "revision": manifest["revision"],
                "nodes": len(graph["nodes"]),
                "edges": len(graph["edges"]),
                "resolution": audit,
            }
        )
        write(ROOT / "artifacts/reports/catalog-readiness.json", rows)
    verify_freeze()
    print("Catalog relation caches ready:", len(rows), flush=True)


if __name__ == "__main__":
    main()
