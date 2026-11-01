# NEURAL CARTOGRAPHER — 12 UNCONVENTIONAL FRONTEND VISUALIZATION PROMPTS
## Copy/paste these individually into your AI coding agent after the master architecture is in place

**Instructions:** These are *real implementation prompts*, not requests to generate pictures. Each describes interactive frontend components, grounded data mappings, animations and definition of done. Their imaginative metaphors must not override typed graph, provenance and score integrity. Reuse the contracts, UI design tokens and shared stores from `NEURAL_CARTOGRAPHER_MASTER_CODING_AGENT_PROMPT.md`.

---

## PROMPT 01 — CODE METROPOLIS: LIVING SOFTWARE CITY (flagship)

```text
Act as a senior creative WebGL engineer and software-visualization researcher. Implement a high-end, fully interactive "Code Metropolis" as the main Neural Cartographer view using React Three Fiber, Three.js, Drei, TypeScript and real GraphSlice API data.

Aesthetic: the interior of a futuristic cartography observatory, NOT a Cyberpunk video game. A black-slate infinite floor, carefully lit architectural districts, luminous seams and legible floating package labels. Buildings represent actual FILES; districts represent PACKAGES/MODULES; floor/window patterns encode aggregated FUNCTIONS; rooftop rings mark CLASSES; satellite outposts represent mapped TESTS. Deterministic file positions and labels persist across reloads and adjacent SHA snapshots. Scale height by normalized/log LOC (configurable to function count); never pretend height is risk if the legend says LOC.

Build interaction modes: architecture, predicted impact, historical churn, test mapping, semantic neighbors, co-change. Each mode remaps materials and legend from actual typed fields; do not generate random values. Click selects real node ID, hover shows path/type/metric, double-click drills into the file floor plan, right-click or action bar offers inspect source, trace callers, simulate change, view history and test links. Fast fuzzy search flies the camera to a node. Selection synchronizes global Zustand store, Impact Lab ranked table, Evidence Lens, code editor and 2D fallback.

In impact mode, animate selection as a single white-cyan signal ring. When prediction API returns, highlight model-ranked targets in warm gradients with capped emissive halos, label rank and score in a readable HTML overlay, and display only retrieved real evidence paths. Create a subtle edge-following pulse for structural candidates and a separate beacon for unconnected semantic/historical candidates—never invent missing edges. Add visible 'model/version/SHA/provenance' and 'predictive visualization, not runtime execution' indicators.

Engineering: shared geometries, InstancedMesh for thousands of file blocks, group by module, automatic LOD, pointer raycasting with instance-to-ID map, stable seeded district placement, camera bookmarks, adaptive DPR, WebGL loss handling, reduced motion and accessible 2D/table fallback. Prefer ambient lighting over aggressive bloom; performant to use on an evaluator's laptop. Build per-node unit mapping tests and Playwright click-through test. Finish with actual running UI + screenshots + verified endpoints, not a mocked image.
```

**Evaluator reveal:** select one function and watch its entire real module context become inspectable architecture, then execute a real prediction without leaving the city.

---

## PROMPT 02 — IMPACT SHOCKWAVE: PREDICTION AS A CINEMATIC FORECAST

```text
Design and implement an interactive "Impact Shockwave" layer that turns a finished ranked PredictionRun into an elegant 3D visualization while remaining scientifically truthful. Use the selected seed as an origin beacon. Starting only after backend prediction.ready event, reveal ranked candidate nodes as ordered light-up events. Structural path candidates receive restrained pulses traveling along edges that genuinely occur in the evidence graph. Candidates discovered only by Git co-change or CodeBERT similarity appear as distant, independent activated beacons with dashed purple/violet or soft cyan glyphs rather than fabricated physical connecting lines.

Add a small sequencer/filmstrip with Play, Pause, Step, Scrub, Reset, Show Top 5/10/20 and path evidence filters. A scrub position reveals exactly the subset of ranked findings at that sequence stage, not a changing model prediction. Color encode calibrated probability only if the actual API supplies calibratedProbability; otherwise label hue 'relative model score' with 0..1 gradient. Allow click on a pulse event to freeze, focus target and open a split explanation drawer showing score, typed path, Git evidence and relevant source lines.

Design atmosphere like a scientific visualization at a particle accelerator: elegant attenuation, visible depth and typography, no meaningless explosions. Include a 'Representation of ranked results—not observed runtime propagation' microcaption. Apply responsive layout: central wide 3D viewport, bottom event sequencer, right ranked evidence ledger. Support reduced motion without losing information. The event sequence and each target's ID/score must be reproducible from persisted prediction run; add a test that compares animated selected IDs to ranked API targets.
```

