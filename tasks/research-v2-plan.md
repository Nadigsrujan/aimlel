# Research v2: from a finished demo to a publishable study

Written 2026-11-21. This plan turns the completed v1 study into a paper-grade empirical study. It lists only the work being implemented: the decisions behind it and the checklist.

## Honest starting point

- **v1 is complete and negative.** On 60 held-out commits (SymPy, scikit-learn, Django), the GraphSAGE fusion model scored 0.397 macro Recall@5, against 0.458 for the co-change baseline. Validation pointed the same way: history-only 0.302, co-change 0.280, fusion 0.285.
- **v1 is too small to support any claim.** It used 140 training queries out of about 89,000 extracted, and 20 test queries per project, all taken from each project's *latest* commits. The macro confidence intervals overlap almost entirely (0.18–0.62 against 0.30–0.61).
- **The held-out projects are spent.** Their results are known, so any new model judged on them is tuned against the test set, however unintentionally.
- **Reproducibility is weaker than the docs say.** On a fresh Windows checkout, `verify_freeze()` fails. Eleven source files differ only in line endings (CRLF from `core.autocrlf`). A further 536 frozen data files exist only on the author's machine.
- **The strongest asset is the protocol,** not the model: parent-snapshot features, ancestor-only history, project-disjoint splits, and a freeze before testing. That protocol is what a paper can stand on.

## Target

**An empirical study in the style of an MSR or EMSE paper,** asking: *"Under leakage-controlled, project-disjoint evaluation, does graph learning beat co-change history for file-level change impact?"* A negative or null answer is publishable if the study is large enough, has fair baselines and is reproducible. We aim for that rather than a new-method paper, because nothing in the evidence so far suggests the method wins.

## Decision log

| # | Decision | Chosen | Why |
|---|---|---|---|
| D1 | What happens to v1 | Kept frozen and byte-identical; reported as the pilot study | Editing it after the results are known would be p-hacking. Every v1-frozen file is untouchable. |
| D2 | Where v2 tests | **5 fresh projects, never ingested:** `aio-libs/aiohttp`, `Textualize/rich`, `pypa/pip`, `celery/celery`, `marshmallow-code/marshmallow` | v1's test projects are spent (D1). Five projects instead of three makes the macro average less fragile. None of them is in SWE-bench Verified, BugsInPy or the current 17 manifests. |
| D3 | Pre-registration | v2 protocol, systems, sample sizes and the primary metric are frozen **before** any fresh project is cloned | This is what makes a negative or positive result believable. |
| D4 | Query sampling | Seeded uniform sample across each project's eligible history (existing bulk-commit rules apply) | v1 used only the latest 20 commits, which is a recency-biased slice. |
| D5 | Sample size | Set by the Phase 1 power analysis, then capped by the measured cost from the Phase 2 pilot | Guessing "1,000 queries" either wastes days of compute or leaves the study underpowered again. |
| D6 | v2 systems | Co-change (baseline), **ROSE-style association rules** (literature baseline), XGBoost, history-only GNN, full fusion GNN, and **a stacked hybrid** that feeds the co-change score into the model | The baseline won, so reviewers will ask whether it's a strawman. ROSE (Zimmermann et al., 2004) is the standard published co-change miner, and the hybrid is the one model change with a real chance of helping. |
| D7 | Primary system | Picked from D6 on **validation only**, by macro Recall@5 | This is the same rule as v1, and it keeps the test set out of model choice. |
| D8 | Statistics | Paired difference with a hierarchical (project → commit) bootstrap CI, a paired sign-flip randomization test, Holm correction across comparisons, and pooled Wilcoxon as a secondary check | Unpaired CIs on each system, which is all v1 reported, can't answer "is A better than B". |
| D9 | CodeBERT channel | Kept **only if** the Phase 2 pilot shows semantic indexing costs ≤ 40% of the per-query time | Validation semantic-only was 0.068, close to random. It's the most expensive channel and has earned no default place. |
| D10 | Code location | v2 code lives in **new modules**. No v1-frozen file is ever edited. | Editing a frozen file breaks `verify_freeze()` and every script that calls it. |
| D11 | Line-ending failure | Add a portable verifier that reports exact, line-ending-only, missing or changed status per file. The freeze record and v1 code stay untouched. | The mismatch isn't a code change. Hiding it would be dishonest, and "fixing" it by rewriting the freeze would be worse. |

## Phases and checklist

Sizes: S = 1–3 files, M = 4–6 files.

### Phase 0: Reproducibility

- [x] **0.1 Diagnose the freeze failure (S).** Found: 59 exact matches, 11 line-ending-only differences, 0 real changes, 536 missing local data files.
- [x] **0.2 Portable freeze verifier (S).** Classifies every frozen file and exits non-zero only on a real content change.
  - Verification: `python scripts/verify_freeze_portable.py` and `test_significance.py`
  - Result: primary freeze has 59 exact, 11 line-ending-only, 536 missing and 0 changed; the leave-one-out freeze has 4 exact.
