import React from "react";
export default function RankFlow({ left, right, onSelect }) {
  const a = left.results[0],
    b = right.results[0],
    ra = new Map(a.candidates.map((r, i) => [r.path, i + 1])),
    rb = new Map(b.candidates.map((r, i) => [r.path, i + 1]));
  const paths = [
      ...new Set(
        [...a.candidates.slice(0, 10), ...b.candidates.slice(0, 10)].map(
          (r) => r.path,
        ),
      ),
    ],
    la = [...paths].sort((x, y) => (ra.get(x) || 101) - (ra.get(y) || 101)),
    lb = [...paths].sort((x, y) => (rb.get(x) || 101) - (rb.get(y) || 101)),
    height = paths.length * 28 + 55;
  const same = a.graph_revision === b.graph_revision && a.seed === b.seed;
  return (
    <section className="rank-flow">
      <h4>Measured rank-flow · saved forecast comparison</h4>
      <p className="result-note">
        {same
          ? "Same snapshot and inspected seed."
          : "Different seed or snapshot — descriptive comparison only."}{" "}
        First seed in each saved run: {a.seed} / {b.seed}. Union of each run’s
        first ten targets; labels retain actual cached ranks. Line position
        orders the displayed subset, not a probability.
      </p>
      <svg
        viewBox={`0 0 850 ${height}`}
        role="img"
        aria-label="Measured file rank changes between saved forecasts"
      >
        {paths.map((path) => {
          const y1 = 30 + la.indexOf(path) * 28,
            y2 = 30 + lb.indexOf(path) * 28,
            short = path.length > 29 ? "…" + path.slice(-28) : path;
          return (
            <g key={path} onClick={() => onSelect(path)}>
              <path
                d={`M 300 ${y1} C 390 ${y1}, 460 ${y2}, 550 ${y2}`}
                fill="none"
                stroke={
                  (ra.get(path) || 101) - (rb.get(path) || 101) >= 0
                    ? "#65d6ad"
                    : "#b69cff"
                }
                strokeWidth="1.6"
                opacity=".7"
              >
                <title>
                  {path}: rank {ra.get(path) || ">100"} →{" "}
                  {rb.get(path) || ">100"}
                </title>
              </path>
              <text x="8" y={y1 + 4}>
                {ra.get(path) || ">100"} · {short}
              </text>
              <text x="560" y={y2 + 4}>
                {rb.get(path) || ">100"} · {short}
              </text>
            </g>
          );
        })}
      </svg>
    </section>
  );
}
