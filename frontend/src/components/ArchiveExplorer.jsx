import React, { useState } from "react";
import CodeMetropolis from "./CodeMetropolis.jsx";
export default function ArchiveExplorer() {
  const [graph, setGraph] = useState(null),
    [selected, setSelected] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [result, setResult] = useState(null);
  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    if (file.size > 20 * 1024 * 1024) {
      setError("Compressed ZIP limit is 20 MiB");
      return;
    }
    setBusy(true);
    try {
      const response = await fetch("/api/v1/observatory/archives", {
        method: "POST",
        headers: { "Content-Type": "application/zip" },
        body: file,
      });
      const value = await response.json();
      if (!response.ok) throw new Error(value.detail || "Archive rejected");
      setGraph(value);
      setResult(null);
      setSelected(value.nodes.find((n) => n.kind === "file")?.path || "");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="archive-explorer">
      <h3>Or inspect a Python source ZIP</h3>
      <p>
        Source snapshot with a clearly labeled static/directory baseline; no Git
        evolution or learned forecast. Limits: 20 MiB compressed, 50 MiB
        expanded, 5000 entries. Unsafe paths, symlinks and compression bombs are
        rejected; source is never executed.
      </p>
      <label>
        Local ZIP
        <input
          type="file"
          accept=".zip,application/zip"
          disabled={busy}
          onChange={upload}
        />
      </label>
      {busy && <p role="status">Parsing archive source…</p>}
      {error && <p role="alert">{error}</p>}
      {graph && (
        <>
          <button
            className="primary"
            disabled={busy || !selected}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                const response = await fetch(
                  `/api/v1/observatory/archives/${graph.revision}/forecast`,
                  {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ seed: selected }),
                  },
                );
                const value = await response.json();
                if (!response.ok)
                  throw new Error(value.detail || "Baseline failed");
                setResult(value);
              } catch (e) {
                setError(e.message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Forecast selected file · static baseline
          </button>
          {result && (
            <>
              <p>
                <strong>{result.model_status}</strong> · {result.limitation}
              </p>
              <ol>
                {result.candidates.slice(0, 10).map((r) => (
                  <li key={r.path}>
                    <button
                      className="link"
                      onClick={() => setSelected(r.path)}
                    >
                      {r.path}
                    </button>{" "}
                    · score {r.score.toFixed(3)} ·{" "}
                    {r.evidence.import_path.join(" → ") ||
                      "No resolved import path"}
                  </li>
                ))}
              </ol>
            </>
          )}
          <CodeMetropolis
            result={result}
            graph={graph}
            selected={selected}
            onSelect={setSelected}
          />
          <p>
            Content SHA-256: <code>{graph.revision}</code>
          </p>
          <p>Parser failures: {graph.quality.parse_failures.length}</p>
          <h4>{selected}</h4>
          <pre className="archive-source">
            {graph.sources[selected]
              ?.split("\n")
              .slice(0, 200)
              .map((line, i) => `${String(i + 1).padStart(4)}  ${line}`)
              .join("\n")}
          </pre>
        </>
      )}
    </section>
  );
}
