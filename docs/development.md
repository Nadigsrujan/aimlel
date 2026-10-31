# Development commands

Install backend: `.venv/bin/python -m pip install -r requirements-api.txt`.

Start API from project root: `.venv/bin/python -m uvicorn api:app --app-dir scripts --host 127.0.0.1 --port 8080`.

Start React UI in a second terminal: `cd frontend && npm ci && npm run dev`.
Open http://127.0.0.1:5173. OpenAPI documentation: http://127.0.0.1:8080/docs.

Tests: `.venv/bin/python -m unittest discover -s backend/tests/unit -v`.
Production frontend build: `cd frontend && npm run build`.
Development baseline evaluation: `.venv/bin/python scripts/evaluate.py --repo pallets/flask --limit 25`.

The nine training/validation catalog entries are visible during development. The three held-out projects remain sealed. The UI graph labels directory-distance relationships explicitly; they are not inferred calls or confirmed dependencies.