- [x] **0.3 Check that a rebuild is byte-identical (S).** Flask, re-ingested on this machine, should match the frozen dataset checksums.
  - Result: all four Flask dataset files (`events.jsonl`, `graph.json`, `queries.jsonl`, `summary.json`) match exactly, so ingestion is deterministic across machines.

### Phase 1: Paired statistics on frozen v1 (no new data)

- [x] **1.1 Significance module (M).** Paired per-query join, hierarchical paired bootstrap, sign-flip test, Holm correction, Wilcoxon, power and sample-size calculation, error slices.
  - Files: `backend/src/neural_cartographer/evaluation/significance.py`, `backend/tests/unit/test_significance.py`
- [x] **1.2 Run it on v1 (S).** Covers the main model against every frozen comparator, the ablations, per-project results, and slices by number of changed files and candidate-pool size.
  - Output: `artifacts/reports/v1-paired-analysis.json`
  - Verification: `python scripts/paired_analysis.py`
- [x] **1.3 Fix the v2 sample size (S).** Recorded under *v1 paired findings* below.

#### v1 paired findings (post-hoc; frozen results, nothing retuned)

| Comparison (model minus other) | Recall@5 difference | 95% CI, projects fixed | Sign-flip p | Holm p | Win / tie / loss |
|---|---:|---|---:|---:|---|
| vs co-change (pre-registered) | −0.061 | −0.138 to +0.008 | 0.126 | 0.755 | 7 / 44 / 9 |
| vs history-only GNN | −0.031 | −0.096 to +0.032 | 0.400 | 1.000 | 6 / 45 / 9 |
| vs XGBoost | +0.048 | −0.054 to +0.153 | 0.391 | 1.000 | 11 / 40 / 9 |
| vs without-semantic | −0.009 | −0.088 to +0.066 | 0.832 | 1.000 | 7 / 46 / 7 |
| vs every system lacking history | +0.30 to +0.40 | all exclude 0 | 0.0001 | 0.0015 | — |

What this means:

1. **v1 is inconclusive, not a loss.** The model is not significantly worse than co-change: the interval crosses zero, and 44 of 60 queries tie. "Gate not met" is accurate; "the GNN is worse" is not supported. Even the hierarchical interval (−0.175 to +0.037) crosses zero.
2. **History is the entire signal.** Every system that uses history is statistically indistinguishable from every other. Every system without it is close to random, and removing semantic or static input changes nothing measurable.
3. **The whole gap is Django.** Django scored 0.175 against 0.327 (0 wins, 5 losses), while scikit-learn and SymPy were roughly level. Django is also the only project with more than 2,000 candidate files, so in v1 "large repository" and "Django" can't be told apart. The model also lost all 4 decided single-partner queries (35 queries with one co-changed file).
4. **Secondary check:** on NDCG@10, the history-only GNN is worse than co-change (−0.095, p = 0.007, Holm p = 0.052). This is borderline and exploratory.

#### Decisions taken from these findings

- **D5 resolved:** detecting a 0.05 macro Recall@5 difference (α = 0.05, 80% power, paired SD 0.299) needs about 281 paired queries. v2 uses **100 test queries per fresh project × 5 = 500**, which detects about 0.037 at the same SD and leaves margin if the new projects are noisier. The training target is 100 queries per training project (700), with 50 for selection and 50 for calibration per validation project. The Phase 2 pilot may lower the training target, but never the test target.
- **New, pre-registered secondary analysis:** results by candidate-pool size (≤ 500, 501–2,000, > 2,000 files) and by number of changed files. The fresh test projects include large ones (pip, celery), so the Django effect can be separated from repository size.
- **D9 leans towards dropping CodeBERT** from the primary arm: removing it changed Recall@5 by −0.009, with p = 0.83. The Phase 2 cost pilot makes the final call.

### Phase 2: Restore development data and pilot the cost

- [x] **2.1 Re-ingest the eight remaining development projects (L, compute only).** All nine development datasets were rebuilt, and every one matches the v1 freeze byte-for-byte (91 exact, 0 changed). Five clones needed a retry after a transient DNS error.
- [x] **2.2 Pilot timing (S).** 20 queries per development project, in `artifacts/reports/v2-pilot.json`.
  - **D9 resolved:** CodeBERT took 85–96% of preparation time in every project (17–191 s per example), against the 40% limit, so v2 excludes it.
  - **D5 confirmed:** without CodeBERT, an example takes 2–18 s, so the planned sizes are affordable unchanged.

### Phase 3: Pre-register v2

- [x] **3.1 Protocol file (S).** `configs/experiments/protocol-v2.json` records the repositories (D2), sampling (D4), sizes (D5), systems (D6), primary metric and selection rule (D7), the statistical tests (D8) and the success gate. It's a draft until the pilot fixes `use_semantics`.
- [x] **3.2 v2 freeze code (M).** `learning/research_v2.py` has `pilot`, `develop`, `freeze`, `verify` and `evaluate` stages, run through `scripts/research_v2.py`. The freeze refuses to run if any test project is already cloned or has a manifest. Evaluation refuses to run without a verified freeze or after results exist. Checksums ignore CRLF/LF differences in text files. Tested in `test_research_v2.py`.

