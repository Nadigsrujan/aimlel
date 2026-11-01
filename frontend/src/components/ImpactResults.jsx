import React, { useState } from "react";
import { ReactFlow, Background, Controls } from "@xyflow/react";
import SymbolSource from "./SymbolSource.jsx";
import EvidenceSummary from "./EvidenceSummary.jsx";
import { graphView } from "../graph/view.js";

export default function ImpactResults({ result, selectedPath, onSelect }) {
  const [localSelected, setLocalSelected] = useState(
    result.candidates[0]?.path || "",
  );
  const selected = selectedPath ?? localSelected;
  const setSelected = onSelect || setLocalSelected;
  const [channel, setChannel] = useState("all");
  const [minimum, setMinimum] = useState(-1);
  const candidates = result.candidates.filter(
    (row) =>
      row.score >= minimum &&
      (channel === "all" || row.channels?.includes(channel)),
  );
  const recommendedTests = (result.recommended_tests || []).filter((row) =>
    /(^|\/)tests?(\/|$)|(^|\/)test_[^/]*\.py$|_test\.py$/.test(row.path),
  );
  const selectedTest = recommendedTests.find((row) => row.path === selected);
  const graphRows =
    selectedTest && !candidates.some((row) => row.path === selected)
      ? [...candidates, selectedTest]
      : candidates;
  const { nodes, edges } = graphView(result, graphRows, selected);
  const candidate =
    candidates.find((row) => row.path === selected) || selectedTest;
  function download() {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${result.repo.replace("/", "-")}-impact.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
  return (
    <section className="results">
      <p className="result-meta">
        <code>{result.graph_revision}</code> ·{" "}
        {result.graph.total_nodes || result.graph.nodes.length} entities ·{" "}
        {result.candidate_count} candidate files
      </p>
      <p className="result-note">
        Ranker: <strong>{result.ranker}</strong>.{" "}
        {result.model_status && <>Checkpoint: {result.model_status}. </>}Scores
        are uncalibrated ranking values, not probabilities. Select a file to
        inspect its evidence. Graph lines show only retrieved static import
        paths.
      </p>
      <div className="filters">
        <button className="secondary" onClick={download}>
          Export analysis ↓
        </button>
        <label>
          Evidence channel
          <select
            value={channel}
            onChange={(event) => setChannel(event.target.value)}
          >
            <option value="all">All</option>
            <option value="structural">Static imports</option>
            <option value="history">Past co-change</option>
            <option value="directory">Directory</option>
            <option value="semantic">Code similarity</option>
          </select>
        </label>
        <label>
          Minimum score
          <input
            type="number"
            min="-1"
            step="0.01"
            value={minimum}
            onChange={(event) => setMinimum(Number(event.target.value))}
          />
        </label>
      </div>
      {!candidates.length && (
        <p role="status">
          No files match these filters. Lower the minimum score or choose
          another channel.
        </p>
      )}
      <section className="workspace">
        <div className="graph" aria-label="Impact graph">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            fitView
            onNodeClick={(_, node) => setSelected(node.id)}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        <aside className="rankings">
          <h2>Ranked files</h2>
          <ol>
            {candidates.map((row) => (
              <li key={row.path}>
                <button
                  className="link"
                  aria-pressed={selected === row.path}
                  onClick={() => setSelected(row.path)}
                >
                  {row.path}
                </button>
                <small>
                  Score {row.score.toFixed(3)} ·{" "}
                  {(row.channels || []).join(", ")}
                </small>
              </li>
            ))}
          </ol>
        </aside>
      </section>
      {!!recommendedTests.length && (
        <section className="test-recommendations">
          <h2>Tests to inspect</h2>
          <p>
            Test files ranked by the same evidence model; this does not
            establish runtime coverage.
          </p>
          {recommendedTests.map((row) => (
            <button
              className="secondary"
              key={row.path}
              onClick={() => setSelected(row.path)}
            >
              {row.path} ↗
            </button>
          ))}
        </section>
      )}
      {candidate && (
        <section className="evidence-panel">
          <h2>Evidence: {candidate.path}</h2>
          <p>
            Cutoff:{" "}
            <code>{result.evidence_cutoff || result.graph_revision}</code>
          </p>
          <SymbolSource
            key={candidate.path}
            result={result}
            path={candidate.path}
          />
          <EvidenceSummary
            key={candidate.path}
            result={result}
            candidate={candidate}
          />
          <h3>Static import path</h3>
          <p>
            {candidate.evidence?.import_path?.join(" → ") ||
              "No resolved import path within three hops."}
          </p>
          <h3>Past co-change commits</h3>
          {candidate.evidence?.past_commits?.length ? (
            <ul>
              {candidate.evidence.past_commits.map((sha) => (
                <li key={sha}>
                  <a
                    href={`https://github.com/${result.repo}/commit/${sha}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {sha}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p>No qualifying past co-change found.</p>
          )}
          <details>
            <summary>Feature values</summary>
            <pre>{JSON.stringify(candidate.features, null, 2)}</pre>
          </details>
        </section>
      )}
    </section>
  );
}
