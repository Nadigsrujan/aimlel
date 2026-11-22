# Run Neural Cartographer yourself

## Daily start: this existing workspace

You do not need to reinstall packages, re-download repositories or train the model each time.

**Easiest:** open the project folder and double-click **START_NEURAL_CARTOGRAPHER.cmd**. It starts the local server and opens your default browser. If the application is already running, it opens the existing instance instead of creating a duplicate server.

**PowerShell:** open a terminal and run:

```powershell
Set-Location -LiteralPath 'C:\Users\raddo\Documents\aiml el 5th sem'
.\.venv\Scripts\python.exe .\scripts\run_local.py --open
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080). Keep the server terminal open while using the site. You can close the browser and reopen the same URL while the terminal is still running.

To stop a server you started, press **Ctrl+C in its terminal**. Wait for the shutdown message. Do not close unrelated Python processes in Task Manager.

The one server serves both the API and the already-built frontend. There is no need to run `npm run dev` for a normal demonstration. Starting the site does not restart training or ingestion.

## If port 8080 is busy

If this project's server is already running, the launcher reports its URL. To run a separate instance on another port:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_local.py --port 8081 --open
```

Use [http://127.0.0.1:8081](http://127.0.0.1:8081) for that instance. If an unrelated application occupies the requested port, choose another port rather than stopping unfamiliar processes.

The direct compatibility command also works:

```powershell
.\.venv\Scripts\python.exe .\scripts\start.py --port 8080
```

This direct command starts a foreground server; it does not check for an existing instance or automatically open a browser.

## After editing the frontend

Stop the running server first. Rebuild once, then start again:

```powershell
npm run build --prefix frontend
.\.venv\Scripts\python.exe .\scripts\run_local.py --open
```

Or use the launcher's rebuild option with the server stopped:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_local.py --rebuild --open
```

Reload the browser after a new build. Rebuilding the frontend does not change the trained model or its dataset.

## Useful local pages

| Page | Address |
|---|---|
| Website | http://127.0.0.1:8080 |
| Simple evaluator guide | http://127.0.0.1:8080/assets/evaluator-guide.html |
| These server instructions | http://127.0.0.1:8080/assets/run-server.html |
| API documentation | http://127.0.0.1:8080/docs |
| Health check | http://127.0.0.1:8080/api/v1/health |

Use the port you selected if it differs from 8080. The guides are also printable HTML files in `frontend/public/assets/` and Markdown documents in `docs/`.

## A reliable demonstration

1. Choose **flask** in the repository list.
2. Search `Scaffold::route`, select the real function, and inspect its source.
3. Click **Forecast selected file**. The model analyzes the function's owning file.
4. Inspect candidates in Impact Lab, then open Evidence, Test Constellation and Research Bench.
5. Keep explanations on **Local deterministic** for a fully local demo without provider credentials.

The public sample repositories, trained weights and prepared data are already present in this workspace. Existing prepared snapshots can be explored locally. Importing a new public repository, downloading absent encoder artifacts or using a hosted explanation provider requires network access.

## Optional Groq or Gemini explanations

The website and normal forecasts work without any hosted API key. If you want the optional hosted evidence selector:

1. Copy `.env.example` to `.env` if `.env` does not already exist. Keep existing credentials if it does.
2. Put your provider's key and a model available to your account into the appropriate fields: `GROQ_API_KEY` / `GROQ_MODEL`, or `GEMINI_API_KEY` / `GEMINI_MODEL`.
3. Restart the server. Explicit process environment values take precedence over `.env`.
4. In Evidence & Explainability, choose the provider and explicitly allow sending evidence paths/commit metadata.

Keys stay server-side; do not put them in frontend source or browser code. The provider request excludes source text. Missing credentials, unavailable models and rejected citations fall back to local evidence. A live hosted-provider success was not claimed during validation because no credentials were configured.

## If something does not work

| Symptom | What to do |
|---|---|
| Browser says connection refused | Start the server, keep its terminal open and check the correct port. |
| Workspace Python is missing | Use the first-time setup below; do not use the system Python 3.14 environment. |
| Frontend build missing | Run `npm ci --prefix frontend`, then `npm run build --prefix frontend`. |
| UI still looks old after edits | Rebuild and reload the browser. |
| Repository has no local data | Restore its pinned artifacts or connect a new public repository. A manifest alone is not source data. |
| 3D does not work on this device | Switch to the entity table; source, ranking and evidence remain usable. |
| A new import takes time | Check Repositories & Jobs / Flight Recorder. Imports build real source/history/vector artifacts, not a fake timed animation. |
| Provider is unavailable | Use the local explanation. No retraining is needed. |
| Frozen artifact mismatch | Restore the matching model/data bundle. Do not delete the freeze record or silently rerun training against held-out outcomes. |

Use this as a localhost application. It has no multi-user authentication layer and should not be exposed publicly without production hardening.

## First-time setup or environment repair

This section is for a fresh environment, not ordinary daily starting. The existing `.venv` and workspace-local `.runtime` are already configured. Recreating a virtual environment while a server is running can interrupt it.

Requirements: Node.js/npm, Git, `uv`, and a supported Python version. This Windows workspace uses Python 3.12; supported project versions are Python 3.10–3.12.

From the project folder, with existing project processes stopped:

```powershell
$env:UV_PYTHON_INSTALL_DIR = Join-Path (Get-Location).Path '.runtime\python'
uv python install 3.12
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-lock-windows-py312.txt
npm ci --prefix frontend
npm run build --prefix frontend
.\.venv\Scripts\python.exe .\scripts\run_local.py --open
```

A fresh source checkout does not include large raw repositories, vector caches, encoder weights or all local model artifacts. Follow the README's restore instructions or restore the matching prepared bundle/data. Keep `.runtime` and `.venv` together in the current workspace; if you move the folder, recreate the environment at the new location.

## Optional verification

These commands check the implementation; they are not needed on every start:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests/unit -q
node --test frontend/src/graph/view.test.js
.\.venv\Scripts\python.exe scripts/check_observatory.py
```

The observatory check intentionally creates a small saved validation scenario. The frozen study and its published scores already exist; do not overwrite or retune them for a presentation.
