import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
import ResearchInstrument from "./ResearchInstrument.jsx";
import FinalStudy from "./FinalStudy.jsx";
export default function ResearchPanel() {
  const [data, setData] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    function refresh() {
      api("/api/v1/research")
        .then((value) => {
          if (active) {
            setData(value);
            setError("");
          }
        })
        .catch((e) => active && setError(e.message));
    }
    refresh();
    const timer = setInterval(refresh, 15000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);
  if (error)
    return (
      <div className="alert" role="alert">
        {error}
      </div>
    );
  if (!data)
    return (
      <section className="analysis-panel" role="status">
        Loading experiment provenance…
      </section>
    );
  const stages = [
    [
      "Development data",
      `${data.ready_repositories} / ${data.development_repositories} materialized`,
      data.ready_repositories === data.development_repositories,
    ],
    [
      "Semantic snapshots",
      `${data.semantic_snapshots} revision indexes`,
      data.semantic_snapshots > 0,
    ],
    [
      "Learned checkpoint",
      data.checkpoint_available ? "Installed" : "Training pending",
      data.checkpoint_available,
    ],
    [
      "Protocol freeze",
      data.frozen ? "Frozen" : "Validation decisions pending",
      data.frozen,
    ],
    [
      "Held-out study",
      data.held_out_evaluated ? "Recorded" : "Sealed until freeze",
      data.held_out_evaluated,
    ],
  ];
  return (
    <section className="research-panel">
      <div className="section-heading">
        <span className="section-tag">RESEARCH / REPRODUCIBILITY</span>
        <span className="snapshot-badge">
          7 train · 2 validation · 3 held out
        </span>
      </div>
      <h2>Evidence for the model, too.</h2>
      <p className="result-note">
        Follow the experiment from pinned data to a frozen evaluation. Metrics
        appear only when their extraction protocol matches the current
        application.
      </p>
      <div className="research-stages">
        {stages.map(([title, value, ready], i) => (
          <div key={title}>
            <span className={ready ? "stage-ready" : "stage-pending"}>
              {ready ? "✓" : String(i + 1).padStart(2, "0")}
            </span>
            <strong>{title}</strong>
            <small>{value}</small>
          </div>
        ))}
      </div>
      <div className="research-grid">
        <section>
          <h3>Validation ranking</h3>
          <p className="result-note">
            Repository-macro Recall@5 · development samples
          </p>
          {data.experiment_compatible ? (
            Object.entries(data.metrics)
              .sort((a, b) => b[1] - a[1])
              .map(([name, value]) => (
                <div className="benchmark-row" key={name}>
                  <div>
                    <span>{name}</span>
                    <strong>{(value * 100).toFixed(1)}%</strong>
                  </div>
                  <div className="benchmark-track">
                    <i
                      style={{
                        width: Math.max(0, Math.min(100, value * 100)) + "%",
                      }}
                    />
                  </div>
                </div>
              ))
          ) : (
            <div className="research-empty">
              <strong>Previous experiment needs a rerun.</strong>
              <p>
                The recorded experiment used extraction version{" "}
                {data.experiment_parser_version || "unknown"}. The current
                version is {data.parser_version}; its numbers are withheld from
                this comparison.
              </p>
            </div>
          )}
        </section>
        <section>
          <h3>Experiment provenance</h3>
          <dl>
            <dt>Training queries</dt>
            <dd>{data.samples.train_queries}</dd>
            <dt>Checkpoint selection</dt>
            <dd>{data.samples.selection_queries}</dd>
            <dt>Calibration queries</dt>
            <dd>{data.samples.calibration_queries}</dd>
            <dt>Extraction version</dt>
            <dd>{data.parser_version}</dd>
            <dt>Original development report</dt>
            <dd>{data.status}</dd>
          </dl>
          <h3>Reported limitations</h3>
          <ul className="research-limits">
            {data.limitations.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
          <p className="result-note">
            The success gate compares frozen fusion ranking with the strongest
            validation-selected baseline on unseen projects. A negative result
            remains part of the report.
          </p>
        </section>
      </div>
      <ResearchInstrument />
      <FinalStudy />
    </section>
  );
}
