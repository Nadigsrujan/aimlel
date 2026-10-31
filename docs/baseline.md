# Baseline explorer

Run `.venv/bin/python scripts/serve.py` from the workspace, then open http://127.0.0.1:8080.
Select any ingested repository and Python seed file. Analyze returns deterministic directory-distance rankings and the extracted graph. All processing reads Git blobs without executing repository code. No API keys are needed.

To add a repository, paste a public `https://github.com/owner/repository` URL into the form and press **Add repository**. The server creates a bounded background ingestion job, pins the default branch revision, and adds the repository after processing. Private repositories, non-GitHub URLs, query-string URLs, and duplicate entries are rejected.

For historical reconstruction use a full single-parent target SHA. The graph is extracted from its parent; candidates never use the target diff. The selected seed must exist in that parent. The UI file selector lists the pinned snapshot, so historical paths can instead be supplied with the CLI:

`.venv/bin/python scripts/analyze.py --repo pallets/flask --seed examples/minitwit/minitwit.py --target-commit 4ec7d2a0d8eac4f915dc0d38a886cd57045bb0c4`

Current limitations: ranking uses directory proximity only. Import resolution, past co-change scoring, probability calibration, learned models, graphical node visualization and aggregate benchmark evaluation remain pending. This local standard-library HTTP adapter is a prototype, not the planned production API or job queue.
