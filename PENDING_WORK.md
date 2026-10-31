# Neural Cartographer — Pending Work

Updated: 31 October 2026

## Latest verified implementation pass

- Backend implementations now live under `backend/src/neural_cartographer/`; existing `scripts/` commands remain compatibility entrypoints.
- Six baseline rankers score the full eligible-file pool before Top-K selection. History includes frequency, recency and co-change Jaccard; static imports support unambiguous `src/` layouts.
- Comparative evaluation records Recall@5/10, Precision@5, MAP, MRR, NDCG, candidate ceiling and commit-clustered confidence intervals.
- Pinned CodeBERT weights were downloaded and a checksum-verified FAISS index was built for the current Flask snapshot. Semantic ranking was verified through the browser. Other snapshots still need their own indexes. FAISS runs in an isolated process because loading it alongside CodeBERT caused a native crash on this Mac.
- Typed GraphSAGE and XGBoost were trained on 35 commits across all seven training projects. Four unseen-project validation queries selected checkpoints; four separate validation queries fitted calibration. These are small development samples, not final research results. See `artifacts/reports/heterogeneous-development.json`.
- Parent-side diff mapping records Git renames and symbol/file fallbacks. Revision-aware entity records and manifest/configuration hashes are returned by analysis; persisted legacy graph IDs still need full migration.
- UI supports ranker selection, evidence/score filters, import-path display, commit links and cancellation. API graph responses are capped at 500 entities. Built UI and API run together with `python scripts/start.py`.
- Added HTTP contract tests, isolated FAISS tests, graph-view tests, local smoke command, packaging metadata and a CI workflow. CI has not yet run on a remote runner.
- Removed the obsolete ingestion report that still referenced the previously deleted unwanted repository.

The sections below describe remaining acceptance work. Some prerequisites are now implemented as listed above; they do not imply that an entire numbered section is complete. Final model freezing, held-out evaluation, external benchmark validation, all-catalog semantic indexing, persistent multiworker jobs, optional Gemini, and full production hardening remain unfinished.

This document lists the remaining work required to complete the approved Neural Cartographer plan. The current system already supports repository ingestion, historical parent snapshots, baseline ranking, FastAPI endpoints, a React graph interface, public GitHub submission, structural import evidence, past co-change evidence, and initial GraphSAGE/XGBoost pilots.

## 1. Contracts and reproducibility

- Complete the formal contract package under `backend/src/neural_cartographer/contracts/`.
- Standardize revision, entity, edge, query, prediction, feature, model, and job schemas.
- Replace legacy line-based graph identifiers with stable revision-aware entity IDs everywhere.
- Add explicit rename aliases and collision tests.
- Record manifest hash, parser version, feature version, encoder version, configuration hash, and random seed in every generated artifact.
- Add contract compatibility tests for API responses and stored artifacts.

## 2. Function and class change mapping

- Map changed Git diff lines to functions and classes in the parent snapshot.
- Support nested functions, classes, decorators, and multiline changes.
- Add rename detection using Git rename metadata and structural similarity.
- Preserve file-level fallback when symbol mapping is ambiguous.
- Publish mapping coverage and ambiguity statistics per repository.
- Verify representative rename, deletion, insertion, and syntax-change cases.

## 3. Candidate generation

- Build structural candidates from resolved imports and bounded graph neighborhoods.
- Add test-to-source and source-to-test relationships.
- Add historical co-change candidates from commits before the cutoff.
- Add semantic candidates from code embeddings.
- Union the channels into one candidate pool with provenance for each candidate.
- Measure recall for each channel and the combined candidate ceiling.
- Ensure the same candidate pool is used by every baseline and learned model.

## 4. Past-only features and embeddings

- Add a pinned pretrained code encoder for file and symbol embeddings.
- Generate embeddings without using future commits or target labels.
- Build a FAISS semantic-neighbor index keyed by repository, revision, encoder, and cutoff.
- Add churn, recency, historical frequency, and co-change strength features.
- Add pair features for seed/candidate distance, relation paths, semantic similarity, and historical evidence.
- Add leakage tests proving future commits cannot affect past feature rows.
- Add deterministic feature caching and cache invalidation tests.

## 5. Baseline models and evaluation

- Complete random, popularity, directory-distance, import, co-change, and semantic baselines.
- Complete XGBoost training using the shared candidate pool and feature schema.
- Add fixed negative sampling and hard-negative sampling.
- Add chronological train/development windows within training repositories.
- Report Recall@5, Recall@10, Precision@5, MAP@10, MRR, NDCG@10, PR-AUC, and candidate ceiling.
- Add macro averages by repository and per-repository metrics.
- Add bootstrap confidence intervals clustered by commit/query.
- Track indexing, feature-generation, training, and inference latency.

## 6. Full graph-learning system

