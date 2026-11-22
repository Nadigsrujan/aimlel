import test from "node:test";
import assert from "node:assert/strict";
import { displaySnapshot } from "./snapshot.js";
const current = { repo: "p/r", revision: "current", nodes: [], edges: [] };
const result = {
  repo: "p/r",
  graph_revision: "past",
  entities: [
    { id: "new-a", legacy_id: "a" },
    { id: "new-b", legacy_id: "b" },
  ],
  graph: {
    edges: [
      { source: "a", target: "b", relation: "CALLS" },
      { source: "a", target: "external", relation: "IMPORTS" },
    ],
  },
};
test("initial loading and absent result cannot select a null cached graph", () => {
  assert.equal(displaySnapshot(null, null, null), null);
  assert.equal(displaySnapshot(null, current, null), current);
  assert.equal(displaySnapshot(undefined, current, undefined), current);
});
test("matching current result retains the full source graph", () =>
  assert.equal(
    displaySnapshot({ ...result, graph_revision: "current" }, current, null),
    current,
  ));
test("historical slice maps stable IDs and drops edges without verified targets", () => {
  const graph = displaySnapshot(result, current, null);
  assert.equal(graph.revision, "past");
  assert.equal(graph.slice, true);
  assert.deepEqual(graph.edges, [
    { source: "new-a", target: "new-b", relation: "CALLS" },
  ]);
});
test("historical cache must match repository and exact result SHA", () => {
  const loaded = { repo: "p/r", revision: "past", nodes: [], edges: [] };
  assert.equal(displaySnapshot(result, current, loaded), loaded);
  assert.equal(
    displaySnapshot(result, current, { ...loaded, revision: "another" }).slice,
    true,
  );
  assert.equal(
    displaySnapshot(result, current, { ...loaded, repo: "different/repo" })
      .slice,
    true,
  );
  assert.equal(
    displaySnapshot({ ...result, repo: "different/repo" }, current, loaded),
    current,
  );
});
