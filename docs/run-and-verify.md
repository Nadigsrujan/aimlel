# Run and verify

Commands are for PowerShell on Windows, run from the project root with the workspace virtual environment (`.venv`, Python 3.12). On macOS or Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

## Start the app

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
.venv\Scripts\python.exe scripts/start.py
```

Open http://127.0.0.1:8080 (OpenAPI at `/docs`). The server serves both the built React interface and the API; add `--port 8090` for another port. After frontend edits, rebuild and restart. For live frontend reloading, run `npm --prefix frontend run dev` alongside the server and open the port Vite prints; it forwards `/api` to port 8080.

Optional Groq or Gemini evidence selection needs `GROQ_API_KEY`/`GROQ_MODEL` or `GEMINI_API_KEY`/`GEMINI_MODEL` in the server environment or in `.env` (copy `.env.example`). Without them the local explanation path is used. See `operations.md`.

## Checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend/tests/unit -q
.venv\Scripts\python.exe scripts/smoke.py
node --test frontend/src/graph/view.test.js
npm --prefix frontend run build
```

`smoke.py` needs Flask ingested (`scripts/ingest.py --clone --reuse --repo pallets/flask`).

## Frozen v1 study

```powershell
.venv\Scripts\python.exe scripts/verify_freeze_portable.py
.venv\Scripts\python.exe scripts/paired_analysis.py
```

The first reports every frozen file as an exact match, a line-ending-only difference (Git on Windows), missing local data, or a real change; only a real change fails. The second writes the paired significance analysis to `artifacts/reports/v1-paired-analysis.json`. Neither changes frozen artifacts.

## v2 study

The plan and checklist are in `tasks/research-v2-plan.md`; the protocol is `configs/experiments/protocol-v2.json`. Stages run in order and refuse to run out of order:

```powershell
.venv\Scripts\python.exe scripts/research_v2.py pilot
.venv\Scripts\python.exe scripts/research_v2.py develop
.venv\Scripts\python.exe scripts/research_v2.py freeze
.venv\Scripts\python.exe scripts/research_v2.py evaluate
```

`evaluate` clones the five fresh test projects, so it needs network access, and it runs once.

## Development experiments

```powershell
.venv\Scripts\python.exe scripts/compare_baselines.py --repo pallets/flask --limit 25
.venv\Scripts\python.exe scripts/embeddings.py --repo pallets/flask --revision d086db856be187255b8ec61ef409357393020f32
```

Add `--download` to the embeddings command only when the pinned CodeBERT encoder is not cached. Setup from a fresh Windows checkout (dependencies installed with pip inside `.venv`) was exercised on 2026-11-21, and the unit tests passed there. A GitHub Actions run has not yet been recorded.
