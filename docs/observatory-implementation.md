# Observatory implementation checkpoint — 2026-11-01

The three new root master briefs have been read. `NEURAL_CARTOGRAPHER_COMPLETE_AGENT_BRIEF.md` contains the master prompt and visualization prompts verbatim. The user's explicit **7 / 2 / 3** split overrides their illustrative 5 / 1 / 3 split.

Implemented additively in this checkpoint:
- React Three Fiber 8 / React 18 Code Metropolis using real pinned graph entities, instanced file buildings, package districts, source-extent heights, actual symbol markers, resolved import fibers, ranked reveal, focus/search, reduced-motion behavior, WebGL/table fallback.
- Command Deck plus Impact Lab, Evolution Observatory, Evidence & Explainability, Test inspection queue, Settings & Provenance, and links to existing Jobs and Research views. Existing impact explorer remains available.
- Shared file selection between the city, ranked list and source inspector; function search selects exact source spans while forecasting explicitly uses the owning file.
- Persisted multi-seed forecasts (up to five files), retained per-seed model results, documented reciprocal rank aggregation, cached Top-K filtering, JSON/CSV/escaped HTML exports and saved scenario comparison with synchronized 3D cameras.
- Unified-diff preview selects existing modified-file seeds without changing source.
- Module risk terrain with explicit sum/mean/count formulas and denominators; static-import Test Constellation; actual source hierarchy Code MRI with conservative CALLS/INHERITS and line links; measured commit-volume corridor/DNA with conventional timeline.
- Recorded research curves, paired validation metric differences, error-case exploration, actual scoring p95, confidence intervals and artifact hashes; saved forecast rank-flow comparison.
- Real first-parent Git timeline; historical prediction uses the parent SHA; observed modified-file truth requires an explicit reveal after a saved prediction.
- Groq/Gemini/local citation-selection interface, explicit hosted metadata consent, server-only credentials, configurable model, validated allowlisted citations, immutable evidence cache and deterministic fallback. No arbitrary provider prose displayed.
- Durable SQLite event sequences and SSE replay through Last-Event-ID; flight recorder shows actual job observations and prediction/explanation events. Observation timestamps are not misrepresented as original phase durations.
- Safe ZIP source inspection: compressed/expanded/file-count limits, source-size bounds, encryption/symlink/special-file/path traversal/duplicate/ratio checks; no extraction and no code execution. Archive snapshots have an explicitly untrained static-import/directory forecast, with no Git history or learned weights.
- Runtime recursion limit raised in API/research/catalog wrappers to handle deep SymPy ASTs without modifying frozen model/source artifacts.

Focused checks passed: graph identity and real imports, Flask 1705 entities / 2005 resolved edges; archive parsing and adversarial paths; real frozen learned two-seed ItsDangerous run and exact reload; evidence hash; hosted consent rejection; all 606 frozen hashes. Frontend production build passes. Archive static-path baseline, recorded commit-volume formulas, research endpoint and rejected invented Groq citations were also checked. Real SSE replay passed (event 1 followed by event 2 after Last-Event-ID=1). Final regression re-run passed: 81 backend unittest tests (13.774s), two graph-view tests, focused observatory checks and production build. Browser verification covered 1366×900 and 390×844; the mobile document stayed within the viewport.

Remaining/partial against the full aspirational briefs:
- ZIP imports use a real static/directory baseline; they do not fabricate Git history or use the frozen Git/CodeBERT model. Historical cities use saved graph slices (up to 500 entities), clearly labeled with their exact SHA.
- Function/class/test inspection is implemented; the trained/evaluated target remains files. No function-supervised accuracy claim.
- Test relationships are static imports and ranked associations, not executed coverage. Risk terrain aggregates the displayed ranked set, with graph-slice denominators for historical data.
- Saved-forecast rank flow is implemented. The original validation report stores per-query metrics rather than per-candidate ranks, so its ablation view displays actual paired metric differences instead of inventing rank trajectories. Collaborative/cloud/GitHub App integrations remain P3 future work.
- Groq remote request implementation is present; a live provider call requires the user's configured server credentials and an available GROQ_MODEL. No key was requested or invented.
- Postgres/Neo4j/Redis production deployment remains optional; local durable stores and typed graph are used. No Docker daemon is installed for a container build check.
- Final held-out evaluation, all six pre-frozen ablations, supplementary frozen XGBoost/heuristic comparisons, query audit, model card, frontend publication and release packaging are complete. The primary success gate was not met; no model was retuned against held-out outcomes.

Launch: `.venv\Scripts\python.exe scripts/start.py`, http://127.0.0.1:8080. Build: `npm run build --prefix frontend`. Focused check: `.venv\Scripts\python.exe scripts/check_observatory.py` (requires localhost access for the in-process TestClient on this Windows sandbox).

Stable city slots are stored per repository/path in browser local storage. Unchanged paths retain coordinates across snapshots; renamed paths receive new slots without claiming verified rename continuity. Historical graph slices and full current graphs share this path layout.

`scripts/finalize_study.py` completed: it validates/publishes the query audit, evaluates pre-frozen extra ablations, republishes the model card/UI summary, builds the frontend and packages the matching release after the primary report appears. Its progress is in `artifacts/reports/finalization-progress.json`. The recorded primary result is fusion Recall@5 0.396754 / NDCG@10 0.407220 versus the validation-selected co-change baseline 0.457588 / 0.462086 (60 queries, three held-out projects). XGBoost supplementary Recall@5 is 0.348500.

All 17 current catalog relation caches are warmed, including the formerly failing deep SymPy AST. Held-out query/candidate tensor checksums are recorded in final-study-audit.json. Supplementary comparator reporting occurred after the primary report, using only already-frozen weights and the exact audited input pool, with no fitting or baseline reselection.
