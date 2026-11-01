import React, { useState } from "react";
import { api } from "../api/client.js";

export default function EvidenceSummary({ result, candidate }) {
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [gemini, setGemini] = useState(false);
  async function load() {
    setBusy(true);
    setError("");
    try {
      setSummary(
        await api("/api/v1/explanations", {
          repo: result.repo,
          seed: result.seed,
          target: result.target_commit || "",
          ranker: result.ranker,
          candidate: candidate.path,
          use_gemini: gemini,
        }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="evidence-summary">
      <div className="section-heading">
        <h3>Why inspect this file?</h3>
        <span className="snapshot-badge">CITATION BOUND</span>
      </div>
      <p className="result-note">
        A concise reading of the retrieved evidence, with links to verify each
        statement.
      </p>
      <label className="optional-provider">
        <input
          type="checkbox"
          checked={gemini}
          onChange={(e) => setGemini(e.target.checked)}
        />
        Use configured Gemini to select evidence
      </label>
      {gemini && (
        <p className="result-note">
          Sends repository paths and evidence metadata to Google. Source code is
          excluded. Falls back locally if unavailable.
        </p>
      )}
      <button className="secondary" disabled={busy} onClick={load}>
        {busy ? "Reading evidence…" : "Explain recommendation ↗"}
      </button>
      {error && <p role="alert">{error}</p>}
      {summary && (
        <div aria-live="polite">
          <small>{summary.status}</small>
          <ul>
            {summary.statements.map((item) => (
              <li key={item.id}>
                {item.text}{" "}
                {item.url && (
                  <a href={item.url} target="_blank" rel="noreferrer">
                    Verify ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
          <p className="result-note">{summary.limitation}</p>
        </div>
      )}
    </section>
  );
}
