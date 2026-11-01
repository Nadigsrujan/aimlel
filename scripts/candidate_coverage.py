"""Audit candidate-channel recall on the unchanged development query pool."""

from collections import defaultdict
import json
from study_inputs import ROOT, load


def main():
    from neural_cartographer.ingest.pipeline import write

    metadata, pools, fingerprint = load()
    rows = []
    for partition, values in pools.items():
        for example in values:
            candidates = example["rows"]
            positives = set(example["positives"])
            channels = {
                "structural_within_three_hops": {
                    row["path"] for row in candidates if "structural" in row["channels"]
                },
                "past_cochange": {
                    row["path"] for row in candidates if "history" in row["channels"]
                },
                "semantic_top_50": {
                    row["path"]
                    for row in sorted(
                        candidates,
                        key=lambda row: (
                            -row["features"]["semantic_cosine"],
                            row["path"],
                        ),
                    )[:50]
                },
                "actual_full_file_pool": set(example["batch"]["paths"]),
            }
            channels["diagnostic_three_channel_union"] = set().union(
                *(
                    channels[name]
                    for name in (
                        "structural_within_three_hops",
                        "past_cochange",
                        "semantic_top_50",
                    )
                )
            )
            rows.append(
                {
                    "repo": example["repo"],
                    "commit": example["commit"],
                    "seed": example["seed"],
                    "partition": partition,
                    "recall": {
                        name: len(paths & positives) / len(positives)
                        for name, paths in channels.items()
                    },
                    "candidate_sizes": {
                        name: len(paths) for name, paths in channels.items()
                    },
                }
            )
    per_repo = defaultdict(list)
    for row in rows:
        per_repo[row["repo"]].append(row)
    macro = {
        name: sum(
            sum(row["recall"][name] for row in values) / len(values)
            for values in per_repo.values()
        )
        / len(per_repo)
        for name in rows[0]["recall"]
    }
    report = {
        "status": "development candidate coverage audit",
        "input_fingerprint": fingerprint,
        "queries": len(rows),
        "repository_macro_recall": macro,
        "cases": rows,
        "policy": "Every learned/baseline system scores the actual full eligible-file pool. The top-50 union is a diagnostic alternative, never substituted into evaluation.",
        "limitations": [
            "Development sample only; no held-out model selection",
            "Channel coverage is not ranking precision or evidence causality",
        ],
    }
    write(ROOT / "artifacts/reports/candidate-coverage.json", report)
    print(json.dumps(macro, indent=2))


if __name__ == "__main__":
    main()
