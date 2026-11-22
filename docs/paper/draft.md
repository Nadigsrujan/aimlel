# Does graph learning beat co-change history for change-impact prediction? A leakage-controlled, project-disjoint study

*Working draft. All numbers come from saved reports: `docs/paper/tables.md` (rebuilt by `scripts/build_tables.py`) and `artifacts/reports/v2-exploratory.json` (from `scripts/v2_exploratory.py`). Related work is still pending.*

## Abstract

Change-impact recommenders are often evaluated with leaks: features from the post-change repository, history from after the query, or test projects that informed design. We ask whether learned rankers, and graph neural networks in particular, beat co-change history for file-level change impact when these leaks are closed. Each query's code graph is rebuilt from the target commit's parent, history is limited to that parent's ancestors, and splits are project-disjoint. All model and protocol choices were frozen by checksum before five fresh test projects were cloned.

A small pilot (60 test queries) was inconclusive. In the pre-registered main study (700 training queries, 500 test queries across aiohttp, Rich, pip, Celery and marshmallow), the validation-selected LambdaMART ranker beat the strongest baseline, ROSE-style association rules, by **+0.058 macro Recall@5**. The 95% interval was +0.030 to +0.086 with projects fixed and +0.022 to +0.097 with projects resampled (sign-flip p = 0.0001). It also beat co-change Jaccard by +0.084.

Exploratory comparisons locate the gain in learning to rank over history and structure features, not in graph message passing:
- the GNN beat co-change Jaccard (+0.054) but not ROSE (+0.028, p = 0.053)
- the GNN was itself beaten by LambdaMART (+0.030, Holm p = 0.049)
- the benefit is largest for single-partner changes and vanishes for commits that change four or more files

## 1. Introduction

When a developer changes a file, which other files will probably need to change too? Recommending them is the file-level change-impact problem. The two families of approach are history mining (files that changed together before) and learned models over code structure and content. Graph neural networks over code graphs are now a common proposal. Their evaluations rarely control three leaks:

1. features computed from a repository state that includes the very change being predicted
2. history that includes commits after the query
3. test projects that informed model design

This paper asks a narrow question under strict controls: **does a relation-aware GraphSAGE model beat co-change history at ranking the other files modified in the same commit?**

Contributions:

1. A leakage-controlled protocol. Each query's graph is rebuilt from the target commit's parent, history is restricted to that parent's Git ancestors, and splits are project-disjoint. Every model and protocol choice is frozen by checksum before test data is opened.
2. A pre-registered evaluation on five fresh projects, with paired, repository-aware statistics and a power analysis that sets the sample size.
3. A pilot study (v1), reported in full, including its null result and the analysis that shaped v2.
4. A replication package that rebuilds every table from saved per-query results.

## 2. Task and labels

A query is a non-merge commit with at least two modified Python files and at most 50 changed files. One modified file is the seed; the other modified files are the positives. Every other eligible file in the parent snapshot is a candidate, so there is no candidate pruning and the candidate ceiling is 1.0. Systems rank all candidates.

Co-change in one commit is a proxy for impact, not proof of it. Section 8 discusses this.

## 3. Data and protocol

**Projects.** Development uses seven training projects (Flask, Requests, pytest, Sphinx, Pydantic, HTTPX, Werkzeug) and two validation projects (FastAPI, SQLAlchemy). The v1 pilot tested on SymPy, scikit-learn and Django. Those results are known, so v2 tests on five projects chosen before any of them was cloned: aiohttp, Rich, pip, Celery and marshmallow. None appear in SWE-bench Verified, BugsInPy or the development set.

**Snapshots and history.** For each query, entities (files, classes, functions, tests) and relations (containment, imports, conservative same-file calls and inheritance) are extracted from the parent commit without executing any code. History features use only commits reachable from that parent.

**Sampling.** One seed per commit, chosen by hash. Commits are sampled uniformly across each project's whole history with a seeded generator, in separate streams for training, validation and test. v1 instead used each project's latest 20 commits.

**Sample size.** From the v1 paired standard deviation (0.299), detecting a 0.05 macro Recall@5 difference at α = 0.05 with 80% power needs about 281 paired queries. v2 uses 100 test queries per project, 500 in total, which detects about 0.037. Development uses 100 training queries per training project, plus 50 selection and 50 calibration queries per validation project.

