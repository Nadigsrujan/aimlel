import React, {useState} from 'react';
import {ReactFlow, Background, Controls} from '@xyflow/react';
import {graphView} from '../graph/view.js';

export default function ImpactResults({result}) {
  const [selected, setSelected] = useState('');
  const [channel, setChannel] = useState('all');
  const [minimum, setMinimum] = useState(0);
  const candidates = result.candidates.filter(row => row.score >= minimum &&
    (channel === 'all' || row.channels?.includes(channel)));
  const {nodes, edges} = graphView(result, candidates, selected);
  const candidate = candidates.find(row => row.path === selected);
  return <section>
    <p><code>{result.graph_revision}</code> · {result.graph.total_nodes || result.graph.nodes.length} entities · {result.candidate_count} candidate files</p>
    <p>Ranker: <strong>{result.ranker}</strong>. Scores are heuristics, not probabilities. Select a file to inspect its evidence. Graph lines show only retrieved static import paths.</p>
    <div className="filters">
      <label>Evidence channel<select value={channel} onChange={event => setChannel(event.target.value)}>
        <option value="all">All</option><option value="structural">Static imports</option>
        <option value="history">Past co-change</option><option value="directory">Directory</option>
        <option value="semantic">Code similarity</option>
      </select></label>
      <label>Minimum score<input type="number" min="-1" step="0.01" value={minimum}
        onChange={event => setMinimum(Number(event.target.value))}/></label>
    </div>
    {!candidates.length && <p role="status">No files match these filters. Lower the minimum score or choose another channel.</p>}
    <section className="workspace">
      <div className="graph" aria-label="Impact graph">
        <ReactFlow nodes={nodes} edges={edges} fitView onNodeClick={(_, node) => setSelected(node.id)}>
          <Background/><Controls/>
        </ReactFlow>
      </div>
      <aside><h2>Ranked files</h2><ol>{candidates.map(row => <li key={row.path}>
        <button className="link" aria-pressed={selected === row.path} onClick={() => setSelected(row.path)}>{row.path}</button>
        <small>Score {row.score.toFixed(3)} · {(row.channels || []).join(', ')}</small>
      </li>)}</ol></aside>
    </section>
    {candidate && <section><h2>Evidence: {candidate.path}</h2>
      <p>Cutoff: <code>{result.evidence_cutoff || result.graph_revision}</code></p>
      <h3>Static import path</h3><p>{candidate.evidence?.import_path?.join(' → ') || 'No resolved import path within three hops.'}</p>
      <h3>Past co-change commits</h3>
      {candidate.evidence?.past_commits?.length ? <ul>{candidate.evidence.past_commits.map(sha =>
        <li key={sha}><a href={`https://github.com/${result.repo}/commit/${sha}`} target="_blank" rel="noreferrer">{sha}</a></li>)}</ul> : <p>No qualifying past co-change found.</p>}
      <details><summary>Feature values</summary><pre>{JSON.stringify(candidate.features, null, 2)}</pre></details>
    </section>}
  </section>;
}
