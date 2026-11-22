"""Paired, repository-aware comparisons of frozen per-query results.

Reads only saved study reports; no model is run and no held-out choice changes.
Each comparison pairs two systems on identical (repository, commit) queries and
reports the repository-macro difference first minus second.
"""

import argparse
import json
import math
import random
from statistics import NormalDist, mean, stdev

from neural_cartographer.ingest.pipeline import ROOT, write
from neural_cartographer.learning.portable_freeze import matches

METRICS = ("recall_at_5", "ndcg_at_10")
PRIMARY = ("heterogeneous", "cochange-v1")


def paired(first, second, metric):
    """Per-query differences grouped by repository; queries must match exactly."""
    left = {(row["repo"], row["commit"]): row[metric] for row in first}
    right = {(row["repo"], row["commit"]): row[metric] for row in second}
    if len(left) != len(first) or len(right) != len(second):
        raise ValueError("Expected one row per repository and commit")
    if left.keys() != right.keys():
        raise ValueError("Systems were evaluated on different queries")
    groups = {}
    for key in sorted(left):
        groups.setdefault(key[0], []).append(left[key] - right[key])
    return groups


def macro(groups):
    return mean(mean(values) for values in groups.values())


def paired_bootstrap(groups, hierarchical, iterations=10000, seed=17):
    """Percentile interval for the macro difference.

    hierarchical=True also resamples repositories, which targets unseen
    projects but is unstable with very few repositories. False keeps the
    observed repositories fixed and resamples queries within each.
    """
    rng = random.Random(seed)
    projects = sorted(groups)
    estimates = []
    for _ in range(iterations):
        chosen = rng.choices(projects, k=len(projects)) if hierarchical else projects
        estimates.append(
            mean(
                mean(rng.choices(groups[project], k=len(groups[project])))
                for project in chosen
            )
        )
    estimates.sort()
    return {
        "lower": estimates[int(0.025 * iterations)],
        "upper": estimates[min(iterations - 1, int(0.975 * iterations))],
        "iterations": iterations,
        "seed": seed,
    }


def sign_flip(groups, iterations=10000, seed=17):
    """Two-sided paired randomization test of the macro difference."""
    rng = random.Random(seed)
    observed = abs(macro(groups))
    extreme = 0
    for _ in range(iterations):
        flipped = {
            project: [value if rng.random() < 0.5 else -value for value in values]
            for project, values in groups.items()
        }
        extreme += abs(macro(flipped)) >= observed - 1e-12
    return (extreme + 1) / (iterations + 1)


def wilcoxon(groups):
    """Pooled signed-rank test; a secondary check that ignores repositories."""
    from scipy.stats import wilcoxon as signed_rank

    values = [value for project in sorted(groups) for value in groups[project]]
    nonzero = sum(value != 0 for value in values)
    if not nonzero:
        return {"p_value": 1.0, "nonzero_pairs": 0}
    return {
        "p_value": float(signed_rank(values, zero_method="wilcox").pvalue),
        "nonzero_pairs": nonzero,
    }


def holm(p_values):
    """Holm step-down adjusted p-values for a family of named tests."""
    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted, running = {}, 0.0
    for index, (name, value) in enumerate(ordered):
        running = max(running, min(1.0, (len(ordered) - index) * value))
        adjusted[name] = running
    return adjusted


def required_queries(sd, delta, alpha=0.05, power=0.8):
    """Paired queries needed to detect a mean difference of delta."""
    z = NormalDist().inv_cdf
    return math.ceil(((z(1 - alpha / 2) + z(power)) * sd / delta) ** 2)


def compare(first, second, metric, iterations=10000):
    groups = paired(first, second, metric)
    values = [value for project in sorted(groups) for value in groups[project]]
    return {
        "difference": macro(groups),
        "per_repository": {project: mean(v) for project, v in groups.items()},
        "wins": sum(value > 0 for value in values),
        "ties": sum(value == 0 for value in values),
        "losses": sum(value < 0 for value in values),
        "queries": len(values),
        "paired_sd": stdev(values),
        "ci_fixed_repositories": paired_bootstrap(groups, False, iterations),
        "ci_resampled_repositories": paired_bootstrap(groups, True, iterations),
        "sign_flip_p": sign_flip(groups, iterations),
        "wilcoxon": wilcoxon(groups),
    }


def bucket(value, edges):
    for upper, label in edges:
        if value <= upper:
            return label
    return edges[-1][1]


