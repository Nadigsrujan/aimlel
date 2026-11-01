import React, { useMemo, useRef, useEffect, useState, Suspense } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Line, Html } from "@react-three/drei";
import * as THREE from "three";

function spiral(index) {
  if (!index) return [0, 0];
  const ring = Math.ceil((Math.sqrt(index + 1) - 1) / 2),
    side = ring * 2,
    offset = (2 * ring + 1) ** 2 - 1 - index;
  if (offset < side) return [ring - offset, -ring];
  if (offset < side * 2) return [-ring, -ring + (offset - side)];
  if (offset < side * 3) return [-ring + (offset - side * 2), ring];
  return [ring, ring - (offset - side * 3)];
}
export function cityLayout(nodes, repo = "unspecified") {
  const files = nodes
      .filter((n) => n.kind === "file")
      .sort((a, b) => a.path.localeCompare(b.path)),
    symbolsByFile = new Map();
  for (const n of nodes)
    if (n.kind !== "file") {
      if (!symbolsByFile.has(n.path)) symbolsByFile.set(n.path, []);
      symbolsByFile.get(n.path).push(n);
    }
  const key = "neural-cartographer.layout.v3:" + repo;
  let layout = {
    districts: Object.create(null),
    files: Object.create(null),
    nextDistrict: 0,
  };
  try {
    const stored = JSON.parse(localStorage.getItem(key));
    if (
      stored?.districts &&
      stored?.files &&
      Number.isInteger(stored.nextDistrict)
    ) {
      layout = {
        ...stored,
        districts: Object.assign(Object.create(null), stored.districts),
        files: Object.assign(Object.create(null), stored.files),
      };
    }
  } catch {}
  if (!layout.stride) {
    const counts = new Map();
    for (const n of files) {
      const group = n.path.split("/").slice(0, -1).join("/");
      counts.set(group, (counts.get(group) || 0) + 1);
    }
    layout.stride = Math.max(
      18,
      ...[...counts.values()].map(
        (count) => 2 * Math.ceil((Math.sqrt(count) + 1) / 2) * 1.7 + 8,
      ),
    );
  }
  const rows = files.map((n) => {
    const group = n.path.includes("/")
      ? n.path.split("/").slice(0, -1).join("/")
      : "root";
    if (!layout.districts[group]) {
      const [x, z] = spiral(layout.nextDistrict++);
      layout.districts[group] = {
        x: x * layout.stride,
        z: z * layout.stride,
        next: 0,
      };
    }
    const district = layout.districts[group];
    if (!layout.files[n.path]) {
      const [x, z] = spiral(district.next++);
      layout.files[n.path] = {
        x: district.x + x * 1.7,
        z: district.z + z * 1.7,
      };
    }
    const symbols = symbolsByFile.get(n.path) || [],
      loc = Math.max(1, ...symbols.map((s) => s.end || 1));
    return {
      ...n,
      group,
      symbols,
      loc,
      ...layout.files[n.path],
      height: 1 + Math.log2(loc + 1) * 0.65,
    };
  });
  try {
    localStorage.setItem(key, JSON.stringify(layout));
  } catch {}
  return rows;
}

