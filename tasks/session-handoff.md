# Final session checkpoint — 2026-11-01

The user’s three new master briefs are read and implemented through the additive observatory layer. See docs/observatory-implementation.md for exact coverage and limitations. Existing frozen backend source and primary model remain unchanged; all 606 hashes verified.

The held-out coordinator and finalizer both completed. Reports: final-heldout.json, final-study-audit.json, leave-one-out-heldout.json, frozen-comparators-heldout.json. Final model card and frontend study summary are published. Main gate is FALSE: fusion Recall@5 .396754 vs cochange .457588, NDCG@10 .407220 vs .462086. XGBoost supplementary Recall@5 .348500. Do not retune against these test outcomes.

All 12 study repos and five submitted demo repos are available; all 17 current relation caches warmed. All CodeBERT current indexes and the audited historical study indexes are built. Workspace Python 3.12 survives resets under .runtime/python; .venv points to it.

Server is live at http://127.0.0.1:8080. Owned parent PID is in artifacts/reports/local-server.pid; verify its command contains scripts/start.py before stopping its tree. Start uses scripts/api.py so new observatory routes and optional .env provider settings are installed. Docker was updated to use that entrypoint.

Critical checks: archive malicious paths, archive static baseline, real graph identity/imports, real two-seed learned runs and exact reload, history volume math, real research data, local explanation hashes, hosted consent, fabricated Groq citation rejection, SSE cursor replay. The frontend production build and npm audit (zero known vulnerabilities) passed. Full backend regression passed: 81 unittest tests, plus two graph-view tests. Responsive laptop/mobile browser checks passed.

Release: artifacts/releases/neural-cartographer-87277161a5cd.zip; rerun scripts/package_demo.py after final screenshots/docs so the manifest includes them. Bundles omit raw repos/encoder/runtime/user scenarios/uploaded source and secrets. The package has a checksummed manifest and ZIP CRC validation.

Limits: forecasts remain file-level; functions/classes/test-named entities are inspectable and select their owning file. ZIP uses an untrained static/directory baseline. Historical city views use saved up-to-500-entity slices. Groq/Gemini live calls need configured credentials; no live provider success is claimed. No untrusted code/tests executed. P3 cloud/collaboration/GitHub App integrations and reliable test execution are not part of this local demo.