### Phase 4: Scaled training and selection

- [x] **4.1 ROSE association-rule baseline (S).** `rose()` ranks by support, which for a single seed file gives the same order as ROSE's confidence. Unit-tested.
- [x] **4.2 Hybrid (S).** Decided as weighted reciprocal-rank fusion of co-change with one GNN. Feeding co-change in as a feature would add nothing, because Jaccard and co-change counts are already pair features of the model. The GNN and weight (0.25–1.0, never 0) are chosen on validation. Unit-tested.
- [x] **4.2b Validation-only model search (M), added 2026-11-22.** v1 trained the GNN once with one hand-picked setup. v2 adds:
  - a pairwise BPR ranking loss beside v1's weighted BCE
  - a LambdaMART learning-to-rank XGBoost (`xgboost-ltr`)
  - a 2 losses × 2 hidden sizes (32, 64) search for each GNN arm, run as 8 parallel processes
  - size-slice error analysis on validation

  Every choice uses validation selection queries only, before the freeze. Recorded in `protocol-v2.json` under `model_search`.
- [x] **4.3 Train all systems at the D5 scale (M, compute).** 700 training, 100 selection and 100 calibration queries; 8 GNN variants trained in parallel. Report: `artifacts/reports/v2-development.json`.
- [x] **4.4 Pick the primary on validation and freeze v2 (S).** Frozen 2026-11-22: 102 artifacts, freeze.json SHA-256 `49b683c3…7328`.
  - **Primary:** `xgboost-ltr` (LambdaMART), validation Recall@5 0.342.
  - **Baseline:** `rose-v1`, 0.269.
  - **GNN variants:** full GNN with BCE at hidden 32 (0.323); history GNN with BPR at hidden 32 (0.313).
  - **Hybrid:** the weight search chose 1.0, which is the pure full GNN, so fusing with co-change didn't help on validation.
  - Unlike v1, every learned system beat every heuristic on validation. These scores are optimistic, because the same queries drove early stopping and selection.

### Phase 5: The single fresh test

- [x] **5.1 Ingest the five fresh projects (compute).** Done after the freeze; the pinned SHAs are in `v2-final.json`.
- [x] **5.2 Evaluate once (S).** 500 queries, in `artifacts/reports/v2-final.json`.
  - **The pre-registered gate is met:** LambdaMART minus ROSE is +0.058 macro Recall@5, with a 95% CI of +0.030 to +0.086 (projects fixed) and +0.022 to +0.097 (projects resampled), p = 0.0001.
  - **Exploratory** (`v2-exploratory.json`): the GNN beats co-change Jaccard (+0.054) but not ROSE (+0.028, p = 0.053), and LambdaMART beats the GNN (+0.030, Holm p = 0.049). The gain is in learning to rank, not in message passing.
  - **The size slice is uninformative:** every test pool had at most 449 files.

### Phase 6: Paper and replication package

- [ ] **6.1 Replication package.** Every stage, the table builder and the exploratory script are reproducible from saved reports. **Remaining:** a GitHub CI run, which needs the branch pushed.
- [ ] **6.2 Paper draft.** `docs/paper/draft.md` has the abstract, methods, v1 pilot, v2 results, threats and replication sections. **Remaining:** related work, which needs real citations taken from the literature surveys in the repository root.

### Housekeeping (any time; never touches frozen files)

- [x] `docs/run-and-verify.md` is rewritten for Windows and the venv, with the v1 checks and v2 stages. `PENDING_WORK.md` now points here and marks its checklist as historical.

## Not yet specified

- Phase 2: whether the 2.2 timings force the training target below 700 queries. The test target of 500 is fixed.
- Phase 4: the hybrid's exact form (feature versus score fusion). It's decided at 4.2 pickup, on validation only.
- Phase 6: venue and format. Still undecided; it depends on 5.2.

## Always and never

- **Always:** select on validation only, pair comparisons per query, report every pre-registered system, keep failures visible, and keep v1 numbers as published.
- **Never:** edit a v1-frozen file, open fresh test projects before the v2 freeze, re-run a final evaluation to get a better number, or execute target-repository code.

## Progress

| Phase | Status |
|---|---|
| 0 Reproducibility | done; the remaining 536 local files are rebuilt in 2.1 |
| 1 Paired v1 statistics | done; 88 backend and 2 frontend tests pass, frozen content unchanged |
| 2 Data restore and pilot | done; CodeBERT excluded by the cost rule |
| 3 Pre-registration | done; protocol final, freeze code tested |
| 4 Scaled training | done; LambdaMART selected as primary, ROSE as baseline |
| 5 Fresh test | done; gate met, +0.058 Recall@5 over ROSE |
| 6 Paper | draft written; related work and a CI run remain |
