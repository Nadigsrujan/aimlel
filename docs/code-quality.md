# Code quality and plan alignment

Scope: application scripts and tests. Downloaded repositories and generated datasets are inputs, not application source; do not format or refactor them.

Quality gate: `.venv/bin/python -m unittest discover -s backend/tests/unit -v`.

Rules: validate external input types and sizes before use; never execute submitted code; keep labels outside scoring inputs; reconstruct parent snapshots for historical evaluation; identify heuristic scores explicitly; do not expose held-out projects before final evaluation; preserve unresolved parsing/import evidence.

Review findings addressed: duplicate manifest reads, malformed JSON payload crashes, unbounded concurrent ingestion, active duplicate ingestion, unlimited retained job records, missing subprocess error handling, premature held-out catalog exposure, and stale checklist approval text.

Additional fixes: current-snapshot analysis reuses ingested graph artifacts; ancestor validation uses Git's ancestry check instead of loading all commit IDs; job state is persisted atomically and interrupted jobs become failed on restart; timeout kills the ingestion process group; Top-K is validated in the analysis function.

Remaining gaps: embedded UI requires modularization and browser coverage; historical analysis still launches per-file Git processes; repository download size is uncapped; structured contracts and the planned FastAPI/React architecture are pending. Job recovery records failure rather than resuming work. Process groups are POSIX-specific. Unit tests alone do not certify end-to-end upload behavior. Full project compliance and performance optimization are not yet achieved.
