# Neural Cartographer: the evaluator's simple guide

## The big idea

Imagine a school with many rooms. Each room does a different job. Some rooms share supplies, some regularly work together, and some do similar work.

Now imagine changing something in one room. Before doing it, you would like a sensible list of other rooms to check.

**Neural Cartographer does that for Python software.** It reads a project, draws its structure, and ranks other files a developer may need to inspect when changing a selected file.

Its answer means **“look here next”**, not **“this will definitely break.”** It does not change the project or run its code.

## A thirty-second explanation

> Neural Cartographer turns a real Python repository into an interactive software map. A trained graph model combines source-code structure, earlier Git changes and code similarity to rank potentially related files. Every result can be inspected through source code, historical evidence and model provenance. The website also shows how the model was evaluated, including results where a simpler baseline performed better.

## A five-minute evaluator walkthrough

1. Open the website and select **flask** in the repository list. The repository is a real public Python project, pinned to a specific commit.
2. In **Code Metropolis**, search for `Scaffold::route`. Choose the result in `src/flask/sansio/scaffold.py`. Inspect the real function at lines 344–373 in this pinned snapshot. A later repository version may have different lines.
3. Click **Forecast selected file**. The function chooses its owning file as the prediction seed. The model predicts files, not individual function failures.
4. In **Impact Lab**, select a ranked file. Compare the score, static import path, previous co-change commits and source code. Move Top K to change how many cached results are shown.
5. Open **Evidence & Explainability**. Choose a ranked candidate and use the local explanation. Click a citation to check the supporting evidence. A hosted provider is optional.
6. Open **Test Constellation**. Explain that these are tests to inspect, with known static associations where available. They were not executed and the diagram is not measured coverage.
7. Open **Research Bench**. Show the genuine held-out comparison and the “Ranking gate not met” result. The system reports evidence honestly instead of hiding a negative outcome.

For a comparison demo, save two forecasts using the same seed and snapshot, choose a different ranking method for the second, then compare the saved runs. Rank-flow lines show actual saved rank changes. Twin city cameras move together.

## What each screen means

| Screen | Simple explanation | What to try |
|---|---|---|
| Command Deck | The project's control room. | Select a repository, see its real source map and search a component. |
| Code Metropolis | A city made from the actual source files. | Click a building or search a function; inspect its exact committed source. |
| Impact Lab | A rehearsal desk for a proposed change. | Save up to five seed files, forecast them, filter cached results and export the run. |
| Evolution Observatory | A time machine through real Git commits. | Select a commit to predict from its parent; reveal observed changes only after the saved forecast. |
| Evidence & Explainability | The proof behind a recommendation. | Inspect structure/history/similarity and request a citation-bound explanation. |
| Test Constellation | A map of test files worth checking. | Select a recommended test and inspect its source. Only real static links receive tethers. |
| Research Bench / Model Lab | The project's report card. | Inspect real training curves, baselines, ablations, confidence intervals and held-out results. |
| Repositories & Jobs | The import desk and processing history. | Connect a public GitHub Python project; inspect progress, cancel or retry a job. |
| Settings & Provenance | The label on each piece of evidence. | Check the source commit, prediction scope and provider/privacy boundaries. |
| Impact explorer | The preserved conventional analysis interface. | Use the existing 2D graph, evidence filters, source viewer and rankers. |

### Other visual instruments

- **Code MRI:** a cutaway of real file/class/function hierarchy. Its layer slider follows actual containment depth. Where conservatively resolved, CALLS and INHERITS links point back to source lines.
- **Risk Topography:** modules become islands. Height represents a selected aggregate: mean score, sum of scores or ranked-file count. The table gives the formula's actual values and denominators. Height is not a failure probability.
- **Commit DNA / Temporal Rift:** alternative shapes for real commit history. Their dimensions come from changed Python lines, changed-file counts and observed file pairs. They are visual encodings, not a physical simulation of software.
- **Flight Recorder:** persisted server events and observed job states. It can replay event IDs after reconnecting. Observation timestamps are not invented original stage durations.
- **Ranked reveal:** plays back already-computed ranked findings. It does not simulate an actual execution trace or invent dependencies.

