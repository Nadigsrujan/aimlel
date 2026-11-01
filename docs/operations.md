# Local deployment and recovery

Use the workspace Python 3.12 environment and `python scripts/start.py`. The server binds to `127.0.0.1:8080` and serves the production React build. OpenAPI documents the versioned routes at `/docs`. Keep the application local: it has no authentication or multi-user isolation.

The FastAPI job API uses `artifacts/jobs/jobs.sqlite`. SQLite transactions enforce the shared two-job limit and case-insensitive deduplication across API processes on one machine. Each ingestion subprocess heartbeats every two seconds. A heartbeat older than 90 seconds marks the job failed, with an explicit retry action. Cancellation is persisted, holds its capacity slot until the worker stops the subprocess tree, and works when the cancellation request reaches another API process. This is local durable coordination, not a distributed queue across machines.

Jobs permit public HTTPS GitHub owner/repository URLs only. Git redirects are disabled and prompts are disabled. Ingestion reads blobs without checking out or running repository code. Jobs stop at one hour or 2 GiB of repository data. At most 100 terminal/active records are retained. Completed clones and datasets are retained until the user archives a submitted repository. The delete route moves submitted data into `data/deleted/`; pinned study projects cannot be deleted through that route.

New clones are published from a unique staging directory only after Git clone succeeds. A cancelled/failed clone remains under `data/raw/<repository>.cloning-<id>` for inspection; a retry uses a new staging directory. Staging data counts toward that repository's job quota. Disk retention beyond this quota is manual. Keep adequate free disk space for the pinned corpus and code-vector caches.

The deprecated standalone `scripts/serve.py` retains its compatibility JSON registry. Use `scripts/start.py` and the FastAPI API for the current job implementation.

## Resume computation

The interpreter lives under `.runtime/python`, and `.venv` points to it. AST-signature SQLite caches, blob-vector caches, revision semantic indexes, prepared examples and completed training epochs persist in the workspace. Restart the same command after a process interruption. A training checkpoint is reused only when its configuration, code and actual input tensors have the same fingerprint. Final model publication is atomic.

`python scripts/complete_study.py` runs or resumes development ingestion, integrity verification, semantic preparation, training, freeze, held-out ingestion, verification and evaluation in that order. Stage output is appended to `artifacts/reports/study-logs/`; `study-progress.json` records the current stage. Run only one study coordinator. Existing frozen choices are verified and never retrained against held-out results. Final evaluation refuses to overwrite an existing result.

## Optional Gemini

Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the server environment, using a model enabled for that account. Leave them unset for the fully local path. The UI separately opts in to sending repository paths and evidence metadata to Google; source text is excluded. The provider may select only existing citation IDs. The application renders its own evidence statements and rejects unknown IDs or arbitrary provider prose. Errors/timeouts use the deterministic local explanation. Keys are never returned to the frontend.

The adapter follows Google's [generateContent REST contract](https://ai.google.dev/api/generate-content). Its network path is covered with mocked responses; a live provider test requires configured credentials.

## Resource limits

Development training uses two CPU threads; CodeBERT index preparation uses at most eight and runs without CUDA on this machine. File vectors cover the first 256 tokens, use masked mean pooling, and are shared by contained symbols. Prediction result graphs are capped at 500 nodes; the observatory current-snapshot endpoint exposes the full parsed graph and uses instanced buildings/filtered edges; source previews are capped at 200 lines and 2 MiB. Full eligible-file pools are ranked before the API takes Top-K.

## Observatory and Groq

Use `scripts/start.py` or `uvicorn api:app --app-dir scripts` so the additive observatory routes are installed. Copy `.env.example` to `.env` for optional Groq/Gemini configuration; explicit process environment variables take precedence. Only documented provider settings are read, without interpolation or code execution. Groq follows its [chat-completions API](https://console.groq.com/docs/api-reference); the UI requires explicit hosted metadata consent and rejects invented citation IDs. Missing credentials or provider failures use local evidence.

Saved scenarios, event sequences and explanation cache live in `artifacts/observatory.sqlite3`; uploaded ZIP snapshots live in `artifacts/archive-snapshots/`. These local user artifacts are excluded from Git and release bundles. ZIPs are never extracted or executed. Archive forecasts are explicitly untrained static/directory baselines.

`scripts/finalize_study.py` can resume publication after the primary evaluation. It validates matching freezes before publishing and never retrains from held-out outcomes. Check `artifacts/reports/finalization-progress.json` and the process log.
