# Neural Cartographer task checklist

Status: implementation in progress following approval. Checked tasks reflect ingestion deliverables only. Each numbered task is a focused implementation slice. Complete acceptance and verification before checking a task.

Current partial work: package implementation now lives under `backend/src/neural_cartographer/`. T06/T16 have browser-verified semantic ranking, selectable import paths, evidence filters and a built UI served by FastAPI. T07 has tested Git diff mapping and rename metadata. T10 has a 25-query comparison of six full-pool baselines. T09 has a verified pinned CodeBERT/FAISS index for current Flask only. T11/T12 have a typed structural/history GraphSAGE development experiment across seven training and two validation projects, with XGBoost, hard negatives, early stopping and separate calibration queries; semantic model inputs, larger evaluation, ablations and final freeze remain pending. T22 has persisted single-process jobs, concurrency/size/time limits, cancellation and recoverable submitted-repository deletion; multiworker storage, refresh and full acceptance coverage remain pending. See `PENDING_WORK.md` for the remaining acceptance boundary. Held-out projects remain sealed.

## Phase 0 — research freeze

- [x] **T01 — Dataset manifest (deps: none; S).** Record URLs, licenses, pinned SHAs, date windows, inclusion/exclusion rules and project split in `data/manifests/`. Completed for all 12 repositories; summaries contain license paths, revisions and extraction counts.
- [ ] **T02 — Reproducibility contract (deps: T01; S).** Define stable entity IDs, graph/feature schema, query/label schema, API payloads and artifact version fields in `docs/` and `contracts/`. Verify sample commit and rename cases can be represented without collision.
- [x] **Checkpoint A.** User approved the plan and repository scope; all splits are pinned and the local data footprint is recorded.

## Phase 1 — smallest complete path

- [x] **T03 — Repository fetch and commit filter (deps: T01; M).** Full default-branch history for all 12 repositories is pinned under `data/raw/`; non-merge events, generated/vendor exclusions, whitespace handling and bulk-event rules are audited in processed outputs.
- [x] **T04 — File graph at revision (deps: T02,T03; M).** Current pinned snapshots contain file/class/function/test nodes plus containment and import evidence. Stdlib AST uses a Tree-sitter fallback for modern syntax; seven focused tests pass.
- [x] **T05 — Pre-commit labels and simple ranker (deps: T03,T04; M).** Historical queries reconstruct parent graphs, rank eligible files excluding the seed, and join labels only in evaluation. Parent identity and seed exclusion are tested; 25 Flask queries evaluated without failures. Historical snapshots use one streaming Git blob reader.
- [ ] **T06 — Minimal impact API and UI slice (deps: T05; M).** Serve one pinned query with ranked file candidates and display it in a selectable graph view. Verify seed selection → Top-K → evidence path in a browser.
- [ ] **Checkpoint B.** A real historical commit is reproducible end to end; no features use its outcome during scoring.

## Phase 2 — data quality and baselines

- [ ] **T07 — Function identity and diff mapping (deps: T04; M).** Map changed lines to stable function/class nodes with rename handling and file fallback. Verify a sample of mapped changes manually and publish coverage.
- [ ] **T08 — Test relationships and candidate union (deps: T05,T07; M).** Add test nodes/links and structural, history and semantic candidate channels. Verify per-channel candidate recall and union ceiling.
- [ ] **T09 — Past-only features and embeddings (deps: T08; M).** Compute code vectors, FAISS neighbors, churn, recency and pair features keyed by cutoff. Verify a future commit cannot change a past feature row.
- [ ] **T10 — Baseline training/evaluation (deps: T09; M).** Run heuristics plus XGBoost on the same candidate pool; produce pilot development metrics and validation design. Verify fixed splits, negative sampling and bootstrap procedure.
- [ ] **Checkpoint C.** Pilot development report includes candidate ceiling, failures, runtime and pinned artifacts. Full project split remains frozen before validation and final testing.

## Phase 3 — graph learning

