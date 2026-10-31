export function graphView(result, candidates, selected) {
  const evidence = candidates.find(candidate => candidate.path === selected)?.evidence?.import_path || [];
  const paths = [...new Set([result.seed, ...candidates.map(row => row.path), ...evidence])];
  const nodes = paths.map((path, index) => ({
    id: path,
    position: {x: index === 0 ? 30 : 370, y: index === 0 ? 180 : (index - 1) * 85},
    data: {label: path},
    className: index === 0 ? 'seed-node' : 'candidate-node',
  }));
  const edges = evidence.slice(1).map((path, index) => ({
    id: `import-${index}`, source: evidence[index], target: path,
    label: 'static import (either direction)',
  }));
  return {nodes, edges};
}
