# Does graph learning beat co-change history for change-impact prediction? A leakage-controlled, project-disjoint study

*Working draft. All numbers come from saved reports: `docs/paper/tables.md` (rebuilt by `scripts/build_tables.py`) and `artifacts/reports/v2-exploratory.json` (from `scripts/v2_exploratory.py`). Related work and references are in Section 9.*

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

**History mining.** Using version history to predict co-change goes back to logical coupling [Gall98]. Ying et al. [Ying04] and Zimmermann et al. [Zimm04, Zimm05] mined frequently co-changed files and association rules from history. ROSE, the second of these, put a correct location in its top three suggestions in more than 70% of cases. TARMAQ [Rolf16] generalised rule mining to queries with several seeds and beat ROSE on six systems. Our queries have exactly one seed file, so TARMAQ reduces to ROSE-style rules and we use ROSE as the baseline. Kagdi et al. [Kagd13] showed that adding textual (conceptual) coupling to history improves impact analysis. IMPER [Zhou24] improves TARMAQ by adding twelve kinds of change relationship, including structural dependencies and clones. Both support our design choice to fuse history with structure. Neither tests whether a learned model beats the history baseline on unseen projects with paired statistics.

**Learned co-change and impact prediction.** Several recent systems learn this task:
- CoChangeFinder [Hong24] uses a GNN over function-level co-change to recommend functions a reviewer missed, and reports beating TARMAQ.
- Germanos et al. [Germ24] model co-change as a temporal graph and predict change propagation with a temporal GNN.
- Kumar et al. [Kuma24] predict co-changes never seen in history by link prediction.
- FCP2Vec [Ahme23] learns file embeddings from changelogs.
- Jia et al. [Jia24] are closest to our primary model: a learning-to-rank model over code and history features that ranks co-changed methods at the pull-request level.
- Caprese [Tava26] combines history mining with runtime dependencies for JavaScript. It finds that the two signals are complementary.

Our result agrees with this line of work: a ranker over history and structure features beats rules mined from history alone. What our study adds is the protocol: parent-snapshot graphs, ancestor-only history, project-disjoint splits, a pre-registered gate checked once on frozen models, and confidence intervals over projects.

**Graph learning over code.** We use GraphSAGE-style inductive aggregation [Hami17] with relation-specific weights in the spirit of R-GCN [Schl18]. Allamanis et al. [Alla18] established typed program graphs for learning, and CodeBERT [Feng20] supplies the optional semantic features, which our cost pilot dropped. Repository-level code graphs now also guide LLM software-engineering agents [Ouya25] evaluated on SWE-bench [Jime24]. That work uses the graph as navigation context for issue repair, not as a predictor of co-change.

**Ranking objectives.** The GNN variants are trained with weighted binary cross-entropy or the pairwise BPR loss [Rend09]. The primary system is LambdaMART [Burg10], trained with the XGBoost ranking objective [Chen16].

**Leakage and label noise.** Kapoor and Narayanan [Kapo23] document leakage across hundreds of machine-learning studies. Train/test overlap and use of future information are among the failure modes they list, and our protocol is built to rule both out for software history. Tangled commits [Herz13] make unrelated files look coupled. They are a known source of label noise for every co-change method here, baselines included (Section 8).

### References

