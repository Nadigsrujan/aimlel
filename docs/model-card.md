# Neural Cartographer model card

This checkpoint ranks related Python files for developer inspection. It does not prove causal impact or runtime test coverage.

## Data and protocol

The user-approved split is 7 training / 2 validation / 3 test projects. Training used 140 commit queries, 20 separate validation-selection queries and 20 calibration queries. The final study used 20 queries per held-out project (60 total), selected by the frozen policy.

Graphs and history use the target commit's parent; labels enter only the loss/evaluation. CodeBERT is pinned and uses the first 256 tokens per file. Two relation-aware GraphSAGE layers operate on file/class/function/test nodes; predictions and proxy labels remain file-level.

## Frozen held-out result

Strongest validation-selected baseline: `cochange-v1`. Ranking gate met: **False**. Model choices were not changed against test results.

| System | Macro Recall@5 | Macro NDCG@10 |
|---|---:|---:|
| cochange-v1 | 0.4576 | 0.4621 |
| heterogeneous | 0.3968 | 0.4072 |
| history-only | 0.4276 | 0.3668 |
| semantic-only | 0.0208 | 0.0185 |
| static-only | 0.0104 | 0.0126 |
| without-history | 0.0229 | 0.0248 |
| without-semantic | 0.4060 | 0.3629 |
| without-static | 0.3668 | 0.3616 |

Confidence intervals and per-project results are in `artifacts/reports/final-heldout.json`. Exact query/candidate/example and dataset checksums are in `final-study-audit.json`.

## Scores and limitations

Online sigmoid scores remain uncalibrated ranking values. A validation-fitted calibrator is evaluated separately on held-out data; it is not used to label online scores as reliable probabilities.

- 60 bounded held-out commit queries across three projects
- Modified-file co-change is a proxy for impact
- File-level predictions; shared file vectors for symbols
- No runtime test-coverage proof
- CodeBERT pretraining overlap is unaudited
- Static call/inheritance resolution is conservative and same-file lexical; dynamic dependencies remain unresolved.
- Static source relationships and co-change explanations are retrieved evidence, not a causal explanation of neural weights.
- The study does not establish global chronological separation across different repositories.

## Provenance

Model SHA256: `87277161a5cdb719c383fb6601568c26340b29d25800376dbcc6040c22050e37`

Final report SHA256: `0cbc1667fffaeedf51ee5942304dbe9eccab7b5674e3a8a7ce10c47251d3057e`

The primary freeze binds 606 source/configuration/model/data artifacts. Additional channel-removal models have a separate pre-test freeze; they never change the primary model or baseline. Reproduction commands and local resource limits are documented in `README.md` and `docs/operations.md`.


## Supplemental frozen comparator evaluation

supplemental evaluation of models/comparators frozen before primary test results; reporting performed afterward; no tuning or reselection. Primary baseline and success gate remain unchanged.

| Comparator | Macro Recall@5 | Macro NDCG@10 |
|---|---:|---:|
| cochange-v1 | 0.4576 | 0.4621 |
| combined-v1 | 0.3153 | 0.3279 |
| imports-v1 | 0.0979 | 0.0718 |
| path-distance-v1 | 0.0333 | 0.0282 |
| popularity-v1 | 0.0143 | 0.0314 |
| random-v1 | 0.0000 | 0.0050 |
| semantic-v1 | 0.0578 | 0.0473 |
| xgboost | 0.3485 | 0.3570 |