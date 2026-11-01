# Neural Cartographer

A local Python repository explorer for change-impact ranking, revision-specific source evidence, static import paths, and past co-change history. The React interface supports repository search, historical snapshots, ranking filters, test-file recommendations, and JSON export.

The learned system uses typed GraphSAGE, CodeBERT file vectors, and seed/candidate features. Learned checkpoints are exposed only after training; heuristic and semantic scores are uncalibrated ranking values. Final research results are not implied by a successful UI demonstration. See `docs/implementation-status.md` for the verified completion boundary.

## Run on Windows

Use Python 3.12 and Node.js. From the project root in PowerShell:

```powershell
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location).Path '.runtime\python'
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-lock-windows-py312.txt
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python.exe scripts/start.py
```

Open http://127.0.0.1:8080. OpenAPI is at http://127.0.0.1:8080/docs. On other platforms, create a supported Python 3.10–3.12 environment and install `requirements-ml.txt` and `requirements-dev.txt`; use that environment's Python for the same scripts.

Clones, processed datasets, encoder weights, model checkpoints and frontend build output are local artifacts excluded from Git. A fresh checkout shows which catalog entries still need local data.

## Restore development data

The approved split is seven training, two validation, and three held-out projects. Development catalog routes keep the held-out projects sealed.

```powershell
.venv\Scripts\python.exe scripts/ingest.py --clone --reuse --split train --split validation --workers 2
.venv\Scripts\python.exe scripts/verify_dataset.py --split train --split validation
.venv\Scripts\python.exe scripts/prepare_semantics.py --download
```

`--reuse` accepts existing artifacts only when their checksums and extraction version match. Semantic indexes are keyed by exact revision and pinned encoder configuration. Unchanged Git blobs reuse code vectors across historical snapshots.

AST signatures, prepared training examples and epoch checkpoints persist on disk. Restart the same command after an interruption to reuse completed work. Keep the workspace-local `.runtime` directory with `.venv`; the environment points to that interpreter.

For a new public repository, use **Connect repository** in the UI. The server reads Git blobs without executing submitted code. Core ranking requires no external API key.

## Development and research checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests/unit -q
node --test frontend/src/graph/view.test.js
npm --prefix frontend run build
.venv\Scripts\python.exe scripts/smoke.py
.venv\Scripts\python.exe scripts/compare_baselines.py --repo pallets/flask --limit 25
.venv\Scripts\python.exe scripts/train_heterogeneous.py
```

Training uses complete eligible-file candidate pools, commit-disjoint validation selection and calibration queries, and separately retrained static/history/semantic ablations. The current experiment configuration remains a bounded development sample. Report its size and uncertainty rather than presenting it as a final cross-project accuracy claim.

After reviewing validation results, freeze all model/protocol choices before processing held-out labels:

```powershell
.venv\Scripts\python.exe scripts/research.py freeze
```

Only then restore the test partition and its required semantic snapshots and run `scripts/research.py evaluate`. Evaluation verifies frozen checksums and refuses to overwrite an existing final result. A model must be compared against the strongest validation-selected baseline on the same queries and candidates. A negative result must be retained honestly.

The FastAPI job service uses shared SQLite state, bounded subprocesses, cancellation, retry and refresh recovery. When a learned checkpoint is installed, submitted repositories also build exact-revision semantic indexes before the job completes. `scripts/smoke_public.py` exercises this workflow against a public repository.

Optional Gemini selects validated evidence citations after ranking; it never generates impact scores. Set `GEMINI_API_KEY` and `GEMINI_MODEL` in the server environment and opt in through the UI. The local explanation path needs no credentials. See `docs/operations.md` for provider boundaries and operational limits.

## Resume and audit the frozen study

```powershell
.venv\Scripts\python.exe scripts/verify_model.py
.venv\Scripts\python.exe scripts/candidate_coverage.py
.venv\Scripts\python.exe scripts/complete_study.py
.venv\Scripts\python.exe scripts/publish_study_report.py
```

Keep model weights, their freeze record and final results together. Existing results from a different freeze are rejected. `complete_study.py` appends stage logs and resumes completed artifact-verified work. `publish_study_report.py` verifies the measured query inputs and produces the model card and browser study summary. Rebuild the frontend after publishing that summary.

The additional channel-removal experiment is declared and trained before primary held-out scores are available with `scripts/remaining_ablations.py train`. After the primary query audit is published, `scripts/remaining_ablations.py evaluate` uses exactly those held-out tensors. It has its own freeze and never changes the primary checkpoint or baseline.

External checks use optional `requirements-external.txt`, a pinned SWE-bench Verified revision and pinned BugsInPy metadata. Reports describe **oracle-seeded file ranking**, not benchmark issue repair or reproduced test-suite accuracy. They exclude all twelve study projects and are separate from the primary held-out gate.

## Optional deployment and graph export

```powershell
.venv\Scripts\python.exe scripts/export_graph.py --repo pallets/flask
docker compose up --build
```

The exporter writes revision-aware CSVs, a Cypher import script and a resolution audit under `artifacts/exports/`. The local API continues to use JSON graphs. Docker/Compose binds the application to host localhost and mounts data/artifact volumes; Docker and a live Neo4j service were unavailable for execution checks on this machine.

The predictor currently ranks files. Class/function/test entities participate in the graph and their source spans can be inspected. Function-level supervised ranking and function/class seeds remain extensions; do not present file-level co-change results as function-level accuracy. The architecture review and exact acceptance boundary are in `docs/architecture.md` and `docs/implementation-status.md`.

## New observatory interface

The Command Deck opens the pinned repository as a real 3D Code Metropolis, with an accessible entity table. Search a function, inspect its exact source, then forecast its owning file. Impact Lab saves up to five seed files, keeps the original model outputs and combines ranks with explicitly labeled reciprocal rank fusion. Saved scenarios can be compared with linked camera controls. Top-K filters cached results. Unified diffs are preview-only and do not edit code.

Evolution Observatory selects real commits for parent-snapshot forecasts. Evidence & Explainability offers deterministic evidence or opt-in Groq/Gemini citation selection. Configure `GROQ_API_KEY` and `GROQ_MODEL` in the server process environment; Copy `.env.example` to `.env` for optional provider settings; explicit server environment variables take precedence. Credentials are never sent to the browser. Missing provider configuration falls back locally.

Connect Repository also accepts bounded ZIP source inspection. This does not synthesize Git history or claim learned archive forecasts. Flight Recorder uses persisted event sequences and SSE replay; timestamps identify observations, not reconstructed job phase timings.

See [observatory implementation and limitations](docs/observatory-implementation.md) for the exact requirements coverage and validation status.
