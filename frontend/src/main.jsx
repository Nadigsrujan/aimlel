import React, {useState, useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import ImpactResults from './components/ImpactResults.jsx';
import {api} from './api/client.js';
import '@xyflow/react/dist/style.css';
import './style.css';

function App() {
  const [repos,setRepos]=useState([]), [repo,setRepo]=useState(''), [files,setFiles]=useState([]);
  const [seed,setSeed]=useState(''),[url,setUrl]=useState(''),[target,setTarget]=useState('');
  const [result,setResult]=useState(null),[status,setStatus]=useState('Loading catalog…');
  const [busy,setBusy]=useState(false),[job,setJob]=useState(null),[selected,setSelected]=useState('');
  const [topK,setTopK]=useState(10),[search,setSearch]=useState('');
  const [ranker,setRanker]=useState('path-distance-v1'),[rankers,setRankers]=useState([]);
  useEffect(()=>{api('/api/v1/models').then(value=>setRankers(value.rankers)).catch(error=>setStatus(error.message));},[]);
  async function catalog(preferred) {
    const list=await api('/api/v1/repositories');setRepos(list);setRepo(preferred || list[0] || '');
  }
  useEffect(()=>{catalog().then(()=>setStatus('Ready')).catch(e=>setStatus(e.message));},[]);
  useEffect(()=>{
    if(!repo)return;
    let active=true;
    setResult(null);setFiles([]);setSeed('');
    if(target && !/^[0-9a-f]{40}$/.test(target)){
      setStatus('Enter the complete 40-character historical SHA');
      return ()=>{active=false};
    }
    const query=new URLSearchParams({repo,target});
    api('/api/files?'+query).then(list=>{
      if(active){setFiles(list);setSeed(list[0]||'');setStatus(list.length?'Ready':'No supported Python files found')}
    }).catch(e=>active&&setStatus(e.message));
    return()=>{active=false};
  },[repo,target]);
  useEffect(()=>{if(!job)return;let active=true,timer;async function poll(){try{const value=await api('/api/v1/jobs/'+job.id);if(!active)return;if(value.status==='running'){setStatus('Indexing '+job.repo+'…');timer=setTimeout(poll,1500)}else{setJob(null);setStatus(value.error||'Repository ready');if(value.status==='processed')await catalog(job.repo)}}catch(e){if(active){setStatus(e.message);setJob(null)}}}poll();return()=>{active=false;clearTimeout(timer)}},[job]);
  async function submit(event){event.preventDefault();setBusy(true);try{const value=await api('/api/v1/jobs',{url});setJob({id:value.job,repo:value.repo});setUrl('')}catch(e){setStatus(e.message)}finally{setBusy(false)}}
  async function run(event){event.preventDefault();setBusy(true);setStatus('Analyzing snapshot…');try{const value=await api('/api/v1/analysis',{repo,seed,target,ranker,top_k:Number(topK)});setResult(value);setSelected('');setStatus('Analysis complete')}catch(e){setStatus(e.message)}finally{setBusy(false)}}
  async function cancel(){try{await api('/api/v1/jobs/'+job.id+'/cancel',{});setJob(null);setStatus('Ingestion cancelled')}catch(error){setStatus(error.message)}}
  return <main><header><span>REPOSITORY INTELLIGENCE / DEVELOPMENT BASELINE</span><h1>Neural Cartographer</h1><p>Select a Python file to explore related files and the evidence available at its revision.</p></header>
    <form onSubmit={submit}><label>Public GitHub repository<input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://github.com/owner/repository" required/></label><button disabled={busy||!!job}>Index repository</button></form>
    {job&&<button onClick={cancel}>Cancel ingestion</button>}
    <label>Ranking method<select value={ranker} onChange={event=>setRanker(event.target.value)}>{rankers.map(name=><option key={name}>{name}</option>)}</select></label>
    <form onSubmit={run}><label>Search catalog<input value={search} onChange={e=>setSearch(e.target.value)}/></label><label>Repository<select value={repo} onChange={e=>setRepo(e.target.value)}>{repos.filter(r=>r===repo||r.toLowerCase().includes(search.toLowerCase())).map(r=><option key={r}>{r}</option>)}</select></label><label>Seed file<select value={seed} onChange={e=>setSeed(e.target.value)}>{files.map(f=><option key={f}>{f}</option>)}</select></label><label>Historical target SHA (optional)<input value={target} onChange={e=>setTarget(e.target.value)} maxLength={40}/></label><label>Top K<input type="number" min="1" max="100" value={topK} onChange={e=>setTopK(e.target.value)}/></label><button disabled={busy||!seed}>Analyze</button></form>
    <p role="status" aria-live="polite">{status}</p>{result&&<ImpactResults key={result.repo+result.graph_revision+result.seed+result.ranker} result={result}/>}
    <footer>Held-out evaluation projects remain sealed until model selection and final evaluation are complete.</footer></main>
}
createRoot(document.getElementById('root')).render(<App/>);
