# Neural Cartographer end-to-end plan

Status: approved architecture, implementation in progress. Ingestion, snapshot reconstruction, baseline evaluation, FastAPI adapter and a React graph interface are implemented to varying verification levels. See todo.md for acceptance status; this document describes the target architecture, not a claim of completion.

## Goal and research question

Given a developer-selected Python file or function at repository revision `t`, rank other files/functions/tests likely to change in the same maintenance event, and show the evidence behind each result. The research question is whether combining current structural dependencies, semantic code similarity, and *past-only* co-change history improves held-out ranking over each signal alone. Observed co-change is a proxy label, not proof of causal impact or a promise that a component needs editing.

## Scope and success gate

First release: a public-repository platform with 12 preindexed Python projects and a form to submit another public GitHub repository URL. Users select a snapshot and file/function seed, then receive ranked files/functions/tests, scores, evidence paths and an interactive graph. Function-level predictions appear only when mapping coverage is reliable. No automatic code edits. Research success requires the full model to beat the strongest non-neural baseline on held-out macro-averaged Recall@5 and NDCG@10 with confidence intervals. If it does not, report the result honestly and serve the best validated baseline.

## Architecture

```text
Git repository at revision t ─┬─ AST/static analysis ────────┐
                             ├─ Git commits before t ───────┤
                             └─ code embeddings ────────────┤
                                                               v
                         versioned heterogeneous graph + feature store
                                                               |
                                candidate union: 2-3 hop graph, past co-change, semantic neighbors
                                                               |
                             GraphSAGE relation-aware encoder + pair scoring head
                                                               |
                            Top-K + calibration + dependency/history evidence
                                                               |
                             FastAPI ── React graph UI ── optional LLM explanation
```

Offline pipeline: pin manifest of repository URLs, commit SHAs and split; mine eligible historical commits; build pre-commit snapshots; extract typed nodes/edges and changed entities; calculate past-only features; generate positive and plausible negative pairs; train/tune; evaluate once on held-out repositories; register model and feature/schema versions. Online pipeline: ingest a pinned repository snapshot, resolve selected seed, construct the same features and candidates using only available history, score, retrieve evidence, serve graph view, optionally explain retrieved evidence with Gemini. The model produces scores; the LLM only paraphrases cited evidence and can be disabled.

### Project layout and ownership

This is the intended layout. Directories exist as placeholders; named code and configuration files are future deliverables, not implemented files.

```text
AIMLEL/
├── README.md                         # setup and demo (T21)
├── pyproject.toml                    # Python dependencies (T03)
├── .gitignore                        # local data and weights (T03)
├── .env.example                      # optional service settings (T15)
├── configs/
│   ├── datasets.yaml                 # repository split and cutoffs (T01)
│   ├── extraction.yaml               # filters (T03)
│   ├── features.yaml                 # feature versions (T09)
│   └── experiments/                 # training configs (T10-T13)
├── docs/
│   ├── architecture.md               # design decisions (T02)
│   ├── data-contract.md              # IDs and schemas (T02)
│   ├── evaluation-protocol.md        # leakage rules and metrics (T10)
│   └── model-card.md                 # measured limitations (T21)
├── data/
│   ├── manifests/                    # tracked URLs, SHAs, checksums
│   ├── raw/                          # ignored Git clones and downloads
│   ├── interim/                      # ignored diff and AST maps
│   └── processed/                    # ignored graphs, features, query pairs
├── backend/
│   ├── src/neural_cartographer/
│   │   ├── contracts/                # typed IDs and payloads (T02)
│   │   ├── ingest/                   # Git, diffs, rename and filters (T03)
│   │   ├── graph/                    # parser, resolver, snapshots (T04,T07)
│   │   ├── labels/                   # changed sets and query labels (T05,T07)
│   │   ├── candidates/               # structural/history/semantic union (T08)
│   │   ├── features/                 # embeddings and past-only features (T09)
│   │   ├── learning/                 # baselines, GNN, calibration (T10-T13)
│   │   ├── evidence/                 # paths, snippets, explanation (T14,T15)
│   │   ├── evaluation/               # ranking metrics and leakage audit (T10,T19)
│   │   ├── api/                      # FastAPI routes and schemas (T06,T17)
│   │   ├── jobs/                     # bounded ingestion workers (T22)
│   │   ├── catalog/                  # built-in registry (T23)
│   │   └── cli/                      # reproducible batch entrypoints (T21)
│   └── tests/
│       ├── fixtures/                 # tiny Git and graph cases
│       ├── unit/
│       └── integration/
├── frontend/
│   ├── src/
│   │   ├── api/                      # typed client
│   │   ├── features/                 # catalog, URL form, seed and impact list
│   │   ├── graph/                    # React Flow view and path controls
│   │   └── components/               # shared accessible UI
│   └── tests/
├── experiments/                      # run configs and notes
├── artifacts/
│   ├── models/                       # ignored model binaries
│   └── reports/                      # generated results
├── scripts/                          # fetch and smoke entrypoints
└── tasks/
    ├── plan.md
    └── todo.md
```

