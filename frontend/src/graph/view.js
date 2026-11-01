export function graphView(result, candidates, selected) {
  const evidence =
    candidates.find((candidate) => candidate.path === selected)?.evidence
      ?.import_path || [];
  const paths = [
    ...new Set([
      result.seed,
      ...candidates.map((row) => row.path),
      ...evidence,
    ]),
  ];
  const nodes = paths.map((path, index) => ({
    id: path,
    position: {
      x: index === 0 ? 20 : 220 + ((index - 1) % 2) * 210,
      y: index === 0 ? 180 : Math.floor((index - 1) / 2) * 100,
    },
    data: { label: path },
    className: index === 0 ? "seed-node" : "candidate-node",
    selected: path === selected,
  }));
  const edges = evidence.slice(1).map((path, index) => ({
    id: `import-${index}`,
    source: evidence[index],
    target: path,
    label: "static import (either direction)",
  }));
  return { nodes, edges };
}
