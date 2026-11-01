"""Publish bounded parent-side symbol mapping and evidence coverage audits."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT, VERSION, write
from neural_cartographer.labels.diffs import map_changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commits-per-repository", type=int, default=1)
    args = parser.parse_args()
    if not 1 <= args.commits_per_repository <= 20:
        parser.error("Use one to twenty commits per development repository")
    reports = []
    for path in sorted((ROOT / "data/manifests").glob("*.json")):
        manifest = json.loads(path.read_text())
        if manifest["split"] not in ("train", "validation"):
            continue
        key = manifest["repo"].replace("/", "__")
        directory = ROOT / "data/processed" / key / manifest["revision"]
        summary = json.loads((directory / "summary.json").read_text())
        if summary["pipeline_version"] != VERSION:
            raise ValueError("Obsolete extraction: " + key)
        queries = {}
        for line in (directory / "queries.jsonl").open():
            query = json.loads(line)
            queries.setdefault(query["commit"], query)
        for query in list(queries.values())[-args.commits_per_repository :]:
            print("Auditing", manifest["repo"], query["commit"], flush=True)
            result = map_changes(ROOT / "data/raw" / key, query["commit"])
            reports.append({"repo": manifest["repo"], **result})
            write(
                ROOT / "artifacts/reports/development-mapping-audit.json",
                {
                    "parser_version": VERSION,
                    "sampling": "last eligible development commits; bounded audit",
                    "commits_per_repository": args.commits_per_repository,
                    "cases": reports,
                    "coverage": {
                        name: sum(row["coverage"][name] for row in reports)
                        for name in ("changed_files", "symbol_mapped", "fallback_files")
                    },
                    "limitations": [
                        "A span overlap is a mapping aid, not a function-level impact label",
                        "Added and ambiguous spans retain file fallback",
                        "Bounded sample does not establish corpus-wide mapping accuracy",
                    ],
                },
            )


if __name__ == "__main__":
    main()