`contracts` defines IDs and formats before producers or consumers. `ingest` owns historical facts; `graph`, `labels`, `candidates` and `features` consume pinned snapshots; `learning` does no Git or HTTP work; `api` orchestrates queries; `frontend` consumes a versioned API. Raw clones, generated features and model weights stay out of version control. No third-party repository belongs in application source.

### Data contracts and APIs

- Revision: `{repo_id, source_url, commit_sha, parent_sha, event_time_utc, split, extraction_version}`. The repository ID is canonical owner/name.
- Entity: `{repo_id, revision_sha, kind, qualified_path, source_span, stable_symbol_key}`. Rename aliases are explicit; ambiguous function mapping falls back to a file.
- Edge: `{source_id, target_id, relation, revision_sha, provenance, resolution_status}`. Historical edges additionally carry a cutoff and past-only count.
- Query: `{repo_id, revision_sha, seed_id, candidate_ids, label_ids, history_cutoff, candidate_policy_version}`. Labels are unavailable to feature and inference code.
- Prediction: `{candidate_id, raw_score, calibrated_probability_if_validated, rank, evidence_ids, model_version, feature_version}`. A raw score is not presented as a probability.
- Every generated artifact records manifest hash, source revision, configuration hash and random seed. Cache keys include history cutoff.

The API will provide repository/snapshot listing, public URL submission, seed search, ingestion job status, impact ranking, and evidence/subgraph retrieval. Exact routes and payloads are fixed in T02/T17. Batch training and interactive inference share feature definitions.

### Component boundaries and storage

