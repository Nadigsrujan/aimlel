import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";

export default function JobHistory({ onRetry }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [retrying, setRetrying] = useState("");
  useEffect(() => {
    let active = true,
      timer;
    async function refresh() {
      try {
        const value = await api("/api/v1/jobs");
        if (active) {
          setRows(value.slice(0, 10));
          setError("");
        }
      } catch (e) {
        if (active) setError(e.message);
      }
      if (active) timer = setTimeout(refresh, 3000);
    }
    refresh();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, []);
  async function retry(row) {
    setRetrying(row.job);
    try {
      onRetry(await api(`/api/v1/jobs/${row.job}/retry`, {}));
    } catch (e) {
      setError(e.message);
    } finally {
      setRetrying("");
    }
  }
  return (
    <section className="job-history">
      <div className="section-heading">
        <h3>Recent indexing jobs</h3>
        <span className="snapshot-badge">PERSISTED LOCALLY</span>
      </div>
      {error && <p role="alert">{error}</p>}
      {!rows.length && (
        <p className="result-note">
          Your indexing history will appear here. Active jobs reconnect after a
          page refresh.
        </p>
      )}
      {rows.map((row) => (
        <div className="job-row" key={row.job}>
          <div>
            <strong>{row.repo}</strong>
            <small>
              {row.progress?.stage || row.status} ·{" "}
              {row.progress?.elapsed_seconds || 0}s
            </small>
            {row.error && <p role="status">{row.error}</p>}
          </div>
          <span className={`job-state ${row.status}`}>{row.status}</span>
          {["failed", "cancelled"].includes(row.status) && (
            <button
              className="secondary"
              disabled={!!retrying}
              onClick={() => retry(row)}
            >
              {retrying === row.job ? "Retrying…" : "Retry ↗"}
            </button>
          )}
        </div>
      ))}
    </section>
  );
}
