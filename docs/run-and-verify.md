# Run and verify

From the project root, using the existing virtual environment:

```sh
.venv/bin/python scripts/start.py
```

Open http://127.0.0.1:8080. The server serves both the built React interface and API. For a different port, add `--port 8090`. After frontend edits, rebuild with `cd frontend && npm run build`, then restart the server.

Checks:

```sh
.venv/bin/python -m unittest discover -s backend/tests/unit -v
.venv/bin/python scripts/smoke.py
cd frontend
node --test src/graph/view.test.js
npm run build
```

For a new environment, install `requirements-dev.txt` and run `npm ci` inside `frontend` before building. An editable Python installation is available with `pip install -e '.[ml,test]'`; retain the workspace's `configs`, `data`, `artifacts` and built `frontend` directories. Set `NEURAL_CARTOGRAPHER_HOME` if the workspace is elsewhere. A clean-machine install has not yet been verified.

Development experiments:

```sh
.venv/bin/python scripts/compare_baselines.py --repo pallets/flask --limit 25
.venv/bin/python scripts/train_heterogeneous.py
```

The training configuration is `configs/experiments/heterogeneous.json`. This is a bounded structural/history development experiment. It does not freeze a final model or unlock held-out projects. Calibration-fit metrics are not held-out calibration estimates.

Semantic indexes are built explicitly for each exact revision:

```sh
.venv/bin/python scripts/embeddings.py --repo pallets/flask --revision d086db856be187255b8ec61ef409357393020f32
```

Add `--download` only when the pinned encoder is not cached. No API key is required. Gemini and Neo4j are not integrated yet.
