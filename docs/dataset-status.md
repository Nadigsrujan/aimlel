# Dataset ingestion status

Completed on 30 October 2026 for all 12 planned public repositories. The verified local dataset contains 190,509 non-merge commits, 243,538 file-level co-change queries and 191,911 current-snapshot entities. Raw Git repositories occupy about 1.5 GB and generated artifacts about 263 MB.

| Split | Repositories | Commits | Queries | Current entities |
|---|---:|---:|---:|---:|
| Train | 7 | 50,463 | 57,541 | 38,366 |
| Validation | 2 | 23,531 | 37,141 | 50,054 |
| Test | 3 | 116,515 | 148,856 | 103,491 |
| Total | 12 | 190,509 | 243,538 | 191,911 |

The integrity gate verifies every manifest revision and artifact checksum, checks split consistency, confirms that each query points to the event's parent revision, and confirms that each seed and positive belongs to the same modified-file set. All 12 repositories pass. Seven ingestion tests cover modern Python fallback parsing, nested entities, relative imports, excluded paths, syntax-error auditing, public URL validation and parent-revision labels.

Three current files remain explicitly recorded as parse failures: two in SQLAlchemy and one in Django. Their file nodes remain present, but symbol-level entities from those files are unavailable. No parse failure is hidden.

This phase supplies current structural graphs, full Git event histories and file-level co-change labels. It does not yet supply resolved calls/imports, rename-aware identities, historical graph snapshots, function-level diff labels, semantic embeddings, candidates/negatives, trained models, Neo4j loading, API jobs or the React interface. Those remain unchecked in `tasks/todo.md`; the existing outputs set `features_materialized=false` to prevent accidental training on latest-snapshot features for past events.

Reproduce with the commands in `README.md`. The authoritative machine-readable audit is `artifacts/reports/verification.json`; per-repository summaries and checksums live under `data/processed/<owner>__<repo>/<sha>/summary.json`.