**Freeze.** `scripts/research_v2.py freeze` records checksums of the protocol, all source code, the development data and every model. It refuses to run if any test project has been cloned, and evaluation refuses to run without a verified freeze or after results exist.

## 4. Systems

- **Heuristics:** co-change Jaccard (`cochange-v1`), ROSE-style association rules (Zimmermann et al., 2004; for a single seed file, ordering by confidence equals ordering by support), import distance, directory distance, popularity, a combined heuristic and random.
- **XGBoost** on seven pair features, both as a binary classifier and as a LambdaMART learning-to-rank model (`rank:ndcg`, one group per query).
- **Full GNN:** a two-layer relation-aware GraphSAGE over four node types and eleven relation channels. Type-specific input projections feed the two layers, and a pair scorer combines the seed embedding, the candidate embedding, their product and the pair features.
- **History GNN:** the same architecture with static inputs masked.
- **Hybrid:** weighted reciprocal-rank fusion of co-change with one GNN. The GNN and its weight (0.25, 0.5, 0.75 or 1.0) are chosen on validation.

**Training.** Each query samples its positives, the 64 nearest negatives by directory distance, and 64 random negatives. Gradients are clipped, and early stopping uses validation macro Recall@5 with a patience of 5 epochs. v1 used one configuration with a weighted pointwise BCE loss. v2 searches, for each GNN arm, two losses × two hidden sizes (32, 64). The losses are v1's BCE and a pairwise Bayesian Personalised Ranking loss, −log σ(s⁺ − s⁻), over sampled positive and negative pairs. A ranking loss fits the task, which is ranking, not classification.

**Selection.** Every choice is made on validation selection queries only:
- the GNN variant
- the hybrid's GNN and weight
- the primary learned system and the strongest baseline, by macro Recall@5

The same selection queries also drive early stopping, so validation scores are optimistic; only the fresh test is unbiased.

**CodeBERT.** A pre-registered cost rule kept CodeBERT only if it took at most 40% of preparation time. A pilot on 20 queries per development project measured 85–96% (17–191 s per example), so v2 excludes it. This also follows v1, where removing it made no measurable difference.

## 5. Statistics

Comparisons are paired per query, and the headline figure is the macro difference across repositories. The analysis reports:

- 95% percentile bootstrap intervals, both with projects fixed and with projects resampled
- a two-sided paired sign-flip test (10,000 draws)
- Holm correction across all comparisons with the primary
- a pooled Wilcoxon signed-rank test as a secondary check

**Pre-registered gate:** the primary's macro Recall@5 minus the baseline's is positive, with sign-flip p < 0.05.

## 6. The v1 pilot

v1 trained on 140 queries and tested on 20 per project across SymPy, scikit-learn and Django (Tables 1 and 2).

- **Headline:** the fusion GNN scored 0.061 lower Recall@5 than co-change. The interval was −0.138 to +0.008, p = 0.126, and 44 of 60 queries tied. The pre-registered gate was not met, and the data do not show the GNN to be worse.
- **History carries the signal:** every system with history was statistically indistinguishable from co-change, and every system without it was close to random.
- **The gap came from Django,** the only project with more than 2,000 candidate files, so project and size are confounded in v1.
- **Consequences for v2:** five fresh projects that include large ones, uniform sampling, and the power-based sample size. CodeBERT is kept only if a cost pilot shows it takes at most 40% of preparation time, because removing it changed Recall@5 by −0.009 (p = 0.83).

## 7. Results (v2)

**Validation (Table 3).** Every learned system beat every heuristic on validation selection queries:

| System | Validation Recall@5 |
|---|---:|
| LambdaMART (`xgboost-ltr`), selected as primary | 0.342 |
| Full GNN (BCE, hidden 32) | 0.323 |
| History GNN (BPR, hidden 32) | 0.313 |
| XGBoost classifier | 0.300 |
| ROSE, selected as baseline | 0.269 |
| Co-change Jaccard | 0.252 |

The hybrid's weight search chose weight 1.0, which is the GNN alone. On validation, fusing with co-change did not help, so on test the hybrid is identical to the full GNN. The BPR ranking loss did not beat BCE for the full GNN (0.318 against 0.323), though it was the better choice for the history GNN.

**Fresh test: pre-registered gate (Tables 4 and 5).** The gate was **met**. LambdaMART scored 0.549 macro Recall@5 against ROSE's 0.491:
- the difference was +0.058, with a 95% CI of +0.030 to +0.086 (projects fixed) and +0.022 to +0.097 (projects resampled)
- sign-flip p = 0.0001, Holm p = 0.0011
- win / tie / loss was 90 / 357 / 53

