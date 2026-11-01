import React, { useState, useEffect } from "react";
import { api } from "../api/client.js";
function Curve({ rows, field, label, zero = false }) {
  const values = rows.map((r) => r[field]),
    min = zero ? 0 : Math.min(...values),
    max = Math.max(...values, min + 0.001),
    width = 620,
    height = 150;
  const point = (r, i) =>
    `${50 + (i / Math.max(1, rows.length - 1)) * (width - 70)},${height - 25 - ((r[field] - min) / (max - min)) * (height - 45)}`;
  return (
    <figure className="training-curve">
      <figcaption>{label}</figcaption>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label} by recorded training epoch`}
      >
        <line x1="50" x2="600" y1="125" y2="125" stroke="#38506b" />
        <line x1="50" x2="50" y1="20" y2="125" stroke="#38506b" />
        <text x="4" y="25">
          {max.toFixed(3)}
        </text>
        <text x="4" y="125">
          {min.toFixed(3)}
        </text>
        <polyline
          points={rows.map(point).join(" ")}
          fill="none"
          stroke="#50d9e8"
          strokeWidth="2"
        />
        {rows.map((r, i) => {
          const [x, y] = point(r, i).split(",");
          return (
            <circle key={i} cx={x} cy={y} r="3" fill="#b69cff">
              <title>
                Epoch {r.epoch}: {r[field].toFixed(6)}
              </title>
            </circle>
          );
        })}
        <text x="50" y="147">
          Epoch {rows[0]?.epoch}
        </text>
        <text x="550" y="147">
          {rows.at(-1)?.epoch}
        </text>
      </svg>
    </figure>
  );
}
export default function ResearchInstrument() {
  const [data, setData] = useState(null),
    [variant, setVariant] = useState("heterogeneous"),
    [metric, setMetric] = useState("recall_at_5"),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api("/api/v1/observatory/research")
      .then((v) => active && setData(v))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, []);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p>Loading recorded training instrument…</p>;
  const history =
    variant === "heterogeneous"
      ? data.history
      : Array.isArray(data.ablation_history[variant.replace("-only", "")])
        ? data.ablation_history[variant.replace("-only", "")]
        : data.ablation_history[variant.replace("-only", "")]?.history;
  const cases = data.comparison[variant] || [],
    full = data.comparison.heterogeneous || [],
    latencies = cases
      .map((c) => c.inference_seconds)
      .filter(Number.isFinite)
      .sort((a, b) => a - b);
  return (
    <section className="research-instrument">
      <div className="section-heading">
        <h3>Model Ablation Observatory</h3>
        <span className="snapshot-badge">RECORDED VALIDATION DATA</span>
      </div>
      <p className="result-note">
        Fixed development query pools. These charts are actual training history
        and validation measurements, distinct from the held-out study shown
        below.
      </p>
      <div className="filters">
        <label>
          Measured variant
          <select value={variant} onChange={(e) => setVariant(e.target.value)}>
            {Object.keys(data.comparison).map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Case metric
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            {[
              "recall_at_5",
              "recall_at_10",
              "ndcg_at_10",
              "map_at_10",
              "mrr",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
      </div>
      {history?.length ? (
        <div className="research-grid">
          <Curve rows={history} field="loss" label="Recorded training loss" />
          <Curve
            rows={history}
            field="validation_macro_recall_at_5"
            label="Validation repository-macro Recall@5"
            zero
          />
        </div>
      ) : (
        <p>No recorded epoch history for this non-neural comparator.</p>
      )}
      <p>
        Measured scoring p95:{" "}
        {latencies.length
          ? (latencies[Math.ceil(latencies.length * 0.95) - 1] * 1000).toFixed(
              1,
            ) + " ms"
          : "unavailable"}{" "}
        across {latencies.length} validation queries. Excludes ingestion,
        embeddings, feature preparation and browser rendering.
      </p>
      <h4>Paired case differences · full fusion vs {variant}</h4>
      <p className="result-note">
        Each row is matched by repository and commit. Positive delta favors full
        fusion. Candidate ranks were not saved in this report; these are
        measured metric differences.
      </p>
      <div className="study-table">
        <table>
          <thead>
            <tr>
              <th>Validation case</th>
              <th>Full</th>
              <th>Selected</th>
              <th>Difference</th>
            </tr>
          </thead>
          <tbody>
            {full.map((c) => {
              const other = cases.find(
                (r) => r.repo === c.repo && r.commit === c.commit,
              );
              if (!other) return null;
              const delta = c[metric] - other[metric];
              return (
                <tr key={c.repo + c.commit}>
                  <td>
                    <a
                      href={`https://github.com/${c.repo}/commit/${c.commit}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {c.repo} · {c.commit.slice(0, 8)}
                    </a>
                  </td>
                  <td>{c[metric]?.toFixed(3)}</td>
                  <td>{other[metric]?.toFixed(3)}</td>
                  <td>
                    <span
                      className={
                        delta >= 0 ? "positive-delta" : "negative-delta"
                      }
                    >
                      {delta >= 0 ? "+" : ""}
                      {delta.toFixed(3)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <h4>Error-case explorer · lowest {metric} first</h4>
      <ol>
        {[...cases]
          .sort((a, b) => a[metric] - b[metric])
          .slice(0, 5)
          .map((c) => (
            <li key={c.repo + c.commit}>
              <a
                href={`https://github.com/${c.repo}/commit/${c.commit}`}
                target="_blank"
                rel="noreferrer"
              >
                {c.repo} / {c.commit.slice(0, 10)}
              </a>{" "}
              · {metric}: {c[metric]?.toFixed(3)} · candidate ceiling:{" "}
              {c.candidate_ceiling}
            </li>
          ))}
      </ol>
      <details>
        <summary>Artifact lineage & confidence intervals</summary>
        <p>
          Report SHA-256: <code>{data.artifact_sha256}</code>
        </p>
        <pre>{JSON.stringify(data.confidence_intervals[variant], null, 2)}</pre>
        <pre>{JSON.stringify(data.metadata, null, 2)}</pre>
      </details>
    </section>
  );
}
