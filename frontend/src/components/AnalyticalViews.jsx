import React, { useMemo, useState, Suspense } from "react";
import { Canvas } from "@react-three/fiber";
import { CanvasBoundary } from "./CodeMetropolis.jsx";
import { OrbitControls, Line, Html } from "@react-three/drei";
const testPath = (p) =>
  /(^|\/)tests?(\/|$)|(^|\/)test_[^/]*\.py$|_test\.py$/.test(p);
function Stage({ children }) {
  const [failed, setFailed] = useState(() => {
    try {
      return !document.createElement("canvas").getContext("webgl2");
    } catch {
      return true;
    }
  });
  return failed ? (
    <p>WebGL unavailable. Use the data list below.</p>
  ) : (
    <CanvasBoundary>
      <div className="analytical-stage">
        <Canvas
          frameloop="demand"
          dpr={[1, 1.5]}
          camera={{ position: [18, 22, 32], fov: 48 }}
          onCreated={({ gl }) =>
            gl.domElement.addEventListener("webglcontextlost", () =>
              setFailed(true),
            )
          }
        >
          <color attach="background" args={["#070b13"]} />
          <ambientLight intensity={1.6} />
          <directionalLight position={[10, 25, 15]} intensity={2} />
          <Suspense fallback={null}>{children}</Suspense>
          <OrbitControls makeDefault />
        </Canvas>
      </div>
    </CanvasBoundary>
  );
}
export function TestStars({ graph, result, onSelect }) {
  const [selected, setSelected] = useState("");
  const rows = (result?.recommended_tests || []).filter((r) =>
    testPath(r.path),
  );
  const sources = (result?.candidates || [])
    .filter((r) => !testPath(r.path))
    .slice(0, 8);
  const nodes = [
    ...sources.map((r, i) => ({
      ...r,
      test: false,
      x: Math.cos((i / sources.length) * Math.PI * 2) * 5,
      z: Math.sin((i / sources.length) * Math.PI * 2) * 5,
    })),
    ...rows.map((r, i) => ({
      ...r,
      test: true,
      x: Math.cos((i / rows.length) * Math.PI * 2) * 13,
      z: Math.sin((i / rows.length) * Math.PI * 2) * 13,
    })),
  ];
  const byPath = new Map(nodes.map((n) => [n.path, n])),
    ids = new Map(
      graph.nodes.filter((n) => n.kind === "file").map((n) => [n.id, n.path]),
    );
  const edges = graph.edges.filter(
    (e) =>
      e.relation === "IMPORTS" &&
      byPath.has(ids.get(e.source)) &&
      byPath.has(ids.get(e.target)) &&
      testPath(ids.get(e.source)) !== testPath(ids.get(e.target)),
  );
  if (!result)
    return (
      <p>
        Forecast a change to populate the constellation from actual
        recommendations.
      </p>
    );
  return (
    <section>
      <h3>Test Constellation · static associations</h3>
      <p className="result-note">
        Green satellites are recommended test files. Cyan nodes are ranked
        source files. A tether exists only for a resolved static import; an
        import is not measured coverage. No tests were executed.
      </p>
      <Stage>
        {nodes.map((n) => (
          <group key={n.path} position={[n.x, n.test ? 2 : 0, n.z]}>
            <mesh
              onClick={() => {
                setSelected(n.path);
                onSelect(n.path);
              }}
            >
              <icosahedronGeometry args={[n.test ? 0.35 : 0.65, 1]} />
              <meshStandardMaterial
                color={
                  selected === n.path
                    ? "#efab69"
                    : n.test
                      ? "#65d6ad"
                      : "#50d9e8"
                }
                emissive={n.test ? "#143c2c" : "#14374a"}
              />
            </mesh>
            {selected === n.path && (
              <Html center position={[0, 1.5, 0]}>
                <span className="city-label">{n.path}</span>
              </Html>
            )}
          </group>
        ))}
        {edges.map((e, i) => {
          const a = byPath.get(ids.get(e.source)),
            b = byPath.get(ids.get(e.target));
          return (
            <Line
              key={i}
              points={[
                [a.x, a.test ? 2 : 0, a.z],
                [b.x, b.test ? 2 : 0, b.z],
              ]}
              color="#65d6ad"
              lineWidth={1}
            />
          );
        })}
      </Stage>
      <p>
        {nodes.length} displayed files · {edges.length} verified import tethers
        · disconnected satellites retain ranking evidence without invented
        coverage links.
      </p>
      <ul>
        {nodes.map((n) => (
          <li key={n.path}>
            <button
              className="link"
              onClick={() => {
                setSelected(n.path);
                onSelect(n.path);
              }}
            >
              {n.path}
            </button>{" "}
            · {n.test ? "recommended test" : "source"} · ranking score{" "}
            {n.score.toFixed(3)}
          </li>
        ))}
      </ul>
    </section>
  );
}
export function CodeMRI({ graph, path, onEntity }) {
  const [depth, setDepth] = useState(0),
    [selected, setSelected] = useState("");
  const nodes = graph.nodes.filter((n) => n.path === path),
    root = nodes.find((n) => n.kind === "file"),
    levels = new Map(root ? [[root.id, 0]] : []);
  const edges = graph.edges.filter((e) => e.relation === "CONTAINS");
  for (let pass = 0; pass < 20; pass++) {
    let changed = false;
    for (const e of edges) {
      if (levels.has(e.source) && !levels.has(e.target)) {
        levels.set(e.target, levels.get(e.source) + 1);
        changed = true;
      }
    }
    if (!changed) break;
  }
  const maximum = Math.max(0, ...levels.values()),
    visible = nodes
      .filter((n) => (levels.get(n.id) || 0) <= depth)
      .slice(0, 200);
  const positions = new Map(
    visible.map((n) => {
      const layer = levels.get(n.id) || 0,
        index = visible
          .filter((v) => (levels.get(v.id) || 0) === layer)
          .indexOf(n);
      return [
        n.id,
        [(index % 8) * 2 - 7, layer * 3 + 0.4, Math.floor(index / 8) * 2 - 3],
      ];
    }),
  );
  const relations = graph.edges
    .filter(
      (e) =>
        positions.has(e.source) &&
        positions.has(e.target) &&
        ["CALLS", "INHERITS"].includes(e.relation),
    )
    .slice(0, 50);
  return (
    <section>
      <h3>Code MRI · source hierarchy cutaway</h3>
      <p>
        {path} · {nodes.length} real entities. Layer is actual CONTAINS depth;
        visibility limit 200 entities.
      </p>
      <label>
        Hierarchy depth {depth} / {maximum}
        <input
          type="range"
          min="0"
          max={maximum}
          value={Math.min(depth, maximum)}
          onChange={(e) => setDepth(+e.target.value)}
        />
      </label>
      <Stage>
        {relations.map((e, i) => (
          <Line
            key={"relation-" + i}
            points={[positions.get(e.source), positions.get(e.target)]}
            color={e.relation === "CALLS" ? "#50d9e8" : "#b69cff"}
            lineWidth={1.5}
          />
        ))}
        {visible.map((n, i) => {
          const layer = levels.get(n.id) || 0,
            layerNodes = visible.filter(
              (v) => (levels.get(v.id) || 0) === layer,
            ),
            index = layerNodes.indexOf(n);
          return (
            <group
              key={n.id}
              position={[
                (index % 8) * 2 - 7,
                layer * 3,
                Math.floor(index / 8) * 2 - 3,
              ]}
            >
              <mesh
                onClick={() => {
                  setSelected(n.id);
                  onEntity(n.id);
                }}
              >
                <boxGeometry
                  args={[
                    n.kind === "file" ? 12 : 1.4,
                    0.3,
                    n.kind === "file" ? 10 : 1.4,
                  ]}
                />
                <meshStandardMaterial
                  color={
                    n.id === selected
                      ? "#efab69"
                      : n.kind === "class"
                        ? "#b69cff"
                        : n.kind === "file"
                          ? "#243d55"
                          : "#50d9e8"
                  }
                />
              </mesh>
              {n.id === selected && (
                <Html center position={[0, 1, 0]}>
                  <span className="city-label">
                    {n.qualified_name || n.path} · L{n.start || 1}–{n.end || 1}
                  </span>
                </Html>
              )}
            </group>
          );
        })}
      </Stage>
      <p className="result-note">
        Dependency X-ray: up to 50 conservative same-file CALLS / INHERITS
        relations touching visible layers. Direction and exact source lines are
        listed below; unresolved dynamic calls are not drawn.
      </p>
      <ul>
        {relations.map((e, i) => (
          <li key={i}>
            <button className="link" onClick={() => onEntity(e.source)}>
              {nodes.find((n) => n.id === e.source)?.qualified_name} →{" "}
              {e.relation} →{" "}
              {nodes.find((n) => n.id === e.target)?.qualified_name}
            </button>{" "}
            · {e.resolution}{" "}
            {e.line && (
              <a
                href={`https://github.com/${graph.repo}/blob/${graph.revision}/${path}#L${e.line}`}
                target="_blank"
                rel="noreferrer"
              >
                source L{e.line}
              </a>
            )}
          </li>
        ))}
      </ul>
      <ul>
        {visible.map((n) => (
          <li key={n.id}>
            <button
              className="link"
              onClick={() => {
                setSelected(n.id);
                onEntity(n.id);
              }}
            >
              {n.kind} · {n.qualified_name || n.path} · L{n.start || 1}–
              {n.end || 1}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
export function EvolutionSculpture({ history, onCommit }) {
  const [mode, setMode] = useState("corridor"),
    [selected, setSelected] = useState("");
  const rows = [...history].reverse().slice(-40),
    a = rows.map((r, i) => {
      const t = i * 0.5,
        rad = 2 + Math.log1p(r.added_lines + r.deleted_lines);
      return [
        Math.cos(t) * rad,
        (i - rows.length / 2) * 0.8,
        Math.sin(t) * rad,
      ];
    }),
    b = rows.map((r, i) => {
      const t = i * 0.5 + Math.PI,
        rad = 2 + Math.log1p(r.observed_file_pairs);
      return [
        Math.cos(t) * rad,
        (i - rows.length / 2) * 0.8,
        Math.sin(t) * rad,
      ];
    });
  return (
    <section>
      <h3>{mode === "dna" ? "Commit DNA" : "Temporal Rift Corridor"}</h3>
      <div className="filters">
        <button
          className="secondary"
          onClick={() => setMode(mode === "dna" ? "corridor" : "dna")}
        >
          {mode === "dna"
            ? "Show timeline layers"
            : "Show empirical double helix"}
        </button>
      </div>
      <p className="result-note">
        Up to 40 actual first-parent commits, oldest → newest. Structural strand
        radius = 2 + ln(1 + added/deleted Python lines); history strand radius =
        2 + ln(1 + changed-file pairs). A bridge is one observed commit, not a
        causal edge or the AST-filtered training label.
      </p>
      <Stage>
        {mode === "dna" ? (
          <>
            {a.length > 1 && <Line points={a} color="#50d9e8" />}
            {b.length > 1 && <Line points={b} color="#b69cff" />}
            {rows.map((r, i) => (
              <group key={r.revision}>
                <Line
                  points={[a[i], b[i]]}
                  color={r.revision === selected ? "#efab69" : "#33465f"}
                />
                <mesh
                  position={a[i]}
                  onClick={() => {
                    setSelected(r.revision);
                    onCommit(r.revision);
                  }}
                >
                  <sphereGeometry args={[0.22, 8, 8]} />
                  <meshStandardMaterial color="#50d9e8" />
                </mesh>
              </group>
            ))}
          </>
        ) : (
          rows.map((r, i) => (
            <mesh
              key={r.revision}
              position={[(i - rows.length / 2) * 0.85, 0, 0]}
              onClick={() => {
                setSelected(r.revision);
                onCommit(r.revision);
              }}
            >
              <boxGeometry
                args={[
                  0.35,
                  1 + Math.log1p(r.added_lines + r.deleted_lines),
                  3 + Math.log1p(r.changed_python_files),
                ]}
              />
              <meshStandardMaterial
                color={r.revision === selected ? "#efab69" : "#6587a9"}
                transparent
                opacity={0.65}
              />
            </mesh>
          ))
        )}
      </Stage>
      {selected && (
        <p>
          Selected commit {selected}. Use the conventional commit list below to
          start its parent-snapshot forecast; observed modified-file labels stay
          hidden until a completed run is revealed.
        </p>
      )}
    </section>
  );
}
export function RiskTerrain({ graph, result, onSelect }) {
  const [metric, setMetric] = useState("mean");
  const islands = useMemo(() => {
    const groups = new Map();
    for (const row of result?.candidates || []) {
      const group = row.path.split("/").slice(0, -1).join("/") || "root";
      if (!groups.has(group)) groups.set(group, []);
      groups.get(group).push(row);
    }
    return [...groups]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([name, rows]) => ({
        name,
        rows,
        sum: rows.reduce((v, r) => v + r.score, 0),
        count: rows.length,
        total: graph.nodes.filter(
          (n) =>
            n.kind === "file" &&
            (n.path.split("/").slice(0, -1).join("/") || "root") === name,
        ).length,
      }));
  }, [graph, result]);
  const values = islands.map((r) =>
      metric === "count" ? r.count : metric === "sum" ? r.sum : r.sum / r.count,
    ),
    maximum = Math.max(0.001, ...values),
    side = Math.ceil(Math.sqrt(islands.length));
  return (
    <section>
      <h3>Risk Topography · module inspection burden</h3>
      <p className="result-note">
        Aggregated over the saved visible ranking, not the whole repository.
        Height = 1 + 10 × metric / displayed maximum. Footprint width = 1 +
        √module file count. Scores are uncalibrated, so sums are inspection
        indicators, not failure probabilities.
      </p>
      <label>
        Aggregate metric
        <select value={metric} onChange={(e) => setMetric(e.target.value)}>
          <option value="mean">Mean model score</option>
          <option value="sum">Sum model scores</option>
          <option value="count">Ranked file count</option>
        </select>
      </label>
      {!islands.length ? (
        <p>No forecast yet; no risk terrain is drawn.</p>
      ) : (
        <Stage>
          {islands.map((r, i) => {
            const h = 1 + (10 * values[i]) / maximum,
              w = Math.min(6, 1 + Math.sqrt(r.total));
            return (
              <group
                key={r.name}
                position={[
                  ((i % side) - side / 2) * 8,
                  h / 2,
                  Math.floor(i / side) * 8,
                ]}
              >
                <mesh onClick={() => onSelect(r.rows[0].path)}>
                  <cylinderGeometry args={[w / 2, w / 2 + 0.4, h, 6]} />
                  <meshStandardMaterial color="#b68b65" roughness={0.7} />
                </mesh>
                <Html center position={[0, h / 2 + 1, 0]}>
                  <span className="district-label">{r.name}</span>
                </Html>
              </group>
            );
          })}
        </Stage>
      )}
      <div className="study-table">
        <table>
          <thead>
            <tr>
              <th>Module</th>
              <th>Ranked / {graph.slice ? "graph slice" : "all"} files</th>
              <th>Mean score</th>
              <th>Sum score</th>
              <th>Height</th>
            </tr>
          </thead>
          <tbody>
            {islands.map((r, i) => (
              <tr key={r.name}>
                <td>
                  <button
                    className="link"
                    onClick={() => onSelect(r.rows[0].path)}
                  >
                    {r.name}
                  </button>
                </td>
                <td>
                  {r.count} / {r.total}
                </td>
                <td>{(r.sum / r.count).toFixed(3)}</td>
                <td>{r.sum.toFixed(3)}</td>
                <td>{(1 + (10 * values[i]) / maximum).toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
