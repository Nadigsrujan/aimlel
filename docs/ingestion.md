# Dataset ingestion

Create the environment with `python3 -m venv .venv` and `.venv/bin/pip install -r requirements-ingest.txt`. Run `.venv/bin/python scripts/ingest.py --clone --workers 3` from the project root. This processes the 12 repositories in `configs/repositories.json`. Use `--repo owner/name` to retry a single catalog entry or `--split train` to process one partition. Use `--public-url https://github.com/owner/repo --clone` to ingest another public GitHub repository into the `submitted` partition. Existing clones are reused without fetching a changing remote HEAD; successful manifests pin a revision. `--single-branch` retains the full default-branch history.

Outputs per repository/revision in `data/processed/`:

- `graph.json`: current Python file, class, function and test entities with containment and unresolved import statements.
- `events.jsonl`: non-merge ancestor commit metadata, parent SHAs, and Python file change statuses. Roots are excluded because they have no pre-change snapshot.
- `queries.jsonl`: modified-file co-change seeds and positives with the parent revision. No negatives or learned features are included. Additions/deletions are in events but excluded from labels because their identity needs additional handling.
- `summary.json`: counts, parse errors, large-file exclusions, license paths/blob IDs and SHA256 checksums.

`artifacts/reports/ingestion.json` records the latest run's successes and failures. Data files and clones are ignored by Git; small manifests are retained. Repository code is never imported or executed. Git history is full, not shallow. Files above 2MB, symlinks, generated/vendor paths are excluded from the current graph. A bulk event above 50 changed Python paths is retained in events but excluded from query labels. The current AST parser uses Tree-sitter when the host Python 3.9 grammar cannot parse newer syntax; residual parse errors are explicitly listed in each summary.

This first processing stage does not claim that co-change is causal impact. It does not resolve dynamic calls/imports, track rename identities, materialize historical graphs/features, create semantic embeddings, train models or expose a web upload endpoint. Each query explicitly sets `features_materialized=false`, preventing consumers from mistaking current graph data for pre-change features. Historical snapshot materialization must use `graph_revision`, never the repository's latest graph. Full acceptance of T04/T07/T09 requires those later components.

Verification: `PYTHONPYCACHEPREFIX=/tmp/neural-cartographer-pycache .venv/bin/python -m unittest discover -s backend/tests/unit -v`, then `.venv/bin/python scripts/verify_dataset.py`.
