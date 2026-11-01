"""Frozen, exploratory SWE-bench file-ranking transfer check (not patch repair).

Exclude all twelve study projects. Predeclare up to five lexicographically first
multi-file Xarray cases. A known changed file is an oracle seed; all other gold
modified Python files are labels, isolated from prediction construction.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.ingest.pipeline import eligible, git, process, write
from neural_cartographer.learning.research import verify_freeze

PROJECT = "pydata/xarray"
MAXIMUM_CASES = 5


def modified_paths(patch):
    paths = []
    for section in re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE):
        match = re.match(r"diff --git a/(.*?) b/(.*?)\n", section)
        if (
            match
            and match[1] == match[2]
            and eligible(match[1])
            and "--- /dev/null" not in section
            and "+++ /dev/null" not in section
        ):
            paths.append(match[1])
    return sorted(set(paths))


def prepare():
    verify_freeze()
    from huggingface_hub import hf_hub_download
    import pyarrow.parquet as parquet

    pin = json.loads((ROOT / "artifacts/reports/external-dataset-pin.json").read_text())
    files, rows = [], []
    for filename in pin["files"]:
        path = Path(
            hf_hub_download(
                pin["dataset"],
                filename,
                repo_type="dataset",
                revision=pin["revision"],
                token=False,
                cache_dir=str(ROOT / "data/external/hf-cache"),
            )
        )
        files.append(
            {"name": filename, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        rows.extend(
            parquet.read_table(
                path, columns=["repo", "instance_id", "base_commit", "patch"]
            ).to_pylist()
        )
    split = json.loads((ROOT / "configs/repositories.json").read_text())
    excluded = {repo.casefold() for repos in split.values() for repo in repos}
    selected = []
    for row in sorted(rows, key=lambda value: value["instance_id"]):
        paths = modified_paths(row["patch"])
        if (
            row["repo"] == PROJECT
            and row["repo"].casefold() not in excluded
            and len(paths) >= 2
        ):
            selected.append(
                {key: row[key] for key in ("repo", "instance_id", "base_commit")}
                | {"modified_paths": paths}
            )
        if len(selected) == MAXIMUM_CASES:
            break
    audit = {
        "dataset": pin,
        "files": files,
        "instances": len(rows),
        "repository_counts": dict(Counter(row["repo"] for row in rows)),
        "excluded_projects": sorted(excluded),
        "excluded_instances": sum(row["repo"].casefold() in excluded for row in rows),
        "selection_policy": "first five instance IDs in pydata/xarray with at least two modified Python paths; no study-project overlap",
        "selected": selected,
        "limitations": [
            "One external project and a bounded sample",
            "Oracle changed-file seed; not issue localization or patch generation",
            "Gold source-file patches are a different label source from commit co-change",
            "No benchmark repository code or tests are executed",
        ],
    }
    if not selected:
        raise ValueError(
            "No non-overlapping cases satisfy the predeclared external policy"
        )
    write(ROOT / "artifacts/reports/external-overlap-audit.json", audit)
    print(
        json.dumps(
            {
                key: value
                for key, value in audit.items()
                if key not in ("repository_counts", "excluded_projects")
            },
            indent=2,
        ),
        flush=True,
    )
    return audit


def evaluate():
    record = verify_freeze()
    destination = ROOT / "artifacts/reports/external-swebench.json"
    if destination.exists():
        raise ValueError("External result already exists; refusing to overwrite it")
    audit = prepare()
    from neural_cartographer.candidates.ranking import rank, finalize
    from neural_cartographer.graph.snapshots import build_snapshot
    from neural_cartographer.features.embeddings import build
    from neural_cartographer.features.history import rerank
    from neural_cartographer.evaluation.metrics import metrics, macro_bootstrap

    print("Restoring external project history:", PROJECT, flush=True)
    process(PROJECT, "submitted", clone=True, reuse=True)
    key = PROJECT.replace("/", "__")
    clone = ROOT / "data/raw" / key
    manifest = json.loads((ROOT / "data/manifests" / (key + ".json")).read_text())
    rows, failures = [], []
    for case in audit["selected"]:
        started = time.monotonic()
        revision = case["base_commit"]
        print("External case", case["instance_id"], revision, flush=True)
        try:
            ancestry = subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone),
                    "merge-base",
                    "--is-ancestor",
                    revision,
                    manifest["revision"],
                ],
                capture_output=True,
                check=False,
            )
            if ancestry.returncode:
                raise ValueError(
                    "External base is not covered by the pinned ancestor-history extraction"
                )
            graph = build_snapshot(clone, revision)
            paths = [node["path"] for node in graph["nodes"] if node["kind"] == "file"]
            existing = sorted(set(paths) & set(case["modified_paths"]))
            if len(existing) < 2:
                raise ValueError(
                    "Fewer than two gold paths are available in the eligible base snapshot"
                )
            seed = existing[0]
            positives = sorted(set(case["modified_paths"]) - {seed})
            build(PROJECT, revision)
            result = finalize(
                {
                    "repo": PROJECT,
                    "seed": seed,
                    "graph_revision": revision,
                    "graph": graph,
                    "candidates": rank(paths, seed),
                    "parse_failures": graph["parse_failures"],
                },
                clone,
                manifest,
                True,
                "heterogeneous-v1",
                len(paths),
            )
            learned = [row["path"] for row in result["candidates"]]
            name = record["strongest_baseline"]
            if name == "semantic-v1":
                baseline = [
                    row["path"]
                    for row in sorted(
                        result["candidates"],
                        key=lambda row: (
                            -row["features"]["semantic_cosine"],
                            row["path"],
                        ),
                    )
                ]
            elif name == "xgboost":
                from xgboost import XGBClassifier
                from neural_cartographer.learning.heterogeneous import tensorize

                model = XGBClassifier()
                model.load_model(
                    ROOT / "artifacts/models/heterogeneous-development/xgboost.json"
                )
                scores = model.predict_proba(tensorize(result)["pairs"].numpy())[:, 1]
                baseline = [
                    result["candidates"][i]["path"]
                    for i in sorted(
                        range(len(scores)),
                        key=lambda i: (
                            -float(scores[i]),
                            result["candidates"][i]["path"],
                        ),
                    )
                ]
            else:
                baseline = [
                    row["path"] for row in rerank(result["candidates"], name, seed)
                ]
            rows.append(
                {
                    "repo": PROJECT,
                    "commit": revision,
                    "instance_id": case["instance_id"],
                    "seed": seed,
                    "positives": positives,
                    "seconds": time.monotonic() - started,
                    "parse_failures": len(graph["parse_failures"]),
                    "heterogeneous": metrics(learned, positives),
                    name: metrics(baseline, positives),
                }
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append({"instance_id": case["instance_id"], "error": str(error)})
        write(
            ROOT / "artifacts/reports/external-swebench-progress.json",
            {"cases": rows, "failures": failures},
        )
    if failures or not rows:
        raise ValueError(
            "External cases were incomplete; inspect the saved failure report"
        )
    report = {
        "status": "exploratory frozen seeded-file ranking; not SWE-bench issue-resolution accuracy",
        "overlap_audit": audit,
        "cases": rows,
        "failures": failures,
        "model_sha256": record["hashes"][
            "artifacts/models/heterogeneous-development/model.pt"
        ],
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "metrics": {},
        "confidence_intervals": {},
    }
    for name in ("heterogeneous", record["strongest_baseline"]):
        values = [
            {"repo": row["repo"], "commit": row["commit"], **row[name]} for row in rows
        ]
        report["metrics"][name] = {
            metric: sum(row[metric] for row in values) / len(values)
            for metric in values[0]
            if metric not in ("repo", "commit")
        }
        report["confidence_intervals"][name] = {
            metric: macro_bootstrap(values, metric)
            for metric in ("recall_at_5", "ndcg_at_10")
        }
    verify_freeze()
    write(destination, report)
    print(json.dumps(report["metrics"], indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "evaluate"])
    arguments = parser.parse_args()
    prepare() if arguments.action == "prepare" else evaluate()