## Reading the city

A building represents a real source file. A district groups files by their actual directory. Height uses a logarithmic source extent derived from parsed symbols; a displayed “at least” line count is a lower bound, not a claim that every line was counted for the building.

Blue buildings are source files. Green identifies test-path files. Amber marks displayed ranked candidates. The seed is bright white; a selected neighbor uses cyan. Follow the legend in each view. Small windows correspond to real parsed symbols, with visual limits to keep large projects usable.

City lines show resolved imports touching the selection. A prediction can exist without a connecting line: historical or semantic evidence may recommend a file even when no static import path is known.

The entity table provides a keyboard-accessible alternative. Drag to orbit, scroll to zoom, press **F** to focus, **1** for 3D, **2** for the table, **Esc** to clear selection and **/** to search.

## The three detectives and the referee

The model combines three kinds of clues:

1. **The blueprint detective — static structure.** The parser reads imports, definitions, containment and conservatively resolvable calls/inheritance. It does not execute the repository. Dynamic Python relationships can remain unresolved.
2. **The diary detective — Git history.** The system asks which files changed together in earlier commits, how often files changed and how recently. Historical predictions use evidence available at the selected source snapshot, not later changes.
3. **The wording detective — semantic similarity.** A pinned CodeBERT encoder converts source text into numeric vectors. Similar vectors are a clue that files do related work. Similarity does not establish a dependency. Here, file vectors cover the first 256 tokens and are shared by contained symbols.

**The referee is the learned ranking model.** A relation-aware GraphSAGE network passes information over typed graph connections, then an MLP scores seed/candidate pairs. The system also includes frozen XGBoost and simpler comparison methods, such as historical co-change.

The model produces an ordered inspection list. A score such as 0.95 is **not** a validated 95% chance of failure.

## What the language model does

Groq or Gemini does not invent the impacted-file list and does not set its scores. Ranking happens first.

The server creates trusted evidence cards with IDs. An optional provider may select existing IDs. The website displays the server's own evidence statements, checks citations and rejects invented IDs or arbitrary provider prose.

Local deterministic explanations need no key. Hosted explanations require server credentials, a configured model and an explicit checkbox allowing evidence paths/commit metadata to be sent. Source text is excluded from that provider request. Missing credentials or invalid responses fall back locally.

## How a forecast travels through the system

**Choose source → identify the owning file → read its exact snapshot → build structural/history/semantic features → score the file candidates → retrieve evidence → save the run → display the results.**

A multi-seed scenario retains each original result and combines cached top-100 ranks using reciprocal rank fusion. That aggregate is an inspection ordering, not a new calibrated neural probability. The per-seed selector controls which original result the city, evidence and explanation show.

A pasted unified diff selects known changed files as seeds. It is a preview; the application does not apply the patch or claim to have analyzed a new executable version of the code.

## Why a commit ID matters

A Git commit is like a dated photograph of a project. Its SHA identifies the exact photograph. Source line numbers, graph nodes and evidence must refer to that same photograph.

A model checksum is a fingerprint of the trained weights. A saved run ties its predictions to source/model provenance. These fingerprints make the demo reproducible and help detect stale or mismatched artifacts.

For time travel, the target commit's **parent** is the before-change photograph. The later modified-file labels stay hidden in the normal retrospective view until the forecast is saved and the evaluator explicitly reveals them. The full historical map loads separately; a saved graph slice remains usable while loading.

## What the evaluation really says

The approved research split is **7 training repositories, 2 validation repositories and 3 held-out repositories**. The held-out projects are SymPy, scikit-learn and Django. Five additional imported projects are available as demos, giving 17 entries in the local catalog.

Training used 140 historical change queries. Checkpoint selection used 20 validation queries; calibration used 20 separate queries. The frozen final test used 20 queries per held-out project, or 60 in total. This is a bounded experiment, not evaluation of every change in all repositories.

| Frozen system | Repository-macro Recall@5 | Repository-macro NDCG@10 |
|---|---:|---:|
| Fusion GraphSAGE | 39.7% | 0.407 |
| Validation-selected historical co-change baseline | 45.8% | 0.462 |
| Frozen XGBoost, supplemental comparison | 34.9% | 0.357 |

**The primary success gate was not met.** The learned fusion model beat XGBoost in this sample but did not beat the selected co-change baseline. It was not retrained or tuned against those test outcomes.

Recall@5 asks: “Of the other files that actually changed, what share appeared in the first five suggestions?” The reported figure averages queries within repositories, then repositories. It is not ordinary classification accuracy or a probability for a particular file.

NDCG@10 rewards putting genuinely changed files near the top of the first ten suggestions. Confidence intervals show uncertainty; with a small benchmark, the ranges can be wide.

An **ablation** removes a clue channel to measure its contribution. Results do not prove every channel improved every metric. The UI preserves negative findings. Calibration diagnostics are reported separately; online scores remain uncalibrated ranking values.

Exploratory SWE-bench and BugsInPy cases use a known changed file as the seed. They measure file ranking, not autonomous issue repair or successful execution of benchmark tests.

## What is finished, and what is deliberately not claimed

The local application supports real public-repository ingestion, persisted jobs, graph/source exploration, learned and baseline forecasts, saved scenarios, historical analysis, evidence, research reports, export and the visual instruments described above.

Predictions remain **file-level**. Functions/classes and test-named symbols are inspectable, but the project does not claim separately validated function-level impact accuracy. A static association is not runtime coverage, and an observed co-change is not proof of causation.

ZIP uploads are parsed safely without extraction or execution. They provide real source inspection and an explicitly **untrained static/directory baseline**. They do not manufacture Git history or silently use the Git/CodeBERT trained pipeline.

The service is designed for this local workstation. Hosted multi-user deployment, collaboration, a GitHub App and sandboxed test execution are future production extensions. Docker configuration exists, but a Docker build was not executed on this machine.

## Questions an evaluator may ask

**What is the practical output?** A prioritized list of files and tests for a developer to inspect, with evidence and an exportable plan.

**Is this just an LLM guessing?** No. A frozen model or explicitly labeled baseline ranks files. The optional LLM only selects allowed evidence citations afterward.

**Are the buildings and metrics real?** Buildings come from parsed source. Git shapes come from actual commits. Scores and research tables come from saved inference/evaluation artifacts. Missing evidence is shown as missing.

**What is the contribution?** An integrated, traceable system combining code structure, evolution and semantic clues with graph learning and interactive inspection. It does not claim to have invented GraphSAGE, embeddings or 3D graph visualization.

**Why show a negative result?** Because a credible research project must distinguish a working implementation from proof of predictive superiority. The result identifies where the current approach needs further study under a new, predeclared evaluation protocol.

## Tiny glossary

| Word | Plain meaning |
|---|---|
| Repository | The project's collection of source files and Git history. |
| Seed | The file where a hypothetical change starts. |
| Node / edge | A component / a recorded relationship between components. |
| Snapshot / SHA | One exact version / its Git identifier. |
| Embedding | A numeric representation used to compare source similarity. |
| GraphSAGE | A neural network that learns by gathering information from graph neighbors. |
| MLP | The small scoring network that reads a seed/candidate pair. |
| Top K | How many highest-ranked suggestions to display. |
| Baseline | A simpler comparison method. |
| Co-change | Files being modified in the same historical commit. |
| Provenance | Where a result came from and which versions produced it. |
| Calibration | Checking whether numeric scores can support probability interpretations. |

## Start and stop the website

For daily use in this already-configured folder, double-click **START_NEURAL_CARTOGRAPHER.cmd**, or follow [the server instructions](RUN_SERVER.md).

The website is at [http://127.0.0.1:8080](http://127.0.0.1:8080). Keep its terminal open. Press **Ctrl+C** in that terminal to stop. Starting the website does not retrain the model.
