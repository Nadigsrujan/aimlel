"""Frozen static file-ranking check on three pinned BugsInPy Black fixes.

This reads source/patch metadata only. Benchmark setup scripts and tests are
never executed; results are not claims of reproduced BugsInPy failures/repairs.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.ingest.pipeline import process, write
from neural_cartographer.learning.research import verify_freeze
from neural_cartographer.candidates.ranking import rank, finalize
from neural_cartographer.graph.snapshots import build_snapshot
from neural_cartographer.features.embeddings import build
from neural_cartographer.features.history import rerank, RANKERS
from neural_cartographer.evaluation.metrics import metrics, macro_bootstrap


def main():
    frozen = verify_freeze()
    destination = ROOT / "artifacts/reports/external-bugsinpy.json"
    if destination.exists():
        raise ValueError("BugsInPy result already exists; refusing to overwrite")
    audit = json.loads(
        (ROOT / "artifacts/reports/external-bugsinpy-audit.json").read_text()
    )
    split = json.loads((ROOT / "configs/repositories.json").read_text())
    if "psf/black" in {repo for repos in split.values() for repo in repos}:
        raise ValueError("External benchmark overlaps a study project")
    baseline = frozen["strongest_baseline"]
    if baseline not in RANKERS:
        raise ValueError(
            "This pinned BugsInPy runner requires a frozen heuristic baseline"
        )
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    process("psf/black", "submitted", clone=True, reuse=True)
    clone = ROOT / "data/raw/psf__black"
    manifest = json.loads((ROOT / "data/manifests/psf__black.json").read_text())
    cases, failures = [], []
    for case in audit["selected"]:
        started = time.monotonic()
        revision = case["base_commit"]
        print("BugsInPy", case["instance_id"], revision, flush=True)
        try:
            for commit in (revision, case["fixed_commit"]):
                check = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(clone),
                        "merge-base",
                        "--is-ancestor",
                        commit,
                        manifest["revision"],
                    ],
                    capture_output=True,
                    check=False,
                )
                if check.returncode:
                    raise ValueError(
                        "Benchmark commit is outside pinned extracted history"
                    )
            graph = build_snapshot(clone, revision)
            paths = [node["path"] for node in graph["nodes"] if node["kind"] == "file"]
            existing = sorted(set(paths) & set(case["modified_paths"]))
            if len(existing) < 2:
                raise ValueError(
                    "No independent changed-file label remains in the buggy snapshot"
                )
            seed = existing[0]
            positives = sorted(set(case["modified_paths"]) - {seed})
            build("psf/black", revision)
            result = finalize(
                {
                    "repo": "psf/black",
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
            prediction = [row["path"] for row in result["candidates"]]
            comparison = [
                row["path"] for row in rerank(result["candidates"], baseline, seed)
            ]
            cases.append(
                {
                    "repo": "psf/black",
                    "commit": revision,
                    "fixed_commit": case["fixed_commit"],
                    "instance_id": case["instance_id"],
                    "seed": seed,
                    "positives": positives,
                    "candidate_files": len(paths) - 1,
                    "parse_failures": len(graph["parse_failures"]),
                    "seconds": time.monotonic() - started,
                    "heterogeneous": metrics(prediction, positives),
                    baseline: metrics(comparison, positives),
                }
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append({"instance_id": case["instance_id"], "error": str(error)})
        write(
            ROOT / "artifacts/reports/external-bugsinpy-progress.json",
            {"cases": cases, "failures": failures},
        )
    if failures or len(cases) != len(audit["selected"]):
        raise ValueError("Incomplete BugsInPy sample; inspect the saved case report")
    report = {
        "status": "exploratory frozen BugsInPy file ranking; no benchmark test reproduction",
        "overlap_audit": audit,
        "cases": cases,
        "failures": failures,
        "metrics": {},
        "confidence_intervals": {},
        "model_sha256": frozen["hashes"][
            "artifacts/models/heterogeneous-development/model.pt"
        ],
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    for name in ("heterogeneous", baseline):
        values = [
            {"repo": row["repo"], "commit": row["commit"], **row[name]} for row in cases
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
    main()
