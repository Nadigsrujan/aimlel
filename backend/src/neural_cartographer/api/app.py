"""Versioned FastAPI adapter for local repository analysis."""
from contextlib import asynccontextmanager
import json
import threading
import uuid
import os
import signal
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from neural_cartographer.candidates.ranking import analyze
from neural_cartographer.features.history import RANKERS, FEATURE_VERSION
from neural_cartographer.contracts.schema import entity_records
from neural_cartographer.graph.snapshots import build_snapshot
from neural_cartographer.ingest.pipeline import ROOT, public_repo_id, write, git, eligible
import re
import subprocess
from neural_cartographer.api import legacy as serve


class Submission(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class Analysis(BaseModel):
    repo: str = Field(min_length=3, max_length=256)
    seed: str = Field(min_length=1, max_length=4096)
    target: str = Field(default='', max_length=40)
    top_k: int = Field(default=10, ge=1, le=100)
    ranker: str = Field(default='path-distance-v1', max_length=64)


@asynccontextmanager
async def lifespan(app):
    serve.restore_jobs()
    yield


app = FastAPI(title='Neural Cartographer', version='1.0.0', lifespan=lifespan)
FRONTEND_DIST = ROOT / 'frontend/dist'
if (FRONTEND_DIST / 'assets').is_dir():
    app.mount('/assets', StaticFiles(directory=str(FRONTEND_DIST / 'assets')), name='assets')


@app.get('/api/v1/models')
def models():
    return {'rankers': list(RANKERS) + ['semantic-v1'], 'default': 'path-distance-v1',
            'feature_version': FEATURE_VERSION, 'score_is_probability': False,
            'learned_models_available': False}


@app.get('/', response_class=HTMLResponse)
def index():
    if (FRONTEND_DIST / 'index.html').is_file():
        return FileResponse(FRONTEND_DIST / 'index.html')
    return '<h1>Neural Cartographer</h1><p>Build the frontend with <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>, then restart the server.</p><a href="/docs">API documentation</a>'


@app.get('/api/v1/health')
def health():
    return {'status': 'ok', 'schema_version': 1, 'frontend_ready': (FRONTEND_DIST / 'index.html').is_file()}


@app.get('/api/repos')
@app.get('/api/v1/repositories')
def repositories():
    return sorted(serve.load_manifests())


@app.get('/api/v1/catalog')
def catalog():
    entries = []
    for repo, manifest in sorted(serve.load_manifests().items()):
        directory = ROOT / 'data/processed' / repo.replace('/', '__') / manifest['revision']
        summary = json.loads((directory / 'summary.json').read_text())
        entries.append({'repo': repo, 'revision': manifest['revision'], 'split': manifest['split'],
                        'source_url': 'https://github.com/' + repo,
                        'deletable': manifest['split'] == 'submitted', 'summary': summary})
    return entries


@app.get('/api/v1/snapshots')
def snapshots(repo: str):
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, 'Repository unavailable')
    return [{'revision': manifest['revision'], 'pinned': True}]


@app.get('/api/v1/seeds')
def seeds(repo: str, search: str = '', kind: str = 'file', limit: int = 100):
    if not 1 <= limit <= 1000 or kind not in ('file', 'function', 'class', 'test', 'all'):
        raise HTTPException(422, 'Invalid seed kind or limit')
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, 'Repository unavailable')
    path = ROOT / 'data/processed' / repo.replace('/', '__') / manifest['revision'] / 'graph.json'
    graph = json.loads(path.read_text())
    return [node for node in entity_records(graph, repo, manifest['revision'])
            if (kind == 'all' or node['kind'] == kind)
            and search.casefold() in (node['path'] + node['qualified_name']).casefold()][:limit]


@app.get('/api/files')
def files(repo: str, target: str = ''):
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, 'Repository unavailable')
    if target:
        if not re.fullmatch('[0-9a-f]{40}', target):
            raise HTTPException(422, 'Historical commit must be a full SHA')
        clone = ROOT / 'data/raw' / repo.replace('/', '__')
        ancestry = subprocess.run(['git', '-C', str(clone), 'merge-base', '--is-ancestor', target,
                                  manifest['revision']], capture_output=True, timeout=60)
        if ancestry.returncode:
            raise HTTPException(422, 'Commit outside pinned history')
        parents = git(clone, 'rev-list', '--parents', '-n', '1', target).decode().split()
        if len(parents) != 2:
            raise HTTPException(422, 'Select a single-parent commit')
        entries = git(clone, 'ls-tree', '-r', '-z', parents[1]).split(b'\0')
        names = []
        for entry in entries:
            if not entry:
                continue
            metadata, raw = entry.split(b'\t', 1)
            path = raw.decode('utf-8', 'surrogateescape')
            if metadata.startswith(b'100') and eligible(path):
                names.append(path)
        return sorted(names)
    path = ROOT / 'data/processed' / repo.replace('/', '__') / manifest['revision'] / 'graph.json'
    return sorted(n['path'] for n in json.loads(path.read_text())['nodes'] if n['kind'] == 'file')