| Component | Responsibility | Proposed implementation |
|---|---|---|
| `ingest` | Allowed source paths, Git metadata, rename tracking, commit filtering | Git CLI/PyDriller, immutable manifest |
| `graph` | Python AST entities; typed `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, `TESTS`, `CO_CHANGE` edges with provenance and snapshot ID | Tree-sitter plus targeted Python resolution; NetworkX for initial prototype |
| `features` | Code embedding, centrality, churn, recency, pair distance and past co-change strength | Pretrained code encoder; parquet/Arrow feature cache; FAISS for nearest neighbors |
| `learning` | Shared candidate pool, leakage-safe labels, baselines, GNN, probability calibration | PyTorch Geometric GraphSAGE pair head; XGBoost and heuristic comparators |
| `evidence` | Short typed paths, code locations and commit references supporting each recommendation | Deterministic retrieval before optional Gemini explanation |
| `api` | Repository job status, seed lookup, ranked impacts, evidence and graph subview | FastAPI, versioned response contracts |
| `web` | Select seed, filter by score/type, inspect paths and recommended tests | React/Vite, React Flow |

Neo4j is an optional adapter after the NetworkX prototype proves the schema; Qdrant is unnecessary for the first version if FAISS meets scale. Separate training snapshots from a current online graph. Feature generation should be content-addressed by repository, SHA, parser version, encoder version and history cutoff. Store source URLs/commit SHAs, never opaque “latest” data in an experiment.

## Dataset decision

The primary dataset is **derived from full Git histories of selected Python repositories**, because this task requires chronological pre-change graph features and many examples of real co-change. A benchmark row or a latest-source archive alone cannot supply those features. Proposed project-wise split, subject to an eligibility audit of license, commit volume, parse quality, runtime and cross-file events:

| Use | Repositories | Reason |
|---|---|---|
| Pilot development within train | [Flask](https://github.com/pallets/flask), [Requests](https://github.com/psf/requests) | Chronological internal train/dev windows to debug the pipeline |
| Full training (7) | Flask, Requests, [pytest](https://github.com/pytest-dev/pytest), [Sphinx](https://github.com/sphinx-doc/sphinx), [Pydantic](https://github.com/pydantic/pydantic), [HTTPX](https://github.com/encode/httpx), [Werkzeug](https://github.com/pallets/werkzeug) | Varied frameworks, libraries and test infrastructure |
| Validation (2) | [FastAPI](https://github.com/fastapi/fastapi), [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) | Unseen projects for model choice, calibration and thresholds |
| Held-out test (3) | [SymPy](https://github.com/sympy/sympy), [scikit-learn](https://github.com/scikit-learn/scikit-learn), [Django](https://github.com/django/django) | Distinct domains and scale; final evaluation after freeze |

The pilot is a pipeline sanity check within future training projects, not a held-out benchmark. Freeze the full split before model development; never inspect held-out outcomes to change features, thresholds, eligibility rules or architecture. All 12 repositories enter the user-facing catalog, but the three test repositories are only exposed after the final evaluation is recorded. If eligibility audit rejects a repository, record why and choose a replacement before the split freeze. Record exact SHAs, licenses and extraction counts in `data/manifests/`.

Secondary external check: [SWE-bench Verified](https://huggingface.co/datasets/SWE-bench/SWE-bench_Verified) provides 500 curated issue/PR instances with base revisions and gold patches; derive affected *source* files from gold patches and inspect candidate recall. It evaluates issue-driven edits and is not a substitute for co-change training. Exclude any repository or commits overlapping training when making a cross-project claim, or call the analysis an in-domain case study. [BugsInPy](https://github.com/soarsmu/BugsInPy) supplies reproducible Python bug/fix versions and tests for a small qualitative validation set; its bug-fix focus does not cover arbitrary future co-changes. [SWE-bench repository](https://github.com/SWE-bench/SWE-bench) documents dataset access. Defects4J is Java and outside phase-one scope.

## Public repository platform

The home page opens with **Explore repositories**: 12 searchable, preindexed examples, each with source URL, pinned revision, indexing status and a sample query. **Analyze a public repository** accepts a GitHub HTTPS URL in v1, canonicalizes owner/name, resolves and pins the current SHA, checks Python content and size, then queues ingestion. The user sees progress and can search or select a seed file/function, set Top-K, inspect scores and typed paths, open source/commit evidence, and view suggested tests. Refresh creates a new pinned snapshot. User-submitted repositories use the frozen cross-project model without retraining. If history is sparse, structural and semantic scoring remain available and historical evidence is marked unavailable.

Ingestion uses bounded asynchronous workers, job deduplication by URL/SHA/pipeline version, timeout/size caps, cancellation, and per-repository isolation. Accept only public `https://github.com/owner/repo` URLs in v1. Validate redirects and resolved hosts, do not execute repository code, and use Git subprocess arguments without shell interpolation. Exclude submodules, binaries, generated/vendor paths and oversized files while recording counts. Give users a way to delete submitted data. The 12 catalog entries should be generated at setup/deployment from pinned manifests or shipped as precomputed artifacts, so a first visitor need not wait for their indexing. The three held-out repos enter the catalog after the final research evaluation is frozen.

## ML, deep learning, and agent methodology

The primary predictor is a two-layer, relation-aware heterogeneous GraphSAGE encoder over file/function/test nodes. Node inputs combine a pinned pretrained code embedding, node type/module information, graph statistics, and history features computed strictly before the query cutoff. Relation-specific message transforms handle static edge types; past co-change is a weighted relation. A pair head takes seed/candidate embeddings plus typed path summary, distance, semantic cosine and past co-change strength, and produces a ranking logit. Train with binary cross-entropy and plausible hard negatives; assess pairwise ranking loss as a documented ablation. Use dropout, early stopping, fixed random seeds and class-imbalance handling. Rank the full candidate pool at evaluation and inference. Calibrate on validation only; do not display uncalibrated scores as probabilities. Pin model weights, encoder revision, graph schema, feature config, data manifest and seed with each checkpoint. Compare against XGBoost using the same explicit features and against individual-signal baselines.

An optional read-only evidence agent uses bounded tools to inspect the already ranked subgraph, source spans, past co-change commits and test mapping. Workflow: retrieve evidence, draft explanation citing evidence IDs, validate cited IDs/claim scope, return explanation or deterministic fallback. It cannot create labels, change scores, fetch arbitrary URLs, run code or write patches. Measure explanation faithfulness separately from ranking quality. The core platform works without an LLM.

Neo4j Community Edition is an optional persistence/query adapter for current graphs and path search once scale warrants it. Versioned graph files and PyTorch Geometric tensors remain the reproducible training path; Neo4j is not the model itself. FAISS is the first semantic search index. Add a hosted graph or vector service only if measured requirements demand it.

## Credentials and infrastructure