def slices(first, second, audit, metric):
    """Where the two systems differ, by query difficulty and project."""
    facts = {(q["repo"], q["commit"]): q for q in audit}
    right = {(row["repo"], row["commit"]): row[metric] for row in second}
    dimensions = {
        "changed_files": lambda q: bucket(
            len(q["positive_paths"]), [(1, "1"), (3, "2-3"), (math.inf, "4+")]
        ),
        "candidate_pool": lambda q: bucket(
            q["candidate_files"],
            [(500, "<=500"), (2000, "501-2000"), (math.inf, ">2000")],
        ),
        "repository": lambda q: q["repo"],
    }
    report = {}
    for dimension, label in dimensions.items():
        cells = {}
        for row in first:
            key = (row["repo"], row["commit"])
            cell = cells.setdefault(label(facts[key]), {"first": [], "second": []})
            cell["first"].append(row[metric])
            cell["second"].append(right[key])
        report[dimension] = {
            name: {
                "queries": len(cell["first"]),
                "first_mean": mean(cell["first"]),
                "second_mean": mean(cell["second"]),
                "wins": sum(a > b for a, b in zip(cell["first"], cell["second"])),
                "losses": sum(a < b for a, b in zip(cell["first"], cell["second"])),
            }
            for name, cell in sorted(cells.items())
        }
    return report


def load(root=ROOT):
    """Collect every frozen system's per-query rows on the audited query pool."""
    reports = root / "artifacts/reports"
    audit = json.loads((reports / "final-study-audit.json").read_text())
    primary_bytes = (reports / "final-heldout.json").read_bytes()
    if matches(primary_bytes, audit["final_report_sha256"], "final.json") == "changed":
        raise ValueError("final-heldout.json does not match the audited report")
    systems = dict(json.loads(primary_bytes)["comparison"])
    for name in ("leave-one-out-heldout.json", "frozen-comparators-heldout.json"):
        for system, rows in json.loads((reports / name).read_text())[
            "comparison"
        ].items():
            systems.setdefault(system, rows)
    return systems, audit["queries"]


def analyze(root=ROOT, iterations=10000, delta=0.05):
    systems, audit = load(root)
    first = systems[PRIMARY[0]]
    report = {
        "status": "post-hoc paired analysis of frozen v1 results; no model choice changed",
        "pre_registered_comparison": "heterogeneous vs cochange-v1",
        "difference_convention": "first minus second; positive favours first",
        "systems": sorted(systems),
        "comparisons": {},
        "slices": {},
        "sample_size": {},
    }
    for metric in METRICS:
        results = {}
        for other in sorted(systems):
            if other != PRIMARY[0]:
                results[other] = compare(first, systems[other], metric, iterations)
        # History-only was the strongest model on validation; test it directly.
        results["history-only vs cochange-v1"] = compare(
            systems["history-only"], systems["cochange-v1"], metric, iterations
        )
        adjusted = holm({name: row["sign_flip_p"] for name, row in results.items()})
        for name, row in results.items():
            row["holm_p"] = adjusted[name]
        report["comparisons"][metric] = results
        report["slices"][metric] = slices(
            first, systems[PRIMARY[1]], audit, metric
        )
        sd = results[PRIMARY[1]]["paired_sd"]
        total = required_queries(sd, delta)
        repositories = len(results[PRIMARY[1]]["per_repository"])
        report["sample_size"][metric] = {
            "observed_paired_sd": sd,
            "detectable_difference": delta,
            "alpha": 0.05,
            "power": 0.8,
            "total_paired_queries": total,
            "assumption": "independent queries, equal queries per repository",
            "per_repository_if_5_projects": math.ceil(total / 5),
            "v1_queries": results[PRIMARY[1]]["queries"],
            "v1_repositories": repositories,
        }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=10000)
    parser.add_argument("--delta", type=float, default=0.05)
    args = parser.parse_args()
    report = analyze(iterations=args.iterations, delta=args.delta)
    write(ROOT / "artifacts/reports/v1-paired-analysis.json", report)
    for metric, results in report["comparisons"].items():
        print(metric)
        for name, row in results.items():
            ci = row["ci_fixed_repositories"]
            print(
                f"  {name:28s} diff {row['difference']:+.4f} "
                f"[{ci['lower']:+.4f}, {ci['upper']:+.4f}] "
                f"p={row['sign_flip_p']:.4f} holm={row['holm_p']:.4f} "
                f"W/T/L {row['wins']}/{row['ties']}/{row['losses']}"
            )
    for metric, size in report["sample_size"].items():
        print(metric, "queries needed:", size["total_paired_queries"])


if __name__ == "__main__":
    main()