@app.post('/api/v1/analysis')
def analysis(request: Analysis):
    if request.repo not in serve.load_manifests():
        raise HTTPException(404, 'Repository unavailable')
    try:
        result = analyze(request.repo, request.seed, request.target or None, request.top_k,
                         include_evidence=True, ranker=request.ranker)
        paths = {request.seed} | {row['path'] for row in result['candidates']}
        for row in result['candidates']:
            paths.update(row['evidence']['import_path'])
        graph = result['graph']
        selected = [node for node in graph['nodes'] if node['path'] in paths]
        selected.sort(key=lambda node: (node['kind'] != 'file', node['id']))
        selected = selected[:500]
        ids = {node['id'] for node in selected}
        result['graph'] = {'nodes': selected,
                           'edges': [edge for edge in graph['edges'] if edge['source'] in ids and edge['target'] in ids],
                           'total_nodes': len(graph['nodes']), 'truncated': len(selected) < len(graph['nodes']),
                           'node_limit': 500}
        result['entities'] = [node for node in result['entities'] if node['legacy_id'] in ids]
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get('/api/analyze')
def legacy_analysis(repo: str, seed: str, target: str = ''):
    return analysis(Analysis(repo=repo, seed=seed, target=target))


@app.post('/api/ingest', status_code=202)
@app.post('/api/v1/jobs', status_code=202)
def submit(request: Submission):
    try:
        repo = public_repo_id(request.url.strip())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    manifests = [json.loads(p.read_text()) for p in (ROOT / 'data/manifests').glob('*.json')]
    if any(m['repo'].lower() == repo.lower() for m in manifests):
        raise HTTPException(409, 'Repository already ingested')
    with serve.LOCK:
        active = [j for j in serve.JOBS.values() if j['status'] == 'running']
        if any(j['repo'].lower() == repo.lower() for j in active):
            raise HTTPException(409, 'Repository ingestion already running')
        if len(active) >= 2:
            raise HTTPException(429, 'Two ingestion jobs are already running')
        if len(serve.JOBS) >= 100:
            oldest = next(k for k, j in serve.JOBS.items() if j['status'] != 'running')
            del serve.JOBS[oldest]
        job = uuid.uuid4().hex
        serve.JOBS[job] = {'status': 'running', 'repo': repo}
        write(serve.JOB_FILE, serve.JOBS)
    threading.Thread(target=serve.ingest_job, args=(job, request.url.strip(), repo), daemon=True).start()
    return {'job': job, 'repo': repo, 'status': 'running'}


@app.get('/api/jobs')
def job_status(id: str):
    with serve.LOCK:
        if id not in serve.JOBS:
            raise HTTPException(404, 'Unknown job')
        return dict(serve.JOBS[id])


@app.get('/api/v1/jobs/{job_id}')
def versioned_job_status(job_id: str):
    return job_status(job_id)


@app.post('/api/v1/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    with serve.LOCK:
        item = serve.JOBS.get(job_id)
        if item is None:
            raise HTTPException(404, 'Unknown job')
        if item['status'] != 'running':
            raise HTTPException(409, 'Job is no longer running')
        process = serve.PROCESSES.get(job_id)
        if process is None:
            raise HTTPException(409, 'Job is starting; retry cancellation shortly')
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        item['status'] = 'cancelled'
        write(serve.JOB_FILE, serve.JOBS)
        return dict(item)


@app.delete('/api/v1/repositories/{owner}/{name}')
def delete_repository(owner: str, name: str):
    try:
        repo = public_repo_id(f'https://github.com/{owner}/{name}')
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    key = repo.replace('/', '__')
    manifest_path = ROOT / 'data/manifests' / (key + '.json')
    if not manifest_path.exists():
        raise HTTPException(404, 'Repository unavailable')
    manifest = json.loads(manifest_path.read_text())
    if manifest['split'] != 'submitted':
        raise HTTPException(409, 'Pinned research repositories cannot be deleted through the API')
    with serve.LOCK:
        if any(j['repo'].lower() == repo.lower() and j['status'] == 'running' for j in serve.JOBS.values()):
            raise HTTPException(409, 'Cancel active ingestion before deletion')
        destination = ROOT / 'data/deleted' / (key + '-' + uuid.uuid4().hex)
        destination.mkdir(parents=True)
        for label, source in [('manifest.json', manifest_path), ('raw', ROOT / 'data/raw' / key),
                              ('processed', ROOT / 'data/processed' / key)]:
            if source.exists():
                shutil.move(str(source), str(destination / label))
    return {'status': 'archived', 'repo': repo, 'recovery_path': str(destination.relative_to(ROOT))}
