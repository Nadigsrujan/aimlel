import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import ArchiveExplorer from "./components/ArchiveExplorer.jsx";
import Observatory from "./components/Observatory.jsx";
import ResearchPanel from "./components/ResearchPanel.jsx";
import JobHistory from "./components/JobHistory.jsx";
import ImpactResults from "./components/ImpactResults.jsx";
import { api } from "./api/client.js";
import "@xyflow/react/dist/style.css";
import "./style.css";
const names = {
  "combined-v1": "Combined evidence",
  "path-distance-v1": "Directory proximity",
  "imports-v1": "Static imports",
  "cochange-v1": "Historical co-change",
  "semantic-v1": "Code similarity",
  "popularity-v1": "Change frequency",
  "heterogeneous-v1": "GraphSAGE · learned fusion",
  "random-v1": "Random baseline",
};
function App() {
  const [catalog, setCatalog] = useState([]),
    [repo, setRepo] = useState(
      new URLSearchParams(window.location.search).get("repo") || "",
    ),
    [files, setFiles] = useState([]),
    [seed, setSeed] = useState("");
  const [search, setSearch] = useState(""),
    [seedSearch, setSeedSearch] = useState(""),
    [target, setTarget] = useState(""),
    [url, setUrl] = useState("");
  const [ranker, setRanker] = useState("combined-v1"),
    [rankers, setRankers] = useState([]),
    [topK, setTopK] = useState(10);
  const [result, setResult] = useState(null),
    [status, setStatus] = useState("Connecting to local engine…"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [job, setJob] = useState(null),
    [tab, setTab] = useState("observatory");
  const requestId = useRef(0);
  const current = catalog.find((r) => r.repo === repo);
  useEffect(() => {
    if (repo) {
      const url = new URL(window.location.href);
      url.searchParams.set("repo", repo);
      window.history.replaceState(null, "", url);
    }
  }, [repo]);
  async function refresh(preferred) {
    const rows = await api("/api/v1/catalog");
    setCatalog(rows);
    setRepo(
      (previous) =>
        preferred ||
        previous ||
        rows.find((r) => r.available)?.repo ||
        rows[0]?.repo ||
        "",
    );
  }
  useEffect(() => {
    Promise.all([
      refresh(),
      api("/api/v1/models").then((v) => {
        setRankers(v.rankers);
        setRanker(v.default);
      }),
      api("/api/v1/jobs").then((rows) => {
        const active = rows.find((row) =>
          ["running", "cancelling"].includes(row.status),
        );
        if (active) {
          setJob({ id: active.job, repo: active.repo });
          setTab("connect");
        }
      }),
    ])
      .then(() => setStatus("Engine connected"))
      .catch((e) => setError(e.message));
    const timer = setInterval(() => {
      refresh().catch(() => {});
      api("/api/v1/models")
        .then((value) => setRankers(value.rankers))
        .catch(() => {});
    }, 15000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    let active = true;
    requestId.current++;
    setBusy(false);
    setFiles([]);
    setSeed("");
    setResult(null);
    setError("");
    if (!repo || !current?.available) return;
    if (target && !/^[0-9a-f]{40}$/.test(target)) {
      setStatus("Enter a complete 40-character commit SHA");
      return;
    }
    setStatus("Loading snapshot…");
    api("/api/files?" + new URLSearchParams({ repo, target }))
      .then((rows) => {
        if (active) {
          setFiles(rows);
          setSeed(rows[0] || "");
          setStatus(
            rows.length ? "Snapshot ready" : "No supported Python files",
          );
        }
      })
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [repo, target, current?.available]);
  useEffect(() => {
    if (!job) return;
    let active = true,
      timer;
    async function poll() {
      try {
        const v = await api("/api/v1/jobs/" + job.id);
        if (!active) return;
        if (v.status === "running" || v.status === "cancelling") {
          const progress = v.progress || {};
          setStatus(
            `${v.status === "cancelling" ? "Stopping" : "Indexing"} ${job.repo} · ${progress.stage || "starting"}${progress.commits_scanned ? ` · ${progress.commits_scanned.toLocaleString()} commits` : ""} · ${progress.elapsed_seconds || 0}s`,
          );
          timer = setTimeout(poll, 1500);
        } else {
          setJob(null);
          if (v.error) setError(v.error);
          else if (v.status === "processed") {
            await refresh(job.repo);
            setTab("explore");
            setStatus("Repository indexed");
          } else setStatus("Indexing cancelled");
        }
      } catch (e) {
        if (active) {
          setError(e.message);
          setJob(null);
        }
      }
    }
    poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [job]);
  async function run(e) {
    e.preventDefault();
    const id = ++requestId.current;
    setBusy(true);
    setError("");
    setStatus("Tracing repository evidence…");
    try {
      const value = await api("/api/v1/analysis", {
        repo,
        seed,
        target,
        ranker,
        top_k: Number(topK),
      });
      if (id === requestId.current) {
        setResult(value);
        setStatus("Analysis complete");
      }
    } catch (e) {
      if (id === requestId.current) setError(e.message);
    } finally {
      if (id === requestId.current) setBusy(false);
    }
  }
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const v = await api("/api/v1/jobs", { url });
      setJob({ id: v.job, repo: v.repo });
      setUrl("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function cancel() {
    try {
      await api("/api/v1/jobs/" + job.id + "/cancel", {});
      setJob(null);
      setStatus("Indexing cancelled");
    } catch (e) {
      setError(e.message);
    }
  }
  const available = catalog.filter((r) => r.available).length;
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#">
          <span className="brand-mark">
            N<span>↗</span>
          </span>
          <span>
            neural<span className="brand-sub">cartographer</span>
          </span>
        </a>
        <div className="workspace-label">YOUR WORKSPACE</div>
        <button
          className={"nav-item " + (tab === "observatory" ? "active" : "")}
          onClick={() => setTab("observatory")}
        >
          ◉ <span>Command Deck</span>
          <kbd>00</kbd>
        </button>
        <button
          className={"nav-item " + (tab === "explore" ? "active" : "")}
          onClick={() => setTab("explore")}
        >
          ◈ <span>Impact explorer</span>
          <kbd>01</kbd>
        </button>
        <button
          className={"nav-item " + (tab === "connect" ? "active" : "")}
          onClick={() => setTab("connect")}
        >
          ＋ <span>Connect repository</span>
        </button>
        <button
          className={"nav-item " + (tab === "research" ? "active" : "")}
          onClick={() => setTab("research")}
        >
          ▥ <span>Model lab</span>
        </button>
        <div className="sidebar-heading">
          REPOSITORIES <span>{catalog.length}</span>
        </div>
        <input
          className="search"
          aria-label="Search repositories"
          placeholder="Search repositories…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <nav className="repo-list">
          {catalog
            .filter((r) => r.repo.toLowerCase().includes(search.toLowerCase()))
            .map((r) => (
              <button
                key={r.repo}
                onClick={() => {
                  setRepo(r.repo);
                  setTab("observatory");
                }}
                className={"repo-item " + (repo === r.repo ? "selected" : "")}
              >
                <span className={"repo-dot " + (r.available ? "ready" : "")} />
                <span>
                  {r.repo.split("/")[1]}
                  <small>{r.repo.split("/")[0]}</small>
                </span>
                <span className="repo-arrow">↗</span>
              </button>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="live-dot" /> Local analysis engine
          <small>Python repositories · Evidence first</small>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <span>
            Workspace <span className="slash">/</span>{" "}
            {tab === "observatory"
              ? "Command Deck"
              : tab === "research"
                ? "Model lab"
                : tab === "connect"
                  ? "Connect repository"
                  : "Impact explorer"}
          </span>
          <span className="local-badge">● LOCAL WORKSPACE</span>
        </div>
        <header className={tab === "observatory" ? "observatory-intro" : ""}>
          <div>
            <div className="eyebrow">UNDERSTAND THE CHANGE BEFORE YOU SHIP</div>
            <h1>
              {tab === "research"
                ? "Put the model to the test."
                : tab === "connect"
                  ? "Map a new codebase."
                  : "Every change has a ripple."}
            </h1>
            <p>
              {tab === "research"
                ? "Inspect experiment provenance, validation results, and the path to an honest held-out evaluation."
                : tab === "connect"
                  ? "Connect a public Python repository and build its structural and historical map."
                  : "Trace related files, inspect the evidence, and plan your next change with context."}
            </p>
          </div>
          <div className="header-coordinate">
            NC / 001
            <br />
            <span>REPOSITORY INTELLIGENCE</span>
          </div>
        </header>
        <label className="mobile-repo">
          Repository
          <select value={repo} onChange={(e) => setRepo(e.target.value)}>
            {catalog.map((row) => (
              <option key={row.repo}>{row.repo}</option>
            ))}
          </select>
        </label>
        <div
          className={
            "metrics " + (tab === "observatory" ? "observatory-hidden" : "")
          }
        >
          <div>
            <span>READY REPOSITORIES</span>
            <strong>
              {available}
              <small>/ {catalog.length}</small>
            </strong>
          </div>
          <div>
            <span>ACTIVE SNAPSHOT</span>
            <strong className="metric-text">
              {current?.revision?.slice(0, 8) || "—"}
              <small>{current?.split || "Select repository"}</small>
            </strong>
          </div>
          <div>
            <span>RANKING STRATEGY</span>
            <strong className="metric-text">
              {names[ranker] || ranker}
              <small>
                {ranker === "heterogeneous-v1"
                  ? "Trained structure + history + semantics"
                  : ranker === "semantic-v1"
                    ? "Pinned CodeBERT similarity"
                    : "Evidence-based heuristic"}
              </small>
            </strong>
          </div>
          <div>
            <span>ANALYSIS SCOPE</span>
            <strong>
              {result?.candidate_count ?? "—"}
              <small>eligible files</small>
            </strong>
          </div>
        </div>
        {error && (
          <div className="alert" role="alert">
            <strong>Action needed</strong>
            <span>{error}</span>
            <button onClick={() => setError("")} aria-label="Dismiss error">
              ×
            </button>
          </div>
        )}
        {tab === "observatory" ? (
          repo && (
            <Observatory
              repo={repo}
              onJobs={() => setTab("connect")}
              onResearch={() => setTab("research")}
            />
          )
        ) : tab === "research" ? (
          <ResearchPanel />
        ) : tab === "connect" ? (
          <section className="connect-panel">
            <span className="section-tag">01 / CONNECT</span>
            <h2>Bring your repository into focus.</h2>
            <p>
              Index source structure and Git history without executing
              repository code. Public GitHub repositories only.
            </p>
            <form onSubmit={submit}>
              <label>
                Repository URL
                <input
                  type="url"
                  placeholder="https://github.com/owner/repository"
                  required
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
              </label>
              <button className="primary" disabled={busy || !!job}>
                Index repository ↗
              </button>
            </form>
            <div className="info-grid">
              <div>
                <strong>01</strong>
                <h3>Pin the revision</h3>
                <p>A fixed commit keeps analysis reproducible.</p>
              </div>
              <div>
                <strong>02</strong>
                <h3>Build the map</h3>
                <p>Extract Python entities and import relationships.</p>
              </div>
              <div>
                <strong>03</strong>
                <h3>Explore evidence</h3>
                <p>Inspect static paths and historical co-change.</p>
              </div>
            </div>
            <ArchiveExplorer />
            <JobHistory
              onRetry={(value) => setJob({ id: value.job, repo: value.repo })}
            />
          </section>
        ) : (
          <>
            <section className="analysis-panel">
              <div className="section-heading">
                <span className="section-tag">01 / CONFIGURE ANALYSIS</span>
                <span className="snapshot-badge">
                  {current?.available
                    ? "Snapshot available"
                    : "Data not materialized"}
                </span>
              </div>
              <form onSubmit={run}>
                <label className="seed-label">
                  Change starts here
                  <input
                    placeholder="Filter Python files…"
                    aria-label="Filter seed files"
                    value={seedSearch}
                    onChange={(e) => setSeedSearch(e.target.value)}
                  />
                  <select
                    aria-label="Seed file"
                    value={seed}
                    onChange={(e) => setSeed(e.target.value)}
                    disabled={!files.length}
                  >
                    {files
                      .filter(
                        (f) =>
                          f === seed ||
                          f.toLowerCase().includes(seedSearch.toLowerCase()),
                      )
                      .map((f) => (
                        <option key={f}>{f}</option>
                      ))}
                  </select>
                </label>
                <label>
                  Ranking method
                  <select
                    value={ranker}
                    onChange={(e) => setRanker(e.target.value)}
                  >
                    {rankers.map((r) => (
                      <option key={r} value={r}>
                        {names[r] || r}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="topk">
                  Top K
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={topK}
                    onChange={(e) => setTopK(e.target.value)}
                  />
                </label>
                <button className="primary" disabled={busy || !seed}>
                  {busy ? "Tracing…" : "Analyze impact"} <span>↗</span>
                </button>
              </form>
              <details className="advanced">
                <summary>
                  Historical analysis <span>optional</span>
                </summary>
                <label>
                  Target commit SHA
                  <input
                    value={target}
                    onChange={(e) => setTarget(e.target.value.trim())}
                    maxLength={40}
                    placeholder="Full 40-character SHA; analyzes the parent snapshot"
                  />
                </label>
              </details>
            </section>
            {result ? (
              <ImpactResults
                key={repo + result.graph_revision + seed + ranker}
                result={result}
              />
            ) : (
              <section className={"empty-canvas " + (busy ? "is-loading" : "")}>
                <div className="orbit">
                  <span>◈</span>
                </div>
                <span className="section-tag">YOUR NEXT CHANGE, MAPPED</span>
                <h2>
                  {busy
                    ? "Following the connections…"
                    : current?.available
                      ? "Start with a file. See the connections."
                      : "This snapshot needs its local data."}
                </h2>
                <p>
                  {current?.available
                    ? "Select a seed file and analyze its related files. Inspect each result to reveal the evidence behind it."
                    : "The pinned manifest is present, but the processed graph is missing. Restore the dataset or connect a new public repository."}
                </p>
                {!current?.available && (
                  <button
                    className="secondary"
                    onClick={() => setTab("connect")}
                  >
                    Connect a repository ↗
                  </button>
                )}
                <div className="canvas-legend">
                  <span>● Seed component</span>
                  <span>○ Related files</span>
                  <span>― Verified import paths</span>
                </div>
              </section>
            )}
          </>
        )}
        <div className="statusbar" role="status" aria-live="polite">
          <span>
            <i className="live-dot" />
            {status}
          </span>
          {job && <button onClick={cancel}>Cancel indexing</button>}
          <span>
            {catalog.some((r) => r.split === "test")
              ? "Held-out study recorded"
              : "Held-out study not published"}
          </span>
        </div>
        <footer>
          NEURAL CARTOGRAPHER <span>Structure. History. Evidence.</span>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
