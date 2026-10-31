# Neural Cartographer

Neural Cartographer includes a pinned Python repository ingestion pipeline, historical snapshot reconstruction, a deterministic impact baseline, a FastAPI service and a React graph explorer. A structural GraphSAGE pilot can be trained locally. The full heterogeneous model, semantic features and final research evaluation remain in progress; see `tasks/todo.md`.

## Run the application

```sh
.venv/bin/python -m pip install -r requirements-api.txt
.venv/bin/python -m uvicorn api:app --app-dir scripts --host 127.0.0.1 --port 8080
```

In a second terminal:

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. API documentation is at http://127.0.0.1:8080/docs. The UI supports public GitHub URL submission, indexing status, repository/seed selection, Top-K rankings, graph navigation and source evidence. Current scores measure directory proximity. Python analysis is supported; other-language repositories can contain no analyzable entities.

## Reproduce development experiments

```sh
.venv/bin/python scripts/evaluate.py --repo pallets/flask --limit 25
.venv/bin/python -m pip install -r requirements-ml.txt
.venv/bin/python scripts/train_pilot.py --commits 30 --epochs 10
```

The pilot uses only Flask training data with disjoint chronological commit groups. It does not establish cross-project accuracy or satisfy the final research success gate.

## Reproduce ingestion

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-ingest.txt
.venv/bin/python scripts/ingest.py --clone --workers 2
.venv/bin/python scripts/verify_dataset.py
PYTHONPYCACHEPREFIX=/tmp/neural-cartographer-pycache .venv/bin/python -m unittest discover -s backend/tests/unit -v
```

For a single catalog repository, append `--repo owner/name`. To process a partition, use `--split train`, `--split validation` or `--split test`. To process another public GitHub project, use `--public-url https://github.com/owner/repo --clone`; submitted repositories receive the `submitted` split. Existing clones are reused and successful manifests pin the same revision on reruns. Full clones, generated graph/history/query artifacts and model binaries are local data excluded by `.gitignore`; small manifests and reports record their provenance. See `docs/ingestion.md` for output contracts and limitations.