**Evaluator reveal:** a click on a distant "surprising" target proves why the model considered it through a real co-change trail.

---

## PROMPT 03 — PARALLEL UNIVERSES: SIDE-BY-SIDE WHAT-IF DIGITAL TWIN

```text
Implement a dual-viewport "Parallel Universes" simulator comparing A: frozen selected graph snapshot and B: predictive impact overlay for a selected proposed edit, different seed selection, or optional actual Git diff. The two 3D scenes must share an aligned deterministic geometry and synchronized or independently togglable camera movement. Do not mutate the right-hand source graph in a hypothetical scenario—only overlay predicted impact on current graph unless there is actual supplied new code/commit to parse.

Create an elegant central optical split seam and thin comparison ledger: baseline SHA, scenario seed(s), selected model, candidate count, Top-K overlap, rank changes, newly highlighted targets, unique tests and evidence coverage. Clicking a file in either viewport highlights the same logical entity on both. Provide 'Linked cameras', 'Difference only', 'Same scoring model', 'Compare scenarios', 'Compare model variants', 'Overlay mode' and 'Export comparison'. Clicking model variants must call exact persisted run IDs and never silently rescore client-side.

Add a mathematically grounded split-heat overlay to show which modules change risk position in the ranking. Use actual numeric delta with legend and null/unknown states, not invented breakage probabilities. Make the entire page a compelling mechanical instrument—matte graphite lens frames, minimal neon, small explanatory labels. Build keyboard support and fallback to side-by-side 2D graphs/tables on low GPU devices. Acceptance test: both sides display identical node geometry on same snapshot, and score differences exactly match backend results.
```

**Evaluator reveal:** compare GraphSAGE vs history-only predictions on the same seed, with rank movers made visually obvious.

---

## PROMPT 04 — TEMPORAL RIFT: WALK THROUGH GIT HISTORY AS ARCHITECTURAL STRATA

```text
Build "Temporal Rift", an optional 3D history view where time is a physical corridor of stacked, translucent repository snapshots. Commit groups become slices along a long receding Z axis. Dense change epochs have thicker highlighted layers; each layer links to a real pinned SHA with timestamp, changed files, extracted functions and available snapshot status. Use a synchronized conventional timeline along the bottom so the experience remains understandable.

The view reads a history/snapshot API, not generated random commits. Clicking a slice freezes that exact graph; if uncached, display job progress instead of showing a fabricated reconstructed snapshot. Animate matched logical file buildings from previous to next using stable IDs, with newly added/removed nodes materializing/dissolving. Historical co-change trails can connect two actual components only when a pre-cutoff observation exists. Keep a visible control 'History known through this cutoff'.

Implement Historical Replay mode: pick c_t, load G_(t-1), choose a seed from observed change set, score only with pre-t features, then optionally reveal actual c_t positives as separate green/purple 'ground truth revealed after prediction' marks. This becomes the evaluator's most persuasive research demonstration. Include alternative flat 2D timeline and Data Quality filter. Do not leak future commit details into rank results or model input. Add a test explicitly preventing future cochanges appearing before reveal.
```

**Evaluator reveal:** an earlier prediction is made before the future change set is disclosed.

---

## PROMPT 05 — FIBER-OPTIC DEPENDENCY PATHS: READABLE RELATIONSHIP TRACING