function Buildings({ rows, selected, onSelect, scores, seed, mode, reveal }) {
  const ref = useRef();
  const object = useMemo(() => new THREE.Object3D(), []);
  useEffect(() => {
    rows.forEach((r, i) => {
      const height =
        mode === "terrain"
          ? 1 + (scores.get(r.path)?.score || 0) * 12
          : r.height;
      object.position.set(r.x, height / 2, r.z);
      object.scale.set(1.1, height, 1.1);
      object.updateMatrix();
      ref.current.setMatrixAt(i, object.matrix);
      const rank = scores.get(r.path)?.rank;
      ref.current.setColorAt(
        i,
        new THREE.Color(
          r.path === seed
            ? "#e0fcff"
            : r.path === selected
              ? "#50d9e8"
              : rank && rank <= reveal
                ? "#efab69"
                : /(^|\/)tests?(\/|$)|(^|\/)test_[^/]*\.py$|_test\.py$/.test(
                      r.path,
                    )
                  ? "#65d6ad"
                  : "#577c9c",
        ),
      );
    });
    ref.current.instanceMatrix.needsUpdate = true;
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true;
  }, [rows, selected, scores, seed, mode, reveal, object]);
  return (
    <instancedMesh
      ref={ref}
      args={[null, null, rows.length]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(rows[e.instanceId].path);
      }}
    >
      <boxGeometry />
      <meshStandardMaterial roughness={0.35} metalness={0.3} />
    </instancedMesh>
  );
}
function SymbolWindows({ rows, onSelect, onSelectEntity }) {
  const ref = useRef(),
    object = useMemo(() => new THREE.Object3D(), []);
  const windows = useMemo(
    () =>
      rows
        .flatMap((r) =>
          r.symbols.slice(0, 24).map((s, i) => ({
            ...s,
            x: r.x + 0.58,
            y: ((i + 1) / (Math.min(24, r.symbols.length) + 1)) * r.height,
            z: r.z,
          })),
        )
        .slice(0, 5000),
    [rows],
  );
  useEffect(() => {
    windows.forEach((s, i) => {
      object.position.set(s.x, s.y, s.z);
      object.scale.set(0.08, 0.07, 0.65);
      object.updateMatrix();
      ref.current.setMatrixAt(i, object.matrix);
      ref.current.setColorAt(
        i,
        new THREE.Color(s.kind === "class" ? "#b69cff" : "#8ad7e8"),
      );
    });
    ref.current.instanceMatrix.needsUpdate = true;
    if (ref.current.instanceColor) ref.current.instanceColor.needsUpdate = true;
  }, [windows, object]);
  return (
    <instancedMesh
      ref={ref}
      args={[null, null, windows.length]}
      onClick={(e) => {
        e.stopPropagation();
        const symbol = windows[e.instanceId];
        onSelect(symbol.path);
        onSelectEntity?.(symbol.id);
      }}
    >
      <boxGeometry />
      <meshBasicMaterial />
    </instancedMesh>
  );
}
function Camera({ rows, selected, focus, cameraBus }) {
  const { camera, invalidate, controls } = useThree();
  useEffect(() => {
    if (!rows.length) return;
    const maxX = Math.max(...rows.map((r) => r.x)),
      maxZ = Math.max(...rows.map((r) => r.z)),
      minX = Math.min(...rows.map((r) => r.x)),
      minZ = Math.min(...rows.map((r) => r.z));
    const cx = (minX + maxX) / 2,
      cz = (minZ + maxZ) / 2,
      span = Math.max(maxX - minX, maxZ - minZ, 20);
    camera.position.set(cx + span * 0.65, span * 0.8, cz + span * 0.85);
    if (controls) {
      controls.target.set(cx, 0, cz);
      controls.update();
    }
    invalidate();
  }, [rows, controls]);
  useEffect(() => {
    if (!controls || !cameraBus) return;
    let applying = false;
    const receive = (state) => {
      applying = true;
      camera.position.fromArray(state.position);
      camera.quaternion.fromArray(state.quaternion);
      controls.target.fromArray(state.target);
      controls.update();
      invalidate();
      applying = false;
    };
    const changed = () => {
      if (applying) return;
      const state = {
        position: camera.position.toArray(),
        quaternion: camera.quaternion.toArray(),
        target: controls.target.toArray(),
      };
      cameraBus.state = state;
      for (const listener of cameraBus.listeners)
        if (listener !== receive) listener(state);
    };
    cameraBus.listeners.add(receive);
    if (cameraBus.state) receive(cameraBus.state);
    controls.addEventListener("change", changed);
    return () => {
      cameraBus.listeners.delete(receive);
      controls.removeEventListener("change", changed);
    };
  }, [controls, cameraBus, camera, invalidate]);
  const previousSelection = useRef(selected);
  useEffect(() => {
    const changed = previousSelection.current !== selected;
    previousSelection.current = selected;
    const r = rows.find((r) => r.path === selected);
    if (r && (focus || changed)) {
      camera.position.set(r.x + 14, 18, r.z + 20);
      camera.lookAt(r.x, 0, r.z);
      if (controls) {
        controls.target.set(r.x, 0, r.z);
        controls.update();
      }
      invalidate();
    }
  }, [focus, selected]);
  return null;
}
function Scene({
  rows,
  edges,
  selected,
  onSelect,
  scores,
  seed,
  mode,
  reveal,
  focus,
  cameraBus,
  onSelectEntity,
}) {
  const max = Math.max(30, ...rows.map((r) => Math.max(r.x, r.z))) + 15;
  const byId = new Map(rows.map((r) => [r.id, r]));
  const districts = [...new Set(rows.map((r) => r.group))].map((name) => {
    const files = rows.filter((r) => r.group === name);
    const minX = Math.min(...files.map((r) => r.x)),
      maxX = Math.max(...files.map((r) => r.x)),
      minZ = Math.min(...files.map((r) => r.z)),
      maxZ = Math.max(...files.map((r) => r.z));
    return {
      name,
      x: (minX + maxX) / 2,
      z: (minZ + maxZ) / 2,
      w: maxX - minX + 3,
      d: maxZ - minZ + 3,
    };
  });
  const paths = edges
    .filter(
      (e) =>
        e.relation === "IMPORTS" &&
        (byId.get(e.source)?.path === selected ||
          byId.get(e.target)?.path === selected),
    )
    .slice(0, 30);
  return (
    <>
      <color attach="background" args={["#070b13"]} />
      <ambientLight intensity={1.3} />
      <directionalLight
        position={[15, 40, 20]}
        intensity={2.4}
        color="#a3d9ef"
      />
      <gridHelper
        args={[max * 2, 80, "#20394b", "#11202e"]}
        position={[max / 2, -0.03, max / 2]}
      />
      {districts.map((d) => (
        <group key={d.name}>
          <mesh position={[d.x, -0.17, d.z]}>
            <boxGeometry args={[d.w, 0.2, d.d]} />
            <meshStandardMaterial color="#142536" roughness={0.6} />
          </mesh>
          <Html
            position={[d.x, 0.1, d.z + d.d / 2 + 1]}
            center
            distanceFactor={65}
          >
            <span className="district-label">{d.name}</span>
          </Html>
        </group>
      ))}
      <Buildings
        {...{ rows, selected, onSelect, scores, seed, mode, reveal }}
      />
      <SymbolWindows
        rows={rows}
        onSelect={onSelect}
        onSelectEntity={onSelectEntity}
      />
      {rows
        .filter((r) => r.path === selected)
        .flatMap((r) =>
          r.symbols.slice(0, 60).map((s, i) => (
            <mesh
              key={s.id}
              position={[
                r.x + 0.6,
                ((i + 1) / (Math.min(60, r.symbols.length) + 1)) * r.height,
                r.z,
              ]}
              onClick={(e) => {
                e.stopPropagation();
                onSelect(r.path);
                onSelectEntity?.(s.id);
              }}
            >
              <boxGeometry args={[0.08, 0.08, 0.6]} />
              <meshBasicMaterial
                color={
                  s.kind === "test"
                    ? "#65d6ad"
                    : s.kind === "class"
                      ? "#b69cff"
                      : "#50d9e8"
                }
              />
            </mesh>
          )),
        )}
      {paths.map((e, i) => {
        const a = byId.get(e.source),
          b = byId.get(e.target);
        return (
          <Line
            key={i}
            points={[
              [a.x, a.height, a.z],
              [
                (a.x + b.x) / 2,
                Math.max(a.height, b.height) + 5,
                (a.z + b.z) / 2,
              ],
              [b.x, b.height, b.z],
            ]}
            color="#50d9e8"
            lineWidth={1.5}
          />
        );
      })}
      {rows
        .filter((r) => r.path === selected)
        .map((r) => (
          <Html key={r.id} position={[r.x, r.height + 2, r.z]} center>
            <div className="city-label">
              {r.path}
              <small>
                {r.symbols.length} symbols · ≥{r.loc} lines
              </small>
            </div>
          </Html>
        ))}
      <OrbitControls
        makeDefault
        target={[max / 3, 0, max / 3]}
        maxPolarAngle={Math.PI / 2.05}
        minDistance={5}
        maxDistance={max * 3}
      />
      <Camera {...{ rows, selected, focus, cameraBus }} />
    </>
  );
}
export class CanvasBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onFailure?.();
  }
  render() {
    return this.state.failed ? (
      <p role="alert">3D unavailable. Use the accessible entity table below.</p>
    ) : (
      this.props.children
    );
  }
}
export default function CodeMetropolis({
  graph,
  selected,
  onSelect,
  result,
  mode = "city",
  cameraBus,
  onSelectEntity,
}) {
  const rows = useMemo(
    () => cityLayout(graph.nodes, graph.repo),
    [graph.nodes, graph.repo],
  );
  const [view, setView] = useState("3d"),
    [focus, setFocus] = useState(0),
    [reveal, setReveal] = useState(100);
  const scores = useMemo(
    () =>
      new Map(
        (result?.candidates || []).map((r, i) => [
          r.path,
          { ...r, rank: i + 1 },
        ]),
      ),
    [result],
  );
  useEffect(() => {
    const handler = (e) => {
      if (/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
      if (e.key === "f") setFocus((v) => v + 1);
      if (e.key === "Escape") onSelect("");
      if (e.key === "2") setView("table");
      if (e.key === "1") setView("3d");
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onSelect]);
  const supported = useMemo(() => {
    try {
      return !!document.createElement("canvas").getContext("webgl2");
    } catch {
      return false;
    }
  }, []);
  const playbackTimer = useRef();
  useEffect(() => () => clearInterval(playbackTimer.current), []);
  function playback() {
    clearInterval(playbackTimer.current);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setReveal(100);
      return;
    }
    setReveal(0);
    let n = 0;
    const timer = setInterval(() => {
      setReveal(++n);
      if (n >= (result?.candidates.length || 1)) clearInterval(timer);
    }, 200);
    playbackTimer.current = timer;
    return timer;
  }
  return (
    <section className="metropolis">
      <div className="city-toolbar">
        <div>
          <span className="section-tag">LIVE SOURCE CARTOGRAPHY</span>
          <h2>{mode === "terrain" ? "Risk Topography" : "Code Metropolis"}</h2>
        </div>
        <div className="filters">
          <button
            className="secondary"
            onClick={() => setView(view === "3d" ? "table" : "3d")}
          >
            {view === "3d" ? "Entity table [2]" : "3D city [1]"}
          </button>
          <button className="secondary" onClick={() => setFocus((v) => v + 1)}>
            Focus [F]
          </button>
          {result && (
            <button className="secondary" onClick={playback}>
              Replay ranked reveal
            </button>
          )}
        </div>
      </div>
      <p className="result-note">
        {graph.slice && "Saved historical graph slice (up to 500 entities) · "}
        {graph.repo} · {graph.revision.slice(0, 12)} · {rows.length} files ·
        Height:{" "}
        {mode === "terrain"
          ? "uncalibrated model score × 12 + 1"
          : "log₂ source extent"}{" "}
        · Cyan selection / green tests / amber predictions
      </p>
      {view === "3d" && supported ? (
        <CanvasBoundary onFailure={() => setView("table")}>
          <div className="city-canvas">
            <Canvas
              frameloop="demand"
              dpr={[1, 1.5]}
              camera={{ position: [65, 55, 80], fov: 48 }}
              onCreated={({ gl }) =>
                gl.domElement.addEventListener("webglcontextlost", () =>
                  setView("table"),
                )
              }
            >
              <Suspense fallback={null}>
                <Scene
                  {...{
                    rows,
                    selected,
                    onSelect,
                    scores,
                    mode,
                    reveal,
                    focus,
                    cameraBus,
                    onSelectEntity,
                  }}
                  edges={graph.edges}
                  seed={result?.seed}
                />
              </Suspense>
            </Canvas>
            <div className="city-watermark">
              PINNED SOURCE / {graph.quality?.entities || graph.nodes.length}{" "}
              ENTITIES
              <br />
              Drag to orbit · Scroll to zoom · Click to inspect
            </div>
          </div>
        </CanvasBoundary>
      ) : null}
      {(view === "table" || !supported) && (
        <div className="entity-table">
          <table>
            <thead>
              <tr>
                <th>File / district</th>
                <th>Symbols</th>
                <th>Source extent</th>
                <th>Rank</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <button
                      className="link"
                      aria-pressed={selected === r.path}
                      onClick={() => onSelect(r.path)}
                    >
                      {r.path}
                    </button>
                  </td>
                  <td>{r.symbols.length}</td>
                  <td>≥{r.loc}</td>
                  <td>{scores.get(r.path)?.rank || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="result-note">
        Predictive visualization — not actual execution trace. Lines are
        existing parsed IMPORTS relations touching selection; unconnected
        predictions have no invented links.{" "}
        {graph.quality?.unresolved_edges || 0} unresolved/external edges
        omitted.
      </p>
    </section>
  );
}
