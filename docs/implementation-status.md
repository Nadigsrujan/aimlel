# Implementation status — 1 November 2026

The architecture PDF, all nine slides of the new PowerPoint, both literature-survey documents and the supplied architecture image have been reviewed. The explicit user decision retains seven training, two validation and three held-out projects. The newer graph-ranking architecture governs the predictor; the earlier XGBoost-after-GraphSAGE diagram is retained as context, with XGBoost evaluated as a baseline.

## Implemented and verified

- A responsive repository workspace with catalog search, historical SHA selection, learned/heuristic/semantic rankers, Top-K, selectable graph paths, evidence filters, test recommendations, JSON export, symbol/type source inspection and pinned source spans.
- FastAPI response contracts, missing-data states, a bounded source endpoint, model readiness, research provenance, and a Model Lab that withholds incompatible old metrics and publishes verified study artifacts.
- Full development extraction: 73,994 non-merge commits and 89,482 queries across all nine development projects, with integrity verification passing. Two residual parser failures are recorded in SQLAlchemy; they are not silently discarded.
- Exact-revision CodeBERT matrices and FAISS indexes, immutable blob-vector caching, ancestor-only history, conservative lexical calls/inheritance, typed graph tensors, and full eligible-file candidate pools.
- Training on 140 commit queries; 20 independent validation-selection queries and 20 calibration queries. Full fusion, XGBoost, six heuristics, semantic similarity, and separately trained single-channel ablations are recorded. Validation macro Recall@5: fusion 0.285; strongest heuristic co-change 0.280; history-only 0.302.
- A primary freeze binding 606 source, configuration, dataset, semantic and model artifacts. The 60-query held-out study and all pre-frozen ablations are complete; no held-out model tuning was performed. Fusion macro Recall@5 is 0.3968 versus co-change 0.4576, so the primary gate was not met.
- Local extractive, citation-bound explanations and optional Groq/Gemini evidence selectors. Unsupported provider IDs/errors fall back locally. No live provider call is claimed without configured credentials.
- Transactional SQLite jobs shared across API processes, cross-worker cancellation, admission limits, heartbeat recovery, retry, persisted progress and UI refresh recovery. New submitted repositories build exact-revision semantic indexes when a learned checkpoint is installed.
- Persistent AST signatures, example caches and exact-input training checkpoints. An interrupted toy training run resumed with identical loss history and weights. Python 3.12 lives inside the workspace so the virtual environment survives host-runtime resets.
- Docker/Compose configuration and a revision-aware Neo4j CSV/Cypher exporter. Flask export produced 1,705 nodes and 2,005 resolved edges. Docker and a live Neo4j server were unavailable here, so deployment/import are not claimed as executed.

## Executed acceptance evidence

81 backend tests passed, two graph-view tests passed, the frontend production build passed, and npm audit reported zero vulnerabilities. Baseline API smoke and real learned Flask API inference passed; learned inference returned five candidates in 3.375 seconds on the initial local request.

Browser checks covered real neural ranking, path inspection, source entity filtering and the selected test's correct source span. A public ItsDangerous submission was indexed and opened; a Click job was cancelled, retried successfully and reconnected after refresh. Screenshots are saved under `artifacts/reports/`.

The bounded mapping audit inspected nine development commits and 30 changed files: ten were fully symbol-mapped, while twenty retained file fallbacks. Spot checks in Flask, Werkzeug and Sphinx matched the stored source spans. This is not a corpus-wide function-mapping accuracy estimate.

External frozen checks completed on five non-overlapping Xarray SWE-bench Verified cases and three BugsInPy Black fixes. Xarray Recall@5 was 0.800 for fusion and co-change; Black Recall@5 was 0.278 versus 0.167. These use a known changed-file seed and measure file ranking. They do not reproduce benchmark tests or measure autonomous issue repair.

## Completion boundary

The implemented predictor is file-level. Class/function/test nodes participate in graph learning, and their source spans can be inspected, but function-level supervised predictions and function/class seed scoring are not complete. Persisted graph edges retain legacy local IDs; revision-aware IDs are exposed separately and used in the Neo4j export. A full storage-ID migration and cross-module/dynamic call or data-flow analysis remain extensions.

The scientific success criterion is a measured outcome, not a guaranteed implementation result. The final held-out result and channel-removal study must finish before this document can claim their acceptance. Optional live Docker, Neo4j and Gemini validation remains unexecuted. See `architecture.md` and `operations.md` for the exact implementation and deployment limits.

## Run and resume

Use `.venv\Scripts\python.exe scripts/start.py` and open http://127.0.0.1:8080. Run `.venv\Scripts\python.exe scripts/complete_study.py` to resume the frozen research pipeline. The interpreter is under `.runtime/python`; keep it with `.venv`. See README.md for clean setup and verification commands.

## Master-brief observatory extension

The three new master Markdown briefs have been reviewed. The source-grounded 3D Command Deck, Code Metropolis, multi-seed scenario persistence, synchronized comparison twins/rank flow, Git corridor/DNA, module terrain, Code MRI, test constellation, citation-bound Groq adapter, safe ZIP/static baseline, SSE flight recorder and research instrument are implemented additively. Exact DONE/PARTIAL boundaries and commands are recorded in [observatory implementation](observatory-implementation.md). The final model card, audited query list, frontend study summary and matching release archive have been published.


## User handoff — 2 November 2026

The interaction cleanup adds selected-file forecasting, explicit per-seed inspection/explanations, full historical source maps, repository-switch cleanup, automatic WebGL/table recovery, and regression protection for initial/stale graph state. The final suite passed 81 backend tests and 6 graph/state tests. The new launcher was checked against an existing server and on a fresh temporary port. In-app printable help pages explain each view, the complete method, the actual negative held-out result, a five-minute evaluator walkthrough, and daily start/stop instructions. See RUN_SERVER.md and EVALUATOR_GUIDE_ELI5.md. Current task lists replace the archived historical checklists.