```text
Implement a visual debugger for typed code dependency paths. When a user clicks 'Why here?', show one to five shortest/relevant evidence paths from seed to candidate as 3D luminous fiber-optic splines, with arrows indicating actual direction and small edge-type tags CALLS, IMPORTS, TESTS, CONTAINS, etc. Differentiate dependency direction from the direction of the visual signal; for reverse dependency search, label it 'caller depends on changed target'.

The center stage isolates selected entities, not a tangled whole-repository hairball. Render path cards in an adjacent scrollable column: exact ordered sequence of node names, typed relations, hop count, confidence/resolution, relevant source file/line. Hovering an edge highlights its original AST evidence; clicking a node opens code in Monaco at exact committed line. Co-change arcs use dashed violet and explicitly display historical commits, not a source-call edge. Unresolved edges are dotted with uncertainty label; if no path exists, say none found and show alternative historical/semantic evidence rather than drawing a phantom path.

Include 'show caller direction', 'show callee direction', 'show alternative paths', 'max hops', 'isolate module' and 'copy path as text'. Path details must come from evidence service with the same ID used by Groq citation validator. Optimize batched line geometry and label occlusion, provide keyboard-focusable path list and exportable SVG/JSON path summary. Use a sober sci-fi engineering look: optic glass and dark instruments, controlled emissive glow.
```

**Evaluator reveal:** click a connection and jump directly to the exact CALLS statement which produced that graph edge.

---

## PROMPT 06 — RISK TOPOGRAPHY: THE BLAST-RADIUS TERRAIN

```text
Create an alternative metric visualization called "Risk Topography". Turn packages/modules into a continuous-ish 3D terrain of discrete, raised islands using the actual list of impacted nodes. Each island's height = normalized aggregate model score or high-ranked impacted count (clearly selectable), island surface area = module component count, and contour rings = threshold bands. Uncertainty/missing embeddings are rendered as hatched neutral ground rather than silently zero risk.

Use custom geometry with smooth normals, subtle contour strokes and professional scientific gradient. Users can rotate/zoom, change aggregate metric, choose Top-K and score threshold, hover an island to inspect numerator/denominator, and click to filter Impact Lab and Code Metropolis to its module. The legend must be quantitative, distinguish sum from mean and show the exact score/model version. Have a sidecard listing 'largest potential inspection burden', 'high centrality modules', 'modules with few mapped tests' as metrics derived from data.

No invented prediction diffusion or fluid physics; the terrain is a geographic encoding of static scores at analysis time. Add 2D heatmap fallback and snapshot compare slider. Build a unit test that sampled island heights match module aggregation formula from API targets.
```

**Evaluator reveal:** the viewer immediately sees which architectural region has the most concentrated predicted inspection burden.

---

## PROMPT 07 — TEST CONSTELLATION: A NIGHT SKY OF VERIFIABLE TEST RELATIONSHIPS

```text
Design a 3D 'Test Constellation' that uses tests as orbiting satellites around real source-module clusters. Visualize *three separate signals*: explicit AST/static TESTS associations (solid green lines), heuristic name/import associations (dashed lines with heuristic tag), and actual executed test outcomes (strong green/red status only when a real sandbox runner returned results). Never falsely claim measured code coverage from test naming conventions.

Connect to `/predictions/{id}/tests`; show source score, test relationship evidence, group, prior runtime if known, and sortable priority queue. Clicking a test reveals function/path, associated impacted nodes and reasons; clicking a source node highlights tests. Add filters: directly mapped, inferred, executed, no associated test, test score threshold. Allow copy/export of exact test invocation paths. Optional launch test run only if a safe isolated execution engine exists and only with explicit user action; otherwise disable visibly and explain why.

Creative style: minimalist astronomical star chart floating above a thin instrument panel, orbit arcs with limited motion, not an exploding sphere of particles. Labels must remain legible. Test data must correspond to actual parsed test functions/paths, with a synchronized plain table for accessibility. Show 'uncovered mapped area' only as 'no known mapped test', never as proof of zero coverage.
```

**Evaluator reveal:** a predicted source change leads directly to a prioritized, evidence-linked list of tests to inspect.

---

## PROMPT 08 — COMMIT DNA: SOFTWARE EVOLUTION AS A DOUBLE HELIX

```text
Build a novel optional 'Commit DNA' visualization, a two-strand helix whose left strand represents chronological code structural change volume and right strand represents historical observed co-change connectivity. Each time step is an actual commit or time bucket; strand radius/thickness is data-derived and labeled. Cross-bridges represent co-changes observed in a real commit (aggregated at module level), with no invented causal arrows. Clicking a bridge opens exact commit SHA, changed files, mapped symbols and allowed evidence. Keep the paired flat timeline below for comprehension and keyboard navigation.

Allow playback through history with stable time buckets, filter by module, highlight a selected function's past co-change partners and compare two time windows. When the helix becomes too dense, aggregate by week/month and indicate aggregation, with 2D histogram alternative. Scene needs deliberate depth, restrained metallic lines and thin pulse accents, not flashy DNA stock animation. The wow factor is transparent empirical lineage: every glowing bridge maps to a Git-derived observation in the dataset.
```

