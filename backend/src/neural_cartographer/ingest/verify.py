"""Audit catalog completeness, artifact integrity and query label invariants."""

import hashlib
import json
import argparse
import subprocess
from pathlib import Path

from neural_cartographer.ingest.pipeline import ROOT, VERSION, git


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", action="append", choices=["train", "validation", "test"]
    )
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/repositories.json").read_text())
    rows = []
    for split, repositories in config.items():
        if args.split and split not in args.split:
            continue
        for repo in repositories:
            key = repo.replace("/", "__")
            try:
                manifest = json.loads(
                    (ROOT / "data/manifests" / (key + ".json")).read_text()
                )
                directory = ROOT / "data/processed" / key / manifest["revision"]
                summary = json.loads((directory / "summary.json").read_text())
                assert summary["pipeline_version"] == VERSION, (
                    "needs corrected processing pass"
                )
                assert manifest["repo"] == repo and manifest["split"] == split
                assert summary["revision"] == manifest["revision"]
                assert (
                    git(
                        ROOT / "data/raw" / key,
                        "rev-parse",
                        manifest["revision"] + "^{commit}",
                    )
                    .decode()
                    .strip()
                    == manifest["revision"]
                )
                assert summary["split"] == split
                for name, digest in summary["checksums"].items():
                    assert (
                        hashlib.sha256((directory / name).read_bytes()).hexdigest()
                        == digest
                    ), name
                events = {}
                with (directory / "events.jsonl").open() as stream:
                    for line in stream:
                        event = json.loads(line)
                        assert event["commit"] != event["parent"]
                        assert event["commit"] not in events
                        events[event["commit"]] = event
                count = 0
                with (directory / "queries.jsonl").open() as stream:
                    for line in stream:
                        query = json.loads(line)
                        event = events[query["commit"]]
                        modified = {
                            item["path"]
                            for item in event["changes"]
                            if item["status"] == "M"
                        }
                        assert query["graph_revision"] == event["parent"]
                        assert query["seed"] in modified
                        assert set(query["positives"]).issubset(modified)
                        assert query["graph_revision"] != query["commit"]
                        assert query["seed"] not in query["positives"]
                        assert query["positives"] and query["split"] == split
                        assert query["features_materialized"] is False
                        count += 1
                assert count == summary["counts"]["queries"]
                rows.append(
                    {
                        "repo": repo,
                        "split": split,
                        "status": "verified",
                        "queries": count,
                        "nodes": summary["nodes"],
                        "parse_failures": len(summary["parse_failures"]),
                        "commits": summary["counts"]["commits"],
                    }
                )
            except (
                OSError,
                ValueError,
                AssertionError,
                KeyError,
                subprocess.SubprocessError,
            ) as exc:
                rows.append({"repo": repo, "status": "incomplete", "error": str(exc)})
    name = (
        "verification-" + "-".join(sorted(args.split)) + ".json"
        if args.split
        else "verification.json"
    )
    report = ROOT / "artifacts/reports" / name
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps(rows, indent=2))
    raise SystemExit(any(row["status"] != "verified" for row in rows))


if __name__ == "__main__":
    main()
