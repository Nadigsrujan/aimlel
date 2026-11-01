> Completion checkpoint: the new master-brief observatory features, full frozen held-out evaluation, pre-frozen ablations, supplemental frozen baselines, model card and release packaging are implemented. See [current coverage and limits](docs/observatory-implementation.md). The original plan below is retained as history; the primary ranking gate was not met and no held-out retuning was performed.

# Neural Cartographer: architecture review and completion plan

Reviewed 1 November 2026 against the architecture PDF, the newly uploaded nine-slide PowerPoint, both literature surveys, the supplied architecture diagram, the implementation and fresh execution evidence. The user explicitly retained the existing 7 training / 2 validation / 3 test split.

## Architecture implemented

| Layer | Current implementation | Evidence / boundary |
|---|---|---|
| Ingestion | Pinned full Git history; Python AST with Tree-sitter fallback; formatting-aware modified-file labels at the parent snapshot; checksums; resumable signatures. | All nine development datasets verified: 73,994 commits and 89,482 queries. Held-out extraction is in progress under a verified model freeze. |
| Graph | File/class/function/test nodes; containment, resolved imports, conservative same-file calls/inheritance, tests and past co-change. Revision-aware entity identities accompany legacy graph IDs. | Typed relations/gradients and collision/rename cases are tested. Cross-module dynamic call/data-flow analysis and complete storage-ID migration are not claimed. |
| Features and retrieval | Pinned CodeBERT vectors, exact-revision FAISS, directory/static/history/semantic features, immutable blob caches, ancestor-only history. | Full candidate pools are shared by all models. The development diagnostic union covers 96.3% of positives versus 100% for the actual full pool. |
| Learning | Two-layer typed GraphSAGE, MLP scorer, weighted BCE, hard/random negatives, early stopping, separate validation calibration, XGBoost and heuristics. | 140 training / 20 selection / 20 calibration queries. Exact saved weights, loss history and validation metrics reproduced by checkpoint resume. |
| Ablations | Static/history/semantic-only models plus separately frozen removal-of-each-channel models. | Primary weights/baseline are unchanged. Removal models are declared and frozen before primary held-out scores. |
| API and jobs | FastAPI contracts, bounded source, catalog/seeds/snapshots, model readiness, SQLite job coordination, progress, cancellation, retry and retention. | Real public URL → semantic indexing → frozen neural ranking passed. Windows process-tree cancellation and paths containing spaces are handled. |
| Evidence/UI | Responsive React workspace, searchable catalog, graph/ranking filters, pinned source with symbol inspection, test suggestions, cited explanations, export, connections and Model Lab. | Real baseline and learned workflows are browser-verified. Gemini can select existing citations only; live credentials were not available. |
| Research | Primary freeze binds 606 artifacts; once-only held-out study, macro/per-repository metrics, bootstrap intervals, calibration and latency. | Final held-out results are running. Five external SWE-bench and three BugsInPy seeded file-ranking cases are recorded separately. |
| Packaging | Supported workspace-local Python 3.12, pinned Windows dependency lock, clean API-environment smoke, production frontend build, Docker/Compose, optional Neo4j export. | Local smoke/build pass. Docker and a Neo4j server were unavailable for live checks. |

## Changes from the illustrative stack

Git CLI streaming replaces GitPython/PyDriller wrappers; custom traversal replaces NetworkX; relation-aware PyTorch implements the GraphSAGE equations without a PyTorch Geometric dependency. JSON graph artifacts serve the local application, with revision-aware Neo4j CSV/Cypher export available. These choices preserve the implemented algorithms and keep the core local deployment usable without external services.

The newer PPT's GNN + MLP scoring head governs the primary predictor. XGBoost is a separately evaluated baseline, rather than the earlier diagram's mandatory final scoring layer. The 5/1/3 PPT split is superseded by the explicit user decision to retain 7/2/3.

## Remaining execution gates for this session

1. Finish SymPy history extraction; the other two held-out datasets are complete.
2. Verify all held-out pins/checksums, then run the unchanged frozen models on 20 commits per test project. Keep any negative outcome.
3. Publish the exact measured query/candidate/example audit and evaluate the separately frozen channel-removal models on those same tensors.
4. Publish the model card and verified UI study summary, rebuild the frontend, check desktop/mobile presentation, and leave the application running.
5. Package the matching model/freeze/report artifacts and update the task checklist from actual acceptance evidence.

## Explicit follow-on requirements

Function-level supervised ranking and function/class seeds require a distinct label/model study; the current predictor is file-level even though symbols participate in the graph and can be inspected. Complete canonical storage migration, cross-module/dynamic calls, READS/WRITES analysis, and live Neo4j integration remain extensions. The current prototype does not claim these features or function-level accuracy.

The final ranking success gate is empirical. A working trained UI, a positive external case study, or an attractive graph cannot substitute for the frozen unseen-project comparison. Full fusion must be reported alongside the strongest baseline and all ablations, including cases where a simpler model performs better.