**Evaluator reveal:** pick a historical bridge and cross-filter the current twin to the associated modules.

---

## PROMPT 09 — EVIDENCE PRISM: THREE CHANNELS, ONE LEARNED RANKING

```text
Build a transparent triangular 3D 'Evidence Prism' floating over a conventional evidence table. The faces represent STATIC STRUCTURE, GIT EVOLUTION and SEMANTIC CODE. When a candidate is selected, each face lights only if that channel contributed a candidate source or real measured feature. Inside the prism display one small node representing the selected target, with radial inscriptions for typed shortest path, prior co-change frequency/cutoff and cosine similarity; display missing value as unavailable rather than zero.

The prism must NOT claim that three light intensities add into the final model score. A sidepanel shows the real learned model score, rank, candidate sources and any valid measured attribution/sensitivity method with disclaimer. Clicking a face opens exactly corresponding evidence: structural path and source line, commit cochanges, or semantically related code spans. Provide 'compare two targets' where prisms rotate and channel values show side-by-side. Include a concise human-readable explanation of why ML fusion may rank a candidate highly even if no direct path exists.

Visual style: premium scientific glass instrument with readable engraved labels and carefully controlled refractive material. Use CSS for values to avoid GPU text clutter. Provide 2D triangular chart alternative that tells the same truth. Add tests verifying all shown values exist in the EvidenceRecord list.
```

**Evaluator reveal:** defend the fusion architecture visually in 20 seconds with clickable proof for all three channels.

---

## PROMPT 10 — CODE MRI: INTERACTIVE X-RAY OF A SOFTWARE MODULE

```text
Implement a 'Code MRI' mode for inspecting one selected module. Render a precise layered cutaway of its files, classes, methods and tests like a medical tomography instrument, but with crisp technical labels instead of biology imagery. A horizontal depth slider moves through nested architectural levels package → file → class → method → test. Layers are real graph entity hierarchy, not arbitrary depth levels.

Add two functional views: dependency X-ray shows typed CALLS/IMPORTS/TESTS flows that touch the current layer; impact X-ray highlights predicted targets in the selected module with rank and score. Clicking a layer or method opens the real source range in Monaco and focuses path evidence. Draw unresolved static relations in a visible uncertainty pattern. A contextual 'inspect why this is here' control retrieves source mapping and graph ancestors. Collapsing hidden layers must not discard ID selection.

Use a slender scanning line as an occasional transition, not as a data claim. Display absolute file/method counts for the current layer and breadcrumbs; provide conventional tree/list fallback. Optimize for mid-size modules with aggregation and scroll drill-down. The unique effect is surgical, traceable precision, not an overwhelming node cloud.
```

**Evaluator reveal:** zoom from district-level visualization to individual source lines while preserving a coherent architecture metaphor.

---

## PROMPT 11 — MODEL ABLATION OBSERVATORY: A RESEARCH INSTRUMENT

```text
Create a 'Model Ablation Observatory' that visualizes real, precomputed evaluation results. Main stage: a butterfly-style rank-flow diagram where each case/candidate is a line connecting its rank under FULL FUSION to its rank under STATIC-ONLY, HISTORY-ONLY, SEMANTIC-ONLY, and optionally XGBoost. Choose a fixed evaluation seed or a bounded aggregate, with explicit sample counts and identical candidate pools. Animated transitions express measured rank movements. Lines and labels show model variants, target symbols and score, not fictional impact trajectories.

Above: micro-metrics for Recall@5/10, MAP@10, NDCG@10, PR-AUC (if calculated), candidate retrieval recall and inference p95; include comparison/CI when available, result version and repo split. Below: matrices for full vs remove-static/remove-history/remove-semantic with measured deltas and a 'show failed cases' drilldown. Click a failing case and jump into the 3D graph on the exact historical pre-commit snapshot, then reveal actual co-change labels after prediction. Have a warning when results are incomplete or not directly comparable.

The visual language should resemble a bespoke scientific oscilloscope, with restrained gradient, sophisticated small multiples, fine grid lines and clearly labeled axes. Never render random 'training curves' as placeholder. The screen must prove this is an ML project evaluated against real baselines, not just a visual code explorer.
```

