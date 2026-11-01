"""Verify and publish completed study provenance, model card and UI summaries."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.ingest.pipeline import VERSION, write
from neural_cartographer.features.history import FEATURE_VERSION
from neural_cartographer.learning.research import verify_freeze


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import torch

    freeze = verify_freeze()
    path = ROOT / "artifacts/reports/final-heldout.json"
    report = json.loads(path.read_text())
    if report["status"] != "frozen held-out evaluation":
        raise ValueError("Final held-out result is not recorded")
    if report.get("freeze") != freeze:
        raise ValueError("Held-out result belongs to a different frozen experiment")
    metadata = json.loads(
        (ROOT / "artifacts/models/heterogeneous-development/metadata.json").read_text()
    )
    source_digest = hashlib.sha256()
    for source in sorted((ROOT / "backend/src/neural_cartographer").rglob("*.py")):
        source_digest.update(source.read_bytes())
    split = json.loads((ROOT / "configs/repositories.json").read_text())
    datasets, queries = [], []
    measured = {
        (row["repo"], row["commit"]) for row in report["comparison"]["heterogeneous"]
    }
    for repo in split["test"]:
        key = repo.replace("/", "__")
        manifest_path = ROOT / "data/manifests" / (key + ".json")
        manifest = json.loads(manifest_path.read_text())
        directory = ROOT / "data/processed" / key / manifest["revision"]
        summary = json.loads((directory / "summary.json").read_text())
        for filename, expected in summary["checksums"].items():
            if checksum(directory / filename) != expected:
                raise ValueError("Held-out dataset checksum mismatch")
        datasets.append(
            {
                "repo": repo,
                "revision": manifest["revision"],
                "manifest_sha256": checksum(manifest_path),
                "summary_sha256": checksum(directory / "summary.json"),
                "checksums": summary["checksums"],
                "current_snapshot_parse_failures": summary["parse_failures"],
            }
        )
        by_commit = {}
        for line in (directory / "queries.jsonl").open():
            query = json.loads(line)
            by_commit.setdefault(query["commit"], query)
        for query in list(by_commit.values())[-freeze["test_commits_per_repo"] :]:
            cache_key = hashlib.sha256(
                json.dumps(
                    {
                        "query": query,
                        "semantic": metadata["config"]["use_semantics"],
                        "encoder": metadata["encoder"],
                        "python": list(sys.version_info[:2]),
                        "pipeline": VERSION,
                        "features": FEATURE_VERSION,
                        "source": source_digest.hexdigest(),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()
            cache = ROOT / "data/interim/learning-examples" / key / (cache_key + ".pt")
            example = torch.load(cache, map_location="cpu", weights_only=True)
            if example["cache_key"] != cache_key or example["seed"] != query["seed"]:
                raise ValueError("Held-out example identity mismatch")
            paths = example["batch"]["paths"]
            expected = torch.tensor([float(p in query["positives"]) for p in paths])
            if not torch.equal(expected, example["labels"]):
                raise ValueError(
                    "Held-out labels differ from the recorded source query"
                )
            queries.append(
                {
                    "repo": repo,
                    "commit": query["commit"],
                    "revision": query["graph_revision"],
                    "seed": query["seed"],
                    "positive_paths": query["positives"],
                    "candidate_files": len(paths),
                    "candidate_paths_sha256": hashlib.sha256(
                        json.dumps(paths).encode()
                    ).hexdigest(),
                    "example_sha256": checksum(cache),
                    "example_cache_key": cache_key,
                    "unresolved_imports": example["batch"]["unresolved_imports"],
                }
            )
    if {(row["repo"], row["commit"]) for row in queries} != measured:
        raise ValueError("Published query policy differs from the final measured pool")
    audit = {
        "status": "verified against frozen source and completed held-out result",
        "final_report_sha256": checksum(path),
        "model_sha256": freeze["hashes"][
            "artifacts/models/heterogeneous-development/model.pt"
        ],
        "datasets": datasets,
        "queries": queries,
        "frozen_artifacts": len(freeze["hashes"]),
    }
    write(ROOT / "artifacts/reports/final-study-audit.json", audit)
    baseline = freeze["strongest_baseline"]
    limits = [
        "60 bounded held-out commit queries across three projects",
        "Modified-file co-change is a proxy for impact",
        "File-level predictions; shared file vectors for symbols",
        "No runtime test-coverage proof",
        "CodeBERT pretraining overlap is unaudited",
    ]
    public = {
        "status": report["status"],
        "success_gate_met": report["success_gate_met"],
        "strongest_baseline": baseline,
        "query_count": len(queries),
        "macro": report["macro"],
        "per_repository": report["per_repository"],
        "confidence_intervals": report["confidence_intervals"],
        "calibration": report["calibration"],
        "model_sha256": audit["model_sha256"],
        "report_sha256": audit["final_report_sha256"],
        "limitations": limits,
    }
    comparator_path=ROOT/"artifacts/reports/frozen-comparators-heldout.json"
    if comparator_path.is_file():
        comparators=json.loads(comparator_path.read_text())
        if comparators["primary_model_sha256"]!=audit["model_sha256"]:raise ValueError("Supplemental comparator model mismatch")
        public["supplemental_comparators"]={key:comparators[key] for key in ("status","macro","confidence_intervals","query_count")}
    extra_path = ROOT / "artifacts/reports/leave-one-out-heldout.json"
    extra = json.loads(extra_path.read_text()) if extra_path.is_file() else None
    if extra:
        public["leave_one_out"] = extra["macro"]
        public["channel_removal_gate_met"] = all(
            report["macro"]["heterogeneous"][metric] > values[metric]
            for values in extra["macro"].values()
            for metric in ("recall_at_5", "ndcg_at_10")
        )
    for name, filename in [
        ("swebench", "external-swebench.json"),
        ("bugsinpy", "external-bugsinpy.json"),
    ]:
        external = ROOT / "artifacts/reports" / filename
        if external.is_file():
            values = json.loads(external.read_text())
            public[name] = {
                "status": values["status"],
                "cases": len(values["cases"]),
                "metrics": values["metrics"],
            }
    write(ROOT / "frontend/public/assets/study-results.json", public)
    lines = [
        "# Neural Cartographer model card",
        "",
        "This checkpoint ranks related Python files for developer inspection. It does not prove causal impact or runtime test coverage.",
        "",
        "## Data and protocol",
        "",
        "The user-approved split is 7 training / 2 validation / 3 test projects. Training used 140 commit queries, 20 separate validation-selection queries and 20 calibration queries. The final study used 20 queries per held-out project (60 total), selected by the frozen policy.",
        "",
        "Graphs and history use the target commit's parent; labels enter only the loss/evaluation. CodeBERT is pinned and uses the first 256 tokens per file. Two relation-aware GraphSAGE layers operate on file/class/function/test nodes; predictions and proxy labels remain file-level.",
        "",
        "## Frozen held-out result",
        "",
        f"Strongest validation-selected baseline: `{baseline}`. Ranking gate met: **{report['success_gate_met']}**. Model choices were not changed against test results.",
        "",
        "| System | Macro Recall@5 | Macro NDCG@10 |",
        "|---|---:|---:|",
    ]
    for name, values in report["macro"].items():
        lines.append(
            f"| {name} | {values['recall_at_5']:.4f} | {values['ndcg_at_10']:.4f} |"
        )
    if extra:
        for name, values in extra["macro"].items():
            lines.append(
                f"| {name} | {values['recall_at_5']:.4f} | {values['ndcg_at_10']:.4f} |"
            )
    lines += [
        "",
        "Confidence intervals and per-project results are in `artifacts/reports/final-heldout.json`. Exact query/candidate/example and dataset checksums are in `final-study-audit.json`.",
        "",
        "## Scores and limitations",
        "",
        "Online sigmoid scores remain uncalibrated ranking values. A validation-fitted calibrator is evaluated separately on held-out data; it is not used to label online scores as reliable probabilities.",
        "",
    ]
    lines += ["- " + limit for limit in limits]
    lines += [
        "- Static call/inheritance resolution is conservative and same-file lexical; dynamic dependencies remain unresolved.",
        "- Static source relationships and co-change explanations are retrieved evidence, not a causal explanation of neural weights.",
        "- The study does not establish global chronological separation across different repositories.",
        "",
        "## Provenance",
        "",
        f"Model SHA256: `{audit['model_sha256']}`",
        "",
        f"Final report SHA256: `{audit['final_report_sha256']}`",
        "",
        f"The primary freeze binds {len(freeze['hashes'])} source/configuration/model/data artifacts. Additional channel-removal models have a separate pre-test freeze; they never change the primary model or baseline. Reproduction commands and local resource limits are documented in `README.md` and `docs/operations.md`.",
        "",
    ]
    if "supplemental_comparators" in public:
        lines += ["", "## Supplemental frozen comparator evaluation", "", public["supplemental_comparators"]["status"]+". Primary baseline and success gate remain unchanged.", "", "| Comparator | Macro Recall@5 | Macro NDCG@10 |", "|---|---:|---:|"]
        lines += [f"| {name} | {values['recall_at_5']:.4f} | {values['ndcg_at_10']:.4f} |" for name,values in public["supplemental_comparators"]["macro"].items()]
    (ROOT / "docs/model-card.md").write_text("\n".join(lines), encoding="utf-8")
    verify_freeze()
    print(
        "Published verified query audit, model card, and UI study summary", flush=True
    )


if __name__ == "__main__":
    main()
