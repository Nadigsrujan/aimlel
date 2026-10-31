# Artifact contracts, version 1

The current file-graph pipeline uses repository owner/name and full Git commit SHA as its immutable snapshot key. `contracts.identity` hashes an unambiguous JSON tuple of repository, revision, path, qualified symbol name and kind. Snapshot identity changes across revisions by design; rename continuity is a separate explicit old/new alias, never an assumption based on matching names. Existing ingestion IDs containing line numbers remain legacy local graph identifiers and are not stable cross-revision identities.

`contracts.artifact_key` includes parser version, feature version and history cutoff. Any future embedding cache must additionally include encoder revision. A feature cache cannot substitute the current graph for a historical parent snapshot.

Graphs contain nodes with id/kind/path and optional start/end spans. Edges contain source/target/relation and optional resolution and line evidence. Static import resolution preserves unresolved imports; it never assumes dynamic module execution.

Historical queries contain repo, split, commit, graph_revision, seed, positives and features_materialized. `graph_revision` must equal the single parent of commit. Labels are passed only to evaluation/training loss, never to inference or feature construction. Modified-file positives are proxy co-change labels.

Analysis response version 1 contains schema_version, repo, graph_revision, target_commit, seed, ranker, score_is_probability, candidates, graph and parse_failures. API requests are validated Pydantic models and discoverable in `/openapi.json`. Scores are not probabilities unless calibration has been independently validated.

Function span mapping currently maps overlapping parent-side spans and falls back to files for zero-length or unresolvable spans. Automated rename aliases and reliable function identity coverage remain outstanding; do not use this helper to claim completed function-level labels.
