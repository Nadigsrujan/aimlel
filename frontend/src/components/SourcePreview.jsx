import React, { useEffect, useState } from "react";
import { api } from "../api/client.js";
export default function SourcePreview({
  repo,
  revision,
  path,
  start = 1,
  lines = 80,
}) {
  const [source, setSource] = useState(null),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    setSource(null);
    setError("");
    api(
      "/api/v1/source?" +
        new URLSearchParams({ repo, revision, path, start, lines }),
    )
      .then((v) => active && setSource(v))
      .catch((e) => active && setError(e.message));
    return () => {
      active = false;
    };
  }, [repo, revision, path, start, lines]);
  return (
    <details>
      <summary>Source at analyzed revision</summary>
      {error ? (
        <p role="alert">{error}</p>
      ) : source ? (
        <>
          <p>
            Lines {source.start}–{source.start + source.lines.length - 1} of{" "}
            {source.total_lines} ·{" "}
            <a
              href={`https://github.com/${repo}/blob/${revision}/${path}#L${source.start}`}
              target="_blank"
              rel="noreferrer"
            >
              Open pinned source ↗
            </a>
          </p>
          <pre>
            {source.lines
              .map(
                (line, i) => `${String(i + source.start).padStart(4)}  ${line}`,
              )
              .join("\n")}
          </pre>
        </>
      ) : (
        <p>Loading pinned source…</p>
      )}
    </details>
  );
}