- [Ahme23] H. A. Ahmed and J. Lee. FCP2Vec: Deep learning-based approach to software change prediction by learning co-changing patterns from changelogs. *Applied Sciences* 13(11):6453, 2023. doi:10.3390/app13116453
- [Alla18] M. Allamanis, M. Brockschmidt and M. Khademi. Learning to represent programs with graphs. *ICLR*, 2018.
- [Burg10] C. J. C. Burges. From RankNet to LambdaRank to LambdaMART: An overview. Microsoft Research, MSR-TR-2010-82, 2010.
- [Chen16] T. Chen and C. Guestrin. XGBoost: A scalable tree boosting system. *KDD*, 2016. doi:10.1145/2939672.2939785
- [Feng20] Z. Feng et al. CodeBERT: A pre-trained model for programming and natural languages. *Findings of EMNLP*, 2020.
- [Gall98] H. Gall, K. Hajek and M. Jazayeri. Detection of logical coupling based on product release history. *ICSM*, 1998.
- [Germ24] M. Germanos, D. Azar and E. M. Hanna. To change or not to change? Modeling software system interactions using temporal graphs and graph neural networks: A focus on change propagation. *Information and Software Technology* 166:107368, 2024. doi:10.1016/j.infsof.2023.107368
- [Hami17] W. L. Hamilton, R. Ying and J. Leskovec. Inductive representation learning on large graphs. *NeurIPS*, 2017.
- [Herz13] K. Herzig and A. Zeller. The impact of tangled code changes. *MSR*, pp. 121–130, 2013.
- [Hong24] Y. Hong, C. Tantithamthavorn, P. Thongtanunam and A. Aleti. Don't forget to change these functions! Recommending co-changed functions in modern code review. *Information and Software Technology* 176:107547, 2024. doi:10.1016/j.infsof.2024.107547
- [Jia24] Y. Jia, S. Hassan and Y. Zou. Enhancing software maintenance: A learning to rank approach for co-changed method identification. arXiv:2411.19099, 2024.
- [Jime24] C. E. Jimenez et al. SWE-bench: Can language models resolve real-world GitHub issues? *ICLR*, 2024.
- [Kagd13] H. Kagdi, M. Gethers and D. Poshyvanyk. Integrating conceptual and logical couplings for change impact analysis in software. *Empirical Software Engineering* 18(5):933–969, 2013.
- [Kapo23] S. Kapoor and A. Narayanan. Leakage and the reproducibility crisis in machine-learning-based science. *Patterns* 4:100804, 2023. doi:10.1016/j.patter.2023.100804
- [Kuma24] A. Kumar, E. Hrishikesh, Y. Desai and S. Agarwal. Prevalence and prediction of unseen co-changes: A graph-based approach. *IEEE COMPSAC*, pp. 1157–1167, 2024. doi:10.1109/COMPSAC61105.2024.00155
- [Ouya25] S. Ouyang et al. RepoGraph: Enhancing AI software engineering with repository-level code graph. *ICLR*, 2025. arXiv:2410.14684
- [Rend09] S. Rendle, C. Freudenthaler, Z. Gantner and L. Schmidt-Thieme. BPR: Bayesian personalized ranking from implicit feedback. *UAI*, 2009.
- [Rolf16] T. Rolfsnes, S. Di Alesio, R. Behjati, L. Moonen and D. W. Binkley. Generalizing the analysis of evolutionary coupling for software change impact analysis. *SANER*, pp. 201–212, 2016. doi:10.1109/SANER.2016.101
- [Schl18] M. Schlichtkrull, T. N. Kipf, P. Bloem, R. van den Berg, I. Titov and M. Welling. Modeling relational data with graph convolutional networks. *ESWC*, 2018.
- [Tava26] S. Tavakoli and S. Alimadadi. Change impact recommendation for JavaScript: Lessons from history and runtime analysis. arXiv:2606.21187, 2026.
- [Ying04] A. T. T. Ying, G. C. Murphy, R. Ng and M. C. Chu-Carroll. Predicting source code changes by mining change history. *IEEE TSE* 30(9):574–586, 2004. doi:10.1109/TSE.2004.52
- [Zhou24] D. Zhou, J. Zhang, P. Yu and W. Guo. Enhancing change impact prediction by integrating evolutionary coupling with software change relationships. *ESEM*, pp. 49–60, 2024. doi:10.1145/3674805.3686668
- [Zimm04] T. Zimmermann, P. Weißgerber, S. Diehl and A. Zeller. Mining version histories to guide software changes. *ICSE*, pp. 563–572, 2004.
- [Zimm05] T. Zimmermann, P. Weißgerber, S. Diehl and A. Zeller. Mining version histories to guide software changes. *IEEE TSE* 31(6):429–445, 2005. doi:10.1109/TSE.2005.72

*Citation check (2026-11-22): every entry from 2004 onward was matched against DBLP, the publisher, or arXiv. Gall98, Alla18, Feng20, Hami17, Rend09, Schl18, Chen16 and Jime24 are standard references cited from their known venues. Jia24 and Tava26 are arXiv preprints, and their venues should be rechecked before submission.*

## 10. Replication

Everything is regenerated with these commands, documented in `docs/run-and-verify.md`:

- `scripts/verify_freeze_portable.py` checks the v1 freeze.
- `scripts/paired_analysis.py` writes the v1 paired analysis.
- `scripts/research_v2.py pilot | develop | freeze | evaluate` runs the v2 study.
- `scripts/v2_exploratory.py` writes the exploratory GNN comparisons.
- `scripts/build_tables.py` rebuilds every table.

Ingestion is deterministic. Re-ingesting all nine development projects on a different machine reproduced every frozen v1 dataset file byte-for-byte. The v2 freeze (`artifacts/models/v2/freeze.json`) binds 102 artifacts and records each fresh project's pinned SHA in the final report.
