import React, { useState } from "react";
import SourcePreview from "./SourcePreview.jsx";

export default function SymbolSource({ result, path, initialEntity = "" }) {
  const [selected, setSelected] = useState(initialEntity);
  const [kind, setKind] = useState("all");
  const symbols = (result.entities || [])
    .filter((node) => node.path === path && node.kind !== "file")
    .sort((a, b) => a.start - b.start);
  const node = symbols.find((item) => item.id === selected);
  const start = node ? Math.max(1, node.start - 2) : 1;
  const lines = node ? Math.min(200, Math.max(40, node.end - start + 4)) : 80;
  return (
    <div className="symbol-source">
      {!!symbols.length && (
        <div className="symbol-controls">
          <label>
            Source entity type
            <select
              value={kind}
              onChange={(event) => {
                setKind(event.target.value);
                setSelected("");
              }}
            >
              <option value="all">All symbols</option>
              <option value="class">Classes</option>
              <option value="function">Functions</option>
              <option value="test">Test-named symbols</option>
            </select>
          </label>
          <label>
            Symbol to inspect
            <select
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              <option value="">File overview</option>
              {symbols
                .filter((item) => kind === "all" || item.kind === kind)
                .slice(0, 200)
                .map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.qualified_name} · L{item.start}–{item.end}
                  </option>
                ))}
            </select>
          </label>
        </div>
      )}
      {node && (
        <p className="result-note">
          {node.kind} · <code>{node.qualified_name}</code> · lines {node.start}–
          {node.end}
        </p>
      )}
      <SourcePreview
        repo={result.repo}
        revision={result.graph_revision}
        path={path}
        start={start}
        lines={lines}
      />
    </div>
  );
}