LambdaMART was higher than ROSE on all five projects, but on aiohttp only by 0.007 (0.565 against 0.558). On aiohttp, co-change Jaccard (0.585) beat both.

| System | Test Recall@5 | Test NDCG@10 |
|---|---:|---:|
| LambdaMART | 0.549 | 0.532 |
| XGBoost classifier | 0.534 | 0.520 |
| Full GNN (= hybrid) | 0.520 | 0.521 |
| History GNN | 0.508 | 0.508 |
| ROSE | 0.491 | 0.480 |
| Co-change Jaccard | 0.465 | 0.441 |

**Where the gain comes from (exploratory, `v2-exploratory.json`).**
- **Over co-change Jaccard:** the full GNN gained +0.054 (Holm p = 0.003) and the history GNN +0.043 (Holm p = 0.026).
- **Over ROSE:** neither GNN was significant: +0.028 (p = 0.053) and +0.017 (p = 0.117).
- **XGBoost classifier:** beat ROSE (+0.043, Holm p = 0.023).
- **LambdaMART vs the GNN:** LambdaMART beat it (+0.030, Holm p = 0.049).
- **LambdaMART vs the XGBoost classifier:** no difference (+0.015, p = 0.14).

On these projects, gradient-boosted ranking over seven hand-built features matches or beats relation-aware message passing over the full code graph.

**Slices (Table 6).** The gain is concentrated in small changes:

| Changed files | Queries | LambdaMART | ROSE | Wins / losses |
|---|---:|---:|---:|---|
| 1 | 257 | 0.708 | 0.623 | 30 / 8 |
| 2–3 | 137 | 0.471 | 0.421 | 32 / 17 |
| 4+ | 106 | 0.266 | 0.265 | 28 / 28 |

The pre-registered pool-size slice turned out to be uninformative. All 500 test queries had at most 449 candidate files (median 139), because uniform sampling over each project's whole history mostly selects earlier, smaller snapshots. So v1's Django effect (pools over 2,000 files) is neither confirmed nor refuted.

**Calibration.** The validation-fitted calibrator applied to the full GNN gives a Brier score of 0.016 and an average precision of 0.179 over 78,801 test pairs.

**v1 against v2.** The pilot's negative direction and the main study's positive result differ in four ways at once:
- training size (140 against 700 queries)
- query sampling (latest commits against uniform)
- test projects
- systems (LambdaMART did not exist in v1)

The study cannot attribute the change to any one of them.

## 8. Threats to validity

- **Construct:** commit co-change is a proxy for impact, and tangled commits add noise to the labels.
- **Internal:** static resolution is conservative and same-file only; dynamic dependencies are missed.
- **External:** these are Python libraries hosted on GitHub. Five test projects is still a small number of clusters, so the resampled-project interval is the honest one for generalising to unseen projects.
- **Conclusion:** the study is powered for a 0.05 difference, not for smaller effects. The exploratory GNN comparisons were not pre-registered.
- **Temporal:** projects are disjoint, but the study does not enforce one global time cutoff across projects.
- **Repository size:** the test snapshots are all at most 449 files, so the results say nothing about very large repositories, where v1 saw the GNN lose.
- **Validation reuse:** selection queries drove early stopping, variant choice, hybrid weights and primary choice, so validation scores are optimistic. The fresh test is unaffected.

## 9. Related work

**Pending:** a short review of history mining (ROSE and its successors), learned change-impact and co-change prediction, GNNs over code, and evaluation leakage in software-engineering machine learning. The literature surveys in the repository root are the starting point.

## 10. Replication

Everything is regenerated with these commands, documented in `docs/run-and-verify.md`:

- `scripts/verify_freeze_portable.py` checks the v1 freeze.
- `scripts/paired_analysis.py` writes the v1 paired analysis.
- `scripts/research_v2.py pilot | develop | freeze | evaluate` runs the v2 study.
- `scripts/v2_exploratory.py` writes the exploratory GNN comparisons.
- `scripts/build_tables.py` rebuilds every table.

Ingestion is deterministic. Re-ingesting all nine development projects on a different machine reproduced every frozen v1 dataset file byte-for-byte. The v2 freeze (`artifacts/models/v2/freeze.json`) binds 102 artifacts and records each fresh project's pinned SHA in the final report.