- [ ] **T11 — Heterogeneous GraphSAGE dataset (deps: T09,T10; M).** Build typed snapshot tensors and seed/candidate pairs without future edges. Verify toy-graph relation semantics and deterministic data loading.
- [ ] **T12 — Pair scorer training (deps: T11; M).** Train two-layer relation-aware encoder with BCE and hard negatives; choose checkpoint on validation only. Verify train loss and validation rank metrics reproduce from saved seed/config.
- [ ] **T13 — Ablations and calibration (deps: T12; M).** Remove one evidence channel at a time, calibrate probabilities on validation, compare strongest baseline. Verify shared query pools and confidence intervals.
- [ ] **Checkpoint D.** Freeze GNN and baseline choices from validation results; keep held-out projects sealed until T19.

## Phase 4 — explanation and product

- [ ] **T14 — Evidence retrieval (deps: T08,T13; M).** Return typed paths, source spans and past co-change commits per Top-K node. Verify each displayed statement resolves to a stored path or commit.
- [ ] **T15 — Optional grounded Gemini explanation (deps: T14; S).** Explain only retrieved evidence with citation IDs and a deterministic fallback. Verify unsupported claims are rejected or omitted.
- [ ] **T16 — Full graph UI (deps: T06,T14; M).** Add score/type filters, path inspection, test recommendations and loading/error states. Verify keyboard access and a large-repository subgraph cap.
- [ ] **T17 — Ingestion and model API contracts (deps: T13,T16; M).** Add job status, repository/snapshot selection and versioned response types. Verify schema compatibility and clear errors for unresolved seeds.
- [ ] **T22 — Public URL ingestion jobs (deps: T03,T17; M).** Validate public GitHub URL, pin SHA, queue bounded analysis, deduplicate jobs, report progress and allow deletion. Verify rejected internal/oversized targets and that repository code is never executed.
- [ ] **T23 — Built-in 12-repository catalog (deps: T01,T17,T19; M).** Register all 12 pinned projects with searchable metadata and sample seeds, and package precomputed graphs/features after the frozen evaluation. Verify entries open without first-visit indexing.
- [ ] **T24 — Submitted-repository UI flow (deps: T16,T22,T23; M).** Add catalog search, URL form, progress and refresh, then route to seed selection and impacts. Verify a public project from submission to evidence view, including no-history and error states.
- [ ] **Checkpoint E.** A user can inspect a real planned change and understand each recommendation's evidence.

## Phase 5 — final study and handoff

- [x] **T18 — Held-out repository ingestion (deps: T13,T17; M).** SymPy, scikit-learn and Django are fetched, pinned and integrity-verified. Their partition remains `test`; their labels must not be used for model selection.
- [ ] **T19 — Final evaluation (deps: T18; M).** Run frozen models, macro and per-repo metrics, confidence intervals, latency and error categories. Verify no test-repository tuning and publish reproducible configs.
- [ ] **T20 — External cases and report (deps: T19; M).** Evaluate non-overlapping SWE-bench Verified cases and sampled BugsInPy fixes where feasible, then write limitations and demo cases. Verify source/file labels and overlap audit.
- [ ] **T21 — Packaging and operational checks (deps: T17,T20; M).** Provide setup, local run instructions, data provenance, model card and clean-room smoke run. Verify a fresh environment can reproduce one pilot query and the report tables.
- [ ] **T25 — Platform handoff (deps: T19,T21,T23,T24; M).** Expose the full catalog after frozen evaluation, document worker limits, retention, optional Neo4j and optional Gemini configuration. Verify a clean setup can browse the catalog and analyze a new public repository without external API keys.
- [ ] **Checkpoint F.** Review all metrics against success gate, demonstrate UI, and record any negative result without changing the predeclared protocol.

## Parallel work after approval

API/UI can progress after T05 while function mapping is developed. Evidence UI design can start once T14's response contract is fixed. Final test data stays untouched until T18. Each task should generally touch no more than five files; split it further if implementation grows.
