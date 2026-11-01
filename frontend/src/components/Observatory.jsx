import RankFlow from "./RankFlow.jsx";
import React, { useState, useEffect, useRef, useMemo } from "react";
import { api } from "../api/client.js";
import {
  TestStars,
  CodeMRI,
  EvolutionSculpture,
  RiskTerrain,
} from "./AnalyticalViews.jsx";
import CodeMetropolis from "./CodeMetropolis.jsx";
import SymbolSource from "./SymbolSource.jsx";
import ImpactResults from "./ImpactResults.jsx";
function savedGraph(result, fallback) {
  if (!result || result.graph_revision === fallback.revision) return fallback;
  const nodes = result.entities || [],
    ids = new Map(nodes.map((n) => [n.legacy_id, n.id]));
  return {
    repo: result.repo,
    revision: result.graph_revision,
    nodes,
    edges: result.graph.edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({
        ...e,
        source: ids.get(e.source),
        target: ids.get(e.target),
      })),
    quality: {
      entities: nodes.length,
      unresolved_edges:
        result.relation_resolution?.calls -
          result.relation_resolution?.resolved_calls || 0,
    },
    slice: true,
  };
}
const pages = [
  "Command Deck",
  "Code Metropolis",
  "Impact Lab",
  "Evolution Observatory",
  "Evidence & Explainability",
  "Test Constellation",
  "Repositories & Jobs",
  "Settings & Provenance",
];
export default function Observatory({ repo, onJobs, onResearch }) {
  const [page, setPage] = useState("Command Deck"),
    [graph, setGraph] = useState(null),
    [selected, setSelected] = useState(""),
    [query, setQuery] = useState(""),
    [seeds, setSeeds] = useState([]),
    [run, setRun] = useState(null),
    [saved, setSaved] = useState([]),
    [history, setHistory] = useState([]),
    [events, setEvents] = useState([]),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [ranker, setRanker] = useState("heterogeneous-v1"),
    [models, setModels] = useState([]),
    [name, setName] = useState("Change rehearsal"),
    [k, setK] = useState(10),
    [target, setTarget] = useState(""),
    [provider, setProvider] = useState("local"),
    [style, setStyle] = useState("concise"),
    [consent, setConsent] = useState(false),
    [reading, setReading] = useState(null),
    [readingBusy, setReadingBusy] = useState(false),
    [comparison, setComparison] = useState(null),
    [terrain, setTerrain] = useState(false),
    [mri, setMRI] = useState(false),
    [entity, setEntity] = useState(""),
    [diff, setDiff] = useState(""),
    [outcome, setOutcome] = useState(null);
  const cameraBus = useMemo(() => ({ listeners: new Set(), state: null }), []);
  const generation = useRef(0),
    readingRequest = useRef(0),
    searchRef = useRef();
  useEffect(() => {
    const id = ++generation.current;
    setGraph(null);
    setRun(null);
    setBusy(false);
    setEntity("");
    setSeeds([]);
    setSelected("");
    setTarget("");
    setError("");
    Promise.all([
      api("/api/v1/observatory/graph?" + new URLSearchParams({ repo })),
      api("/api/v1/observatory/history?" + new URLSearchParams({ repo })),
      api("/api/v1/models"),
    ])
      .then(([g, h, m]) => {
        if (id !== generation.current) return;
        setGraph(g);
        setHistory(h);
        setModels(m.rankers);
        setRanker(m.default);
        const first = g.nodes.find((n) => n.kind === "file");
        setSelected(first?.path || "");
      })
      .catch((e) => id === generation.current && setError(e.message));
    api("/api/v1/observatory/runs")
      .then(setSaved)
      .catch(() => {});
  }, [repo]);
  useEffect(() => {
    const stream = new EventSource("/api/v1/observatory/events");
    stream.onmessage = (e) => {
      const row = JSON.parse(e.data);
      setEvents((previous) =>
        [...previous.filter((p) => p.sequence !== row.sequence), row].slice(
          -100,
        ),
      );
    };
    return () => stream.close();
  }, []);
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);
  useEffect(() => {
    readingRequest.current++;
    setReading(null);
    setReadingBusy(false);
    setOutcome(null);
  }, [selected, run?.id]);
  async function forecast(e) {
    e?.preventDefault();
    const id = ++generation.current;
    if (!seeds.length) setSeeds([selected]);
    setBusy(true);
    setError("");
    try {
      const value = await api("/api/v1/observatory/runs", {
        repo,
        seeds: seeds.length ? seeds : [selected],
        target,
        ranker,
        name,
      });
      if (id !== generation.current) return;
      setRun(value);
      setPage("Impact Lab");
      setSaved(await api("/api/v1/observatory/runs"));
      setSelected(value.results[0].candidates[0]?.path || selected);
    } catch (e) {
      if (id === generation.current) setError(e.message);
    } finally {
      if (id === generation.current) setBusy(false);
    }
  }
  const result = run?.results?.[0],
    shown = result
      ? { ...result, candidates: result.candidates.slice(0, k) }
      : null;
  const displayGraph = useMemo(
    () => (graph ? savedGraph(result, graph) : null),
    [result, graph],
  );
  const visible = (displayGraph?.nodes || [])
    .filter(
      (n) =>
        query &&
        (n.path + " " + n.qualified_name)
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .slice(0, 30);
  const sourceResult = result || {
    repo,
    graph_revision: graph?.revision,
    entities: graph?.nodes,
  };
  const stale = !!result && result.graph_revision !== graph?.revision;
  async function explain() {
    const id = ++readingRequest.current;
    setError("");
    setReadingBusy(true);
    try {
      const value = await api("/api/v1/observatory/readings", {
        run: run.id,
        candidate: selected,
        provider,
        style,
        allow_hosted: consent,
      });
      if (id === readingRequest.current) setReading(value);
    } catch (e) {
      if (id === readingRequest.current) setError(e.message);
    } finally {
      if (id === readingRequest.current) setReadingBusy(false);
    }
  }
  async function load(id, compare = false) {
    try {
      const revisionOfRequest = generation.current;
      const value = await api("/api/v1/observatory/runs/" + id);
      if (revisionOfRequest !== generation.current) return;
      if (value.request.repo !== repo)
        throw new Error("Choose a saved scenario for the active repository");
      if (compare) {
        if (value.id === run?.id)
          throw new Error("Choose a different saved forecast to compare.");
        setComparison(value);
      } else {
        generation.current++;
        setBusy(false);
        setRun(value);
        setSeeds(value.request.seeds);
        setTarget(value.request.target);
        setRanker(value.request.ranker);
        setName(value.name);
        setPage("Impact Lab");
      }
    } catch (e) {
      setError(e.message);
    }
  }
  function exportRun(format) {
    if (!run) return;
    let content, type;
    if (format === "html") {
      const pre = document.createElement("pre");
      pre.textContent = JSON.stringify(run, null, 2);
      content =
        '<!doctype html><meta charset="utf-8"><title>Neural Cartographer inspection plan</title><h1>Saved inspection plan</h1><p>Potential co-change ranking; not runtime failures or calibrated probabilities.</p>' +
        pre.outerHTML;
      type = "text/html";
    } else if (format === "csv") {
      const csv = (value) => '"' + String(value).replaceAll('"', '""') + '"';
      content =
        "path,reciprocal_rank_fusion,seed_ranks\n" +
        run.aggregate
          .map((r) =>
            [
              csv(/^[=+@-]/.test(r.path) ? "'" + r.path : r.path),
              r.rrf,
              csv(JSON.stringify(r.seed_ranks)),
            ].join(","),
          )
          .join("\n");
      type = "text/csv";
    } else {
      content = JSON.stringify(run, null, 2);
      type = "application/json";
    }
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `cartographer-${run.id}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="observatory">
      <nav className="observatory-tabs" aria-label="Observatory sections">
        {pages.map((p) => (
          <button
            key={p}
            aria-current={page === p ? "page" : undefined}
            className={page === p ? "active" : ""}
            onClick={() =>
              p === "Repositories & Jobs" ? onJobs() : setPage(p)
            }
          >
            {p}
          </button>
        ))}
        <button onClick={onResearch}>Research Bench ↗</button>
      </nav>
      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      <div className="observatory-heading">
        <div>
          <span className="section-tag">NEURAL CARTOGRAPHER / OBSERVATORY</span>
          <h2>{page}</h2>
          <p>
            {repo} ·{" "}
            <code>
              {graph?.revision?.slice(0, 12) || "Loading pinned snapshot…"}
            </code>
          </p>
        </div>
        <span className="snapshot-badge">
          FILE-LEVEL MODEL · SOURCE-LEVEL INSPECTION
        </span>
      </div>
      {graph && (
        <>
          <div className="command-rail">
            <label>
              Search files, classes, functions <kbd>/</kbd>
              <input
                ref={searchRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Find an actual entity…"
              />
            </label>
            <label>
              Ranking model
              <select
                value={ranker}
                onChange={(e) => setRanker(e.target.value)}
              >
                {models.map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
            <button
              className="primary"
              disabled={busy || (!selected && !seeds.length)}
              onClick={forecast}
            >
              {busy ? "Forecast running…" : "Forecast impact ↗"}
            </button>
          </div>
          {!!query && (
            <div className="search-results">
              {visible.length ? (
                visible.map((n) => (
                  <button
                    className="secondary"
                    key={n.id}
                    onClick={() => {
                      setSelected(n.path);
                      setEntity(n.kind === "file" ? "" : n.id);
                      setQuery("");
                      setPage("Code Metropolis");
                    }}
                  >
                    {n.kind} · {n.qualified_name || n.path}
                    <small>
                      {n.path} : {n.start || 1}
                    </small>
                  </button>
                ))
              ) : (
                <p>No matching entity in this pinned snapshot.</p>
              )}
            </div>
          )}
          {busy && run && (
            <p role="status">
              Previous saved run remains visible while a new forecast is
              running.
            </p>
          )}
          {stale && (
            <p className="alert">
              Historical result: {result.graph_revision.slice(0, 12)}. The city
              uses the saved historical graph slice (up to 500 entities). Source
              and evidence retain that SHA.
            </p>
          )}
          {["Command Deck", "Code Metropolis"].includes(page) && (
            <>
              <CodeMetropolis
                graph={displayGraph}
                selected={selected}
                onSelect={setSelected}
                onSelectEntity={setEntity}
                result={shown}
                mode="city"
              />
              <button
                className="secondary"
                onClick={() => setTerrain(!terrain)}
              >
                {terrain
                  ? "Hide module risk terrain"
                  : "Show module risk terrain"}
              </button>
              {terrain && (
                <RiskTerrain
                  graph={displayGraph}
                  result={shown}
                  onSelect={setSelected}
                />
              )}
              {!result && terrain && (
                <p>
                  No prediction yet; neutral baseline heights carry no risk
                  claim.
                </p>
              )}
            </>
          )}
          {page === "Command Deck" && (
            <div className="observatory-stats">
              {[
                ["Source entities", graph.nodes.length],
                ["Files", graph.nodes.filter((n) => n.kind === "file").length],
                ["Resolved relations", graph.edges.length],
                ["Unresolved / external", graph.quality.unresolved_edges],
              ].map(([label, value]) => (
                <button key={label} onClick={() => setPage("Code Metropolis")}>
                  <small>{label}</small>
                  <strong>{value.toLocaleString()}</strong>
                </button>
              ))}
            </div>
          )}
          {["Code Metropolis", "Command Deck"].includes(page) && selected && (
            <section className="evidence-panel">
              <div className="section-heading">
                <h3>{selected}</h3>
                <button
                  className="secondary"
                  disabled={seeds.includes(selected) || seeds.length >= 5}
                  onClick={() => setSeeds([...seeds, selected])}
                >
                  ＋ Add owning file to scenario
                </button>
              </div>
              <button className="secondary" onClick={() => setMRI(!mri)}>
                {mri ? "Hide Code MRI" : "Open Code MRI cutaway"}
              </button>
              {mri && (
                <CodeMRI
                  graph={displayGraph}
                  path={selected}
                  onEntity={setEntity}
                />
              )}
              <p className="result-note">
                Selecting a function opens its real source through the entity
                selector. Forecasts use its owning file; no function-level
                accuracy is claimed.
              </p>
              <SymbolSource
                key={repo + selected + displayGraph.revision + entity}
                initialEntity={entity}
                result={{
                  repo,
                  graph_revision: displayGraph.revision,
                  entities: displayGraph.nodes,
                }}
                path={selected}
              />
            </section>
          )}
          {page === "Impact Lab" && (
            <>
              <section className="analysis-panel">
                <h3>Rehearse a change</h3>
                <label>
                  Optional unified diff · preview only
                  <textarea
                    rows="4"
                    value={diff}
                    onChange={(e) => setDiff(e.target.value)}
                    placeholder="Paste a unified diff to select changed file seeds"
                  />
                </label>
                <button
                  className="secondary"
                  onClick={() => {
                    const paths = [
                      ...new Set(
                        [...diff.matchAll(/^\+\+\+ b\/(.+)$/gm)].map(
                          (m) => m[1],
                        ),
                      ),
                    ];
                    const known = paths.filter((p) =>
                      graph.nodes.some(
                        (n) => n.kind === "file" && n.path === p,
                      ),
                    );
                    if (!known.length) {
                      setError(
                        "No changed Python files match this pinned source snapshot",
                      );
                      return;
                    }
                    if (known.length > 5) {
                      setError("Scenario limit is five seeds; narrow the diff");
                      return;
                    }
                    setSeeds(known);
                  }}
                >
                  Use changed files as seeds
                </button>
                <label>
                  Scenario name
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </label>
                <p>
                  Seeds:{" "}
                  {seeds.length
                    ? seeds.join(" + ")
                    : selected || "Select a file in the city"}
                </p>
                {seeds.map((s) => (
                  <button
                    className="secondary"
                    key={s}
                    onClick={() => setSeeds(seeds.filter((v) => v !== s))}
                  >
                    Remove {s} ×
                  </button>
                ))}
                <label>
                  Cached visible Top K
                  <input
                    type="range"
                    min="1"
                    max="100"
                    value={k}
                    onChange={(e) => setK(+e.target.value)}
                  />
                  {k}
                </label>
                <button
                  className="primary"
                  disabled={busy || (!selected && !seeds.length)}
                  onClick={forecast}
                >
                  Save & forecast scenario
                </button>
                <p className="result-note">
                  Hypothetical analysis never edits repository code. Multi-seed
                  ordering uses reciprocal rank fusion over cached top-100
                  lists; each original model result is retained.
                </p>
              </section>
              {run && (
                <>
                  {run.request.target && (
                    <div className="evidence-panel">
                      <p>
                        Retrospective forecast completed. Observed co-change
                        truth is hidden until you reveal it.
                      </p>
                      <button
                        className="secondary"
                        onClick={async () => {
                          try {
                            setOutcome(
                              await api(
                                "/api/v1/observatory/runs/" +
                                  run.id +
                                  "/outcome",
                              ),
                            );
                          } catch (e) {
                            setError(e.message);
                          }
                        }}
                      >
                        Reveal observed co-change
                      </button>
                      {outcome && (
                        <>
                          <p>
                            Actual modified Python files (seed files excluded),
                            commit {outcome.commit}:
                          </p>
                          <ul>
                            {outcome.paths.map((p) => (
                              <li key={p}>{p}</li>
                            ))}
                          </ul>
                          <p>
                            Observed co-change is a historical label, not proof
                            of runtime breakage.
                          </p>
                        </>
                      )}
                    </div>
                  )}
                  <p>
                    Run <code>{run.id}</code> ·{" "}
                    {run.duration_seconds.toFixed(2)}s measured request time ·{" "}
                    {run.aggregation}
                  </p>
                  <div className="filters">
                    <button
                      className="secondary"
                      onClick={() => exportRun("json")}
                    >
                      Export immutable run JSON
                    </button>
                    <button
                      className="secondary"
                      onClick={() => exportRun("csv")}
                    >
                      Export aggregate CSV
                    </button>
                    <button
                      className="secondary"
                      onClick={() => exportRun("html")}
                    >
                      Export inspection report HTML
                    </button>
                  </div>
                  {run.results.length > 1 && (
                    <ol>
                      {run.aggregate.slice(0, k).map((r) => (
                        <li key={r.path}>
                          <button
                            className="link"
                            onClick={() => setSelected(r.path)}
                          >
                            {r.path}
                          </button>{" "}
                          · RRF {r.rrf.toFixed(5)} ·{" "}
                          {JSON.stringify(r.seed_ranks)}
                        </li>
                      ))}
                    </ol>
                  )}
                  <CodeMetropolis
                    graph={displayGraph}
                    selected={selected}
                    onSelect={setSelected}
                    onSelectEntity={setEntity}
                    result={shown}
                  />
                  <ImpactResults
                    key={run.id + k}
                    result={shown}
                    selectedPath={selected}
                    onSelect={setSelected}
                  />
                </>
              )}
              <section className="evidence-panel">
                <h3>Saved scenarios & parallel universes</h3>
                <p>
                  Compare saved forecasts. Matching SHA and candidate protocol
                  are required for direct score comparisons.
                </p>
                {saved
                  .filter((s) => s.request.repo === repo)
                  .map((s) => (
                    <div className="saved-run" key={s.id}>
                      <span>
                        {s.name} · {s.revision.slice(0, 8)} · {s.request.ranker}
                      </span>
                      <button className="secondary" onClick={() => load(s.id)}>
                        Open
                      </button>
                      <button
                        className="secondary"
                        onClick={() => load(s.id, true)}
                      >
                        Compare
                      </button>
                    </div>
                  ))}
                {comparison && run && (
                  <>
                    <p>
                      {comparison.results[0].graph_revision ===
                      result.graph_revision
                        ? "Same source snapshot"
                        : "Different snapshots — descriptive comparison only"}
                    </p>
                    <RankFlow
                      left={run}
                      right={comparison}
                      onSelect={setSelected}
                    />
                    <div className="twin-grid">
                      {[run, comparison].map((v) => (
                        <section key={v.id}>
                          <h4>{v.name}</h4>
                          <CodeMetropolis
                            graph={savedGraph(v.results[0], graph)}
                            selected={selected}
                            onSelect={setSelected}
                            result={v.results[0]}
                            cameraBus={cameraBus}
                          />
                          <p>
                            {v.request.ranker} ·{" "}
                            {v.results[0].graph_revision.slice(0, 12)}
                          </p>
                          <ol>
                            {v.results[0].candidates.slice(0, k).map((r) => (
                              <li key={r.path}>
                                {r.path} · {r.score.toFixed(3)}
                              </li>
                            ))}
                          </ol>
                        </section>
                      ))}
                    </div>
                  </>
                )}
              </section>
            </>
          )}
          {page === "Evolution Observatory" && (
            <section className="evidence-panel">
              <EvolutionSculpture history={history} onCommit={setTarget} />
              <h3>Temporal Rift · actual pinned Git history</h3>
              <p>
                Pick a commit to forecast from its parent. Future co-change
                outcomes remain hidden in this view. First-parent commits only;
                uncached historical inference may take longer.
              </p>
              <ol className="commit-ribbon">
                {history.map((h, i) => (
                  <li key={h.revision}>
                    <button
                      className="secondary"
                      onClick={() => {
                        setTarget(h.revision);
                        setPage("Impact Lab");
                      }}
                    >
                      <code>{h.revision.slice(0, 9)}</code>
                      <time>
                        {new Date(h.timestamp * 1000).toLocaleDateString()}
                      </time>
                      <span>{h.subject}</span>
                    </button>
                  </li>
                ))}
              </ol>
              {target && (
                <p>
                  Selected historical target: {target}
                  <button onClick={() => setTarget("")}>
                    Return to pinned head
                  </button>
                </p>
              )}
            </section>
          )}
          {page === "Evidence & Explainability" && (
            <section className="evidence-panel">
              <h3>Evidence Prism / Ask the Cartographer</h3>
              <p>
                Questions are bounded to why a saved ranked file merits
                inspection. No free-form unsupported code claims are generated.
              </p>
              {!run ? (
                <p>Run a forecast first to create immutable evidence.</p>
              ) : (
                <>
                  <label>
                    Candidate
                    <select
                      value={selected}
                      onChange={(e) => setSelected(e.target.value)}
                    >
                      <option value="">Select ranked file</option>
                      {result.candidates.map((c) => (
                        <option key={c.path}>{c.path}</option>
                      ))}
                    </select>
                  </label>
                  <div className="prism-channels">
                    {["structural", "history", "semantic"].map((channel) => {
                      const c = result.candidates.find(
                        (c) => c.path === selected,
                      );
                      return (
                        <section
                          key={channel}
                          className={
                            (c?.channels || []).includes(channel)
                              ? "present"
                              : ""
                          }
                        >
                          <h4>{channel}</h4>
                          <pre>
                            {JSON.stringify(
                              channel === "structural"
                                ? c?.evidence?.import_path
                                : channel === "history"
                                  ? c?.evidence?.past_commits
                                  : c?.features,
                              null,
                              2,
                            ) || "Unavailable"}
                          </pre>
                        </section>
                      );
                    })}
                  </div>
                  <p className="result-note">
                    Channel presence is evidence membership, not additive model
                    attribution.
                  </p>
                  <label>
                    Provider
                    <select
                      value={provider}
                      onChange={(e) => setProvider(e.target.value)}
                    >
                      <option value="local">Local deterministic</option>
                      <option value="groq">Groq · citation selection</option>
                      <option value="gemini">
                        Gemini · citation selection
                      </option>
                    </select>
                  </label>
                  <label>
                    Reading style
                    <select
                      value={style}
                      onChange={(e) => setStyle(e.target.value)}
                    >
                      {["concise", "technical", "evaluator"].map((s) => (
                        <option key={s}>{s}</option>
                      ))}
                    </select>
                  </label>
                  {provider !== "local" && (
                    <label>
                      <input
                        type="checkbox"
                        checked={consent}
                        onChange={(e) => setConsent(e.target.checked)}
                      />
                      Allow sending evidence paths and commit metadata to the
                      hosted provider; source code excluded.
                    </label>
                  )}
                  <button
                    className="primary"
                    disabled={
                      busy ||
                      readingBusy ||
                      !result.candidates.some((c) => c.path === selected) ||
                      (provider !== "local" && !consent)
                    }
                    onClick={explain}
                  >
                    {readingBusy
                      ? "Selecting verified evidence…"
                      : "Explain with verified citations"}
                  </button>
                  {reading && (
                    <>
                      <p>{reading.status}</p>
                      <ul>
                        {reading.statements.map((s) => (
                          <li key={s.id}>
                            {s.text}{" "}
                            {s.url && (
                              <a href={s.url} target="_blank" rel="noreferrer">
                                [{s.id}] ↗
                              </a>
                            )}
                          </li>
                        ))}
                      </ul>
                      <p>{reading.limitation}</p>
                      <code>Evidence hash: {reading.evidence_hash}</code>
                    </>
                  )}
                </>
              )}
            </section>
          )}
          {page === "Test Constellation" && (
            <section className="evidence-panel">
              <TestStars
                graph={displayGraph}
                result={shown}
                onSelect={setSelected}
              />
              <h3>Test inspection queue</h3>
              <p>
                Tests ranked by model evidence; no sandbox execution or runtime
                coverage claim.
              </p>
              {!result ? (
                <p>Forecast a change to populate test recommendations.</p>
              ) : (
                <>
                  {result.recommended_tests?.length ? (
                    <ol>
                      {result.recommended_tests.map((t) => (
                        <li key={t.path}>
                          <button
                            className="link"
                            onClick={() => setSelected(t.path)}
                          >
                            {t.path}
                          </button>{" "}
                          · score {t.score?.toFixed(3)} ·{" "}
                          {(t.channels || []).join(", ")}
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p>
                      No known recommended test in this result; this does not
                      prove zero test coverage.
                    </p>
                  )}
                  <SymbolSource
                    key={selected}
                    result={sourceResult}
                    path={selected}
                  />
                </>
              )}
            </section>
          )}
          {page === "Settings & Provenance" && (
            <section className="evidence-panel">
              <h3>Immutable source. Honest predictions.</h3>
              <dl>
                <dt>Snapshot</dt>
                <dd>{graph.revision}</dd>
                <dt>Scope</dt>
                <dd>
                  Python file-level potential co-change; real
                  functions/classes/tests available for source inspection.
                </dd>
                <dt>Scores</dt>
                <dd>
                  Uncalibrated ranking values. No probability or guaranteed
                  failure claims.
                </dd>
                <dt>Protocol</dt>
                <dd>
                  7 training / 2 validation / 3 held-out repositories. Frozen
                  GraphSAGE weights and pinned CodeBERT embeddings.
                </dd>
                <dt>Hosted explanations</dt>
                <dd>
                  Opt-in evidence metadata only. Set GROQ_API_KEY and GROQ_MODEL
                  server-side; missing credentials trigger deterministic local
                  fallback.
                </dd>
                <dt>Security</dt>
                <dd>
                  Localhost service. Repository code and tests are not executed.
                </dd>
              </dl>
              <button className="secondary" onClick={onResearch}>
                Inspect real research artifacts ↗
              </button>
            </section>
          )}
          <section className="flight-recorder">
            <div className="section-heading">
              <h3>Predictive Flight Recorder</h3>
              <span className="snapshot-badge">
                PERSISTED EVENTS · REPLAYABLE SSE
              </span>
            </div>
            <p className="result-note">
              Timestamps mark server observations. Earlier job stages are not
              reconstructed or given fabricated durations.
            </p>
            <ol>
              {events
                .slice(-12)
                .reverse()
                .map((e) => (
                  <li key={e.sequence}>
                    <code>#{e.sequence}</code>
                    <time>
                      {new Date(e.observed_at * 1000).toLocaleTimeString()}
                    </time>
                    <strong>{e.type.replaceAll("_", " ")}</strong>
                    <span>
                      {e.state?.progress?.stage ||
                        e.state?.status ||
                        e.run?.slice(0, 12)}
                    </span>
                  </li>
                ))}
            </ol>
          </section>
        </>
      )}
      {!graph && !error && (
        <p role="status">Reading the pinned source graph…</p>
      )}
    </div>
  );
}
