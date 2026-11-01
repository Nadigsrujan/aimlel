/** Choose only a graph whose repository and snapshot match the visible result. */
export function displaySnapshot(result, current, loaded) {
  if (!current) return null;
  if (
    !result ||
    result.repo !== current.repo ||
    result.graph_revision === current.revision
  )
    return current;
  if (
    loaded &&
    loaded.repo === current.repo &&
    loaded.revision === result.graph_revision
  )
    return loaded;
  const nodes = result.entities || [],
    ids = new Map(nodes.map((n) => [n.legacy_id, n.id]));
  return {
    repo: result.repo,
    revision: result.graph_revision,
    nodes,
    edges: (result.graph?.edges || [])
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({
        ...e,
        source: ids.get(e.source),
        target: ids.get(e.target),
      })),
    quality: {
      entities: nodes.length,
      unresolved_edges: Math.max(
        0,
        (result.relation_resolution?.calls || 0) -
          (result.relation_resolution?.resolved_calls || 0),
      ),
    },
    slice: true,
  };
}