- Build typed snapshot tensors for file, class, function, and test nodes.
- Include typed relations for containment, imports, calls where resolvable, inheritance where resolvable, tests, and past co-change.
- Create deterministic seed/candidate pair datasets with labels isolated from inference features.
- Replace the file-only pilot with the planned heterogeneous GraphSAGE encoder.
- Add relation-specific message transforms and pair scoring.
- Train with BCE, class-imbalance handling, hard negatives, dropout, and early stopping.
- Save model checkpoints with full data/configuration provenance.
- Select checkpoints using validation repositories only.
- Reproduce train loss and validation metrics from saved seeds and configuration.

## 7. Ablations and calibration

- Compare the graph model against the strongest non-neural baseline.
- Run static-only, history-only, semantic-only, and combined-channel ablations.
- Use shared query and candidate pools for every comparison.
- Calibrate probabilities on validation data only.
- Report calibration curves, Brier score, confidence intervals, and ranking metrics.
- Freeze the chosen model and baseline before opening held-out test repositories.

## 8. Evidence and explanations

- Return verified typed graph paths for each recommendation.
- Return source spans and symbol names where mapping is reliable.
- Return past co-change commit references with cutoff provenance.
- Add test recommendations linked to stored test relationships.
- Validate every evidence citation before displaying it.
- Add deterministic fallbacks for missing or ambiguous evidence.
- Implement the optional Gemini evidence agent.
- Restrict the agent to retrieved evidence and citation IDs.
- Reject unsupported claims and keep the core platform usable without an API key.

## 9. Production API

- Move the current adapter into the planned `backend/src/neural_cartographer/api/` package.
- Use versioned request and response models for every endpoint.
- Add repository and snapshot listing.
- Add seed search and symbol selection.
- Add impact-ranking and evidence endpoints.
- Add model/version selection and feature-schema reporting.
- Add job progress events, cancellation, retry, deduplication, and retention policies.
- Add persistent job storage suitable for multiple workers.
- Add repository size, timeout, file-count, and disk-quota enforcement before and during cloning.
- Validate GitHub redirects and resolved hosts.
- Verify submitted repository code is never executed.
- Add API integration tests and OpenAPI contract tests.

## 10. Production frontend

- Move the current single-file React prototype into the planned feature/component structure.
- Add catalog search and repository metadata.
- Add public repository submission, progress, retry, cancellation, and deletion controls.
- Add snapshot and historical commit selection.
- Add file and function seed search.
- Add Top-K, score, node-type, and evidence-channel filters.
- Add graph-size caps and large-graph subgraph loading.
- Add source-span, path, and commit evidence panels.
- Add test recommendations.
- Add accessible loading, empty, error, retry, and no-history states.
- Add keyboard navigation and screen-reader labels.
- Add frontend unit tests and browser integration tests.
- Add API error handling for unresolved seeds, unsupported languages, sparse history, and failed ingestion.

## 11. Catalog and submitted repositories

- Package searchable metadata, licenses, pinned revisions, and sample seeds for all 12 repositories.
- Keep SymPy, scikit-learn, and Django sealed until final model selection is complete.
- Expose the held-out catalog only after final evaluation artifacts are recorded.
- Verify first-visit catalog entries open without re-indexing.
- Verify a new public repository can go from URL submission to evidence view.
- Add no-history, no-Python, oversized, duplicate, failed-clone, and cancellation cases.

## 12. Final evaluation

- Freeze models, features, thresholds, candidate policies, and configurations.
- Evaluate the frozen system on SymPy, scikit-learn, and Django.
- Do not tune against held-out results.
- Report macro and per-repository metrics with confidence intervals.
- Report candidate ceiling, ranking failures, parse failures, latency, resource use, and error categories.
- Compare the final model against the strongest validated baseline.
- Record the result against the project success gate honestly, including a negative result if the neural model does not improve.

## 13. External validation

- Obtain a pinned, non-overlapping SWE-bench Verified revision.
- Derive affected source files from gold patches.
- Audit repository and commit overlap with the training corpus.
- Evaluate candidate recall and document the task mismatch.
- Add a small BugsInPy validation sample where reproducible.
- Record source/file label coverage and limitations.

## 14. Packaging and handoff

- Add a complete `pyproject.toml` or equivalent reproducible Python setup.
- Pin compatible Python, PyTorch, frontend, and graph dependencies.
- Add clean-install setup instructions.
- Add one-command API/UI startup instructions.
- Add data provenance and license documentation.
- Add model card with training data, metrics, limitations, and intended use.
- Add evaluation protocol and leakage audit report.
- Add optional Neo4j adapter documentation and configuration.
- Add optional Gemini configuration and key requirements.
- Add worker limits, retention, disk, CPU, and memory guidance.
- Add a clean-room smoke test for one pilot query.
- Add CI for Python tests, API tests, frontend build, and dependency audit.
- Complete the final architecture review and update `tasks/todo.md` only after acceptance checks pass.

## Current completion boundary

The software currently provides a working ingestion and baseline exploration platform. The research-grade semantic candidate system, full heterogeneous model, validated cross-project evaluation, complete evidence layer, production API/UI hardening, external evaluation, and final handoff are still pending.