**Evaluator reveal:** demonstrate which data channel actually contributes measurable predictive value, including when it doesn't.

---

## PROMPT 12 — FLIGHT RECORDER / LIVE INDEXING CONTROL ROOM

```text
Build a gorgeous but rigorous 'Flight Recorder' showing the real processing timeline for a selected job or prediction. Each backend phase is a physical track segment on a horizontal runway: clone, parse, graph construction, Git evolution, embedding, candidate retrieval, GNN scoring, evidence retrieval, explanation. Active tasks show pulses only when server events arrive. Completed phases show real durations, processed counts and source versions. Failures interrupt the track and open actionable retry information. Avoid fake infinite spinners or fabricated countdowns.

Support WebSocket/SSE reconnect and event ID replay, and a synchronized structured log inspector. Clicking a phase opens its diagnostic details. Running a forecast should draw a new track based on actual job data, then end in a visual packet containing prediction run ID, SHA, model version, candidate pool size and evidence coverage. Add job cancel/retry controls wired to endpoints and clear stale-result indicator. A 'replay completed job' feature animates persisted event history, labeled replay rather than live ingestion.

Visual art direction: aircraft recorder / mission-control testbench, precise lines, muted CRT-inspired typography, cyan phase accents, no fake terminal text. Reuse event schema from master prompt. An evaluator should be able to trace how a particular score was produced and exactly when Groq was invoked after scoring.
```

**Evaluator reveal:** the processing pipeline becomes visible, proving the interface is driven by real asynchronous backend work.

---

## PROMPT 13 — EXTRA: COMPLETE COMMAND DECK HOME SCREEN (use early in frontend build)

```text
Design and implement the home/dashboard page of Neural Cartographer as a premium dark technical observatory. The top 60% of the page is a magnificent but grounded 3D architectural preview of the ACTIVE REPOSITORY (Code Metropolis component in preview mode), not a marketing stock photo or randomly generated graph. A slim floating command rail lets the user choose repo/ref, search a function and launch 'Forecast impact'. On the right, a precise model readiness/provenance panel explains whether results will use a trained GraphSAGE, XGBoost baseline or heuristic fallback. Across the bottom show real graph stats, history churn hotspots and recent processing stages from API; no fake charts.

Create a persistent navy/graphite shell, small uppercase section labels, highly legible text, icy cyan action accents, dusty purple history indicators, amber risk, understated animated linework. Use spacious but purposeful placement and a clear one-click demo path. Include skeleton loading, clean empty onboarding, unauthorized/error states and a demo-fixture provenance badge. The page must remain usable in 1366px laptop width and 4K evaluator projection. Every metric card is clickable and filters/opens the actual underlying page; buttons must do work.

Deliver polished React/TypeScript components, responsive CSS, URL-synced selected repo and a Playwright test covering import/search/forecast navigation. This screen should immediately communicate 'software intelligence instrument' rather than ordinary admin dashboard.
```

---

## How to run these prompts in the most productive order

1. Start with the **master coding-agent prompt** and instruct the agent to implement Phase 0–2 first; use the home screen prompt and Code Metropolis (13 and 01) while building actual repo ingestion.
2. Once true prediction endpoints exist, implement 02 (Shockwave), 05 (Dependency Fiber Optics) and 09 (Evidence Prism) to show explainable ML visually.
3. Add 03 (Parallel Universes), 04 (Temporal Rift) and 11 (Ablation Observatory) as the most persuasive evaluator features.
4. Only then add 07 (Test Constellation), 06 (Risk Topography), 10 (Code MRI), 08 (Commit DNA) and 12 (Flight Recorder), according to time and performance.

**One crucial agent instruction to prepend to every visual prompt:** "Reuse existing real backend API contracts and shared node IDs. Do not generate random nodes, scores, citations or Git history. If real data is unavailable, build a visibly labeled demo-only fixture and wire the component so it works with the real API when available. Produce actual interactive React code, not only a design mockup."