| Service | Required? | Use |
|---|---|---|
| Public Git clone | No key | Built-in and user-submitted public GitHub repositories |
| GitHub token | Optional | API metadata and higher rate limits; cloning works without it |
| Hugging Face token | Usually no | Public benchmark metadata and open encoder weights; gated model choice would require one |
| Gemini API key | Optional | Evidence agent only, when enabled |
| Neo4j username/password | Only if Neo4j enabled | Local/container graph database authentication; no vendor API key required |
| Frontend | No key | Calls the project's FastAPI service |

Keep credentials in environment variables; provide `.env.example` containing names and feature flags but no values. A fully local deployment can run the ranking and deterministic evidence view without external API keys. External LLM calls require explicit UI action, bounded context and cost/error handling.

## Label and evaluation protocol

For eligible commit `c` and changed seed `u`, construct graph/features at `parent(c)` using commits strictly before `c`. Positives are other source/test entities changed in `c`; negatives are eligible candidate neighbors unchanged in `c`. Exclude merges, generated/vendor files, bulk formatting, massive commits and ambiguous renames; document thresholds after a pilot audit. Split multi-file versus single-file examples explicitly; report the candidate generation ceiling before ranking. Prefer file-level labels initially; map changed line ranges to functions when AST identity is stable, otherwise fall back to files. One commit is an imperfect unit of intent, so report noise and avoid claiming causality.

Training uses chronological windows within train repositories, with validation on an unseen repository and final tests on unseen repositories. No future history in node/edge features, embeddings, graph statistics, candidate generation, thresholds or calibration. Deduplicate equivalent patch/cherry-pick events. Candidate pool, negative sampling and seed exclusion are identical across comparators. Evaluate all eligible candidates per query, rather than only sampled negatives. Report macro average by repository, per-repo results, Recall@5/10, Precision@5, MAP@10, NDCG@10, candidate ceiling, PR-AUC and calibration where meaningful. Bootstrap confidence intervals by query/commit cluster. Ablate static, semantic and history channels; compare random/popularity, graph distance, co-change frequency, cosine similarity and XGBoost on the same features. Track ingestion cost and inference latency separately from explanation latency.

## Delivery order and checkpoints

1. Freeze dataset manifest, split and extraction rules; audit disk/network/CPU and repository licenses.
2. Build a tiny one-repository vertical slice: pinned commit → file graph → historical label → simple rank → API → minimal UI.
3. Validate temporal correctness and candidate ceiling on the pilot; then add function mapping and test links.
4. Add semantic and history features, baselines and XGBoost; establish a reproducible non-neural result.
5. Train heterogeneous GraphSAGE and pair scorer; tune on validation only; run ablations.
6. Add evidence paths, optional grounded explanation, catalog and public-repository submission flow.
7. Freeze model, run held-out evaluation and external case studies, then expose all 12 catalog repositories, measure scaling and prepare report/demo.

Each phase ends with the acceptance checks in `tasks/todo.md`. Indicative sequence: week 1 contracts and pilot ingestion; week 2 graph, labels and first UI path; week 3 features and baselines; week 4 GNN and ablations; week 5 evidence and UI; week 6 held-out evaluation; week 7 report and reproducibility. These are planning windows contingent on compute and history volume.

## Downloads and local data policy

All 12 primary repositories have been downloaded and pinned. External benchmark metadata remains a separate deliverable. Preserve full histories for selected time windows; never use shallow clones for historical training. Store clones and caches under ignored `data/raw/`, extracted features under ignored `data/processed/`, and small pinned manifests in `data/manifests/`. Pin exact SHAs and dataset revision hashes with checksums. Running benchmark test suites may require separate environments/containers and is optional for impact-label evaluation.

## Risks and unresolved choices

| Risk | Mitigation |
|---|---|
| History leakage from snapshot/embedding cache | Cutoff-aware feature tests, immutable manifest, pre-commit graph fixtures |
| Co-change labels reflect developer behavior, not actual dependency | State proxy clearly; source-only and test-only results; evidence review |
| Python calls/imports can be dynamic | Preserve unresolved edges and confidence; measure parser resolution coverage |
| Large history and GNN cost | Pilot first, cache snapshots incrementally, stage large repos |
| Project overlap with SWE-bench | Deduplicate by repository and SHA; label external check as in-domain when needed |
| LLM hallucinated reasons | Only provide retrieved paths/snippets; require cited evidence; deterministic fallback |

Approval of this plan authorizes staged public-repository downloads and implementation. Gemini explanation stays optional; no API key is needed for the core platform.
