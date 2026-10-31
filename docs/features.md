# Structural and historical evidence

The FastAPI analysis response enriches ranked files with directory proximity, structural hop count, past modified-file co-change count, static import paths and up to five supporting commit SHAs. Paths traverse exact resolved imports in either direction to a maximum of three hops; direction is not an impact prediction.

History is filtered by Git ancestry of the selected graph revision. For a historical target, that revision is its parent. Target and unreachable future commits cannot contribute history features. Bulk events above 50 eligible changes are excluded. Features are computed over the complete eligible-file pool before Top-K selection. Available baselines are directory, deterministic random, popularity, imports, co-change Jaccard and their equal-weight combination.

Pinned CodeBERT file embeddings use attention-mask mean pooling over the first 256 tokens. FAISS indexes include the repository revision, encoder configuration and checksum. `semantic-v1` requires an index for the exact queried revision; missing indexes produce an explicit error without downloading weights. Current Flask indexing is verified. Symbol embeddings, full candidate-channel evaluation, calibrated learned serving and complete provenance migration remain pending.

Encoder sources: [Microsoft model card](https://huggingface.co/microsoft/codebert-base), [pinned model revision metadata](https://huggingface.co/api/models/microsoft/codebert-base). Pretraining overlap with the evaluation corpus has not been audited.
