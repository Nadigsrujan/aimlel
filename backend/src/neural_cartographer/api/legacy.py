"""Local baseline explorer. Run: python scripts/serve.py"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs
from neural_cartographer.candidates.ranking import analyze
from neural_cartographer.ingest.pipeline import ROOT, public_repo_id, write
import os
import signal
import time
import subprocess
import sys
import threading
import uuid
from neural_cartographer.jobs.processes import stop_process_tree

PAGE = """<!doctype html><meta charset="utf-8"><title>Neural Cartographer</title>
<style>body{font:17px system-ui;background:#101821;color:#e3edf5;max-width:1000px;margin:60px auto}select,input,button{padding:12px;margin:8px;background:#243445;color:white;border:1px solid #63798c}pre{white-space:pre-wrap}li{padding:8px}small{color:#9eb2c6}</style>
<h1>Neural Cartographer</h1><p>Explore Python files and directory-proximity impact rankings.</p>
<small>Baseline scores are relative proximity scores, not probabilities. Imports are recorded as unresolved module names.</small>
<p><label>Public GitHub repository <input id="url" size="42" placeholder="https://github.com/owner/repository"></label><button id="add">Add repository</button></p>
<p><label>Repository <select id="repo"></select></label><label>Seed file <select id="seed"></select></label></p>
<label>Historical target commit (optional) <input id="commit" placeholder="Full SHA"></label><button id="run">Analyze</button>
<p id="status" role="status"></p><ol id="results"></ol><details><summary>Graph and source evidence</summary><pre id="graph"></pre></details>
<script>
const $=id=>document.getElementById(id);async function get(url){let r=await fetch(url);let d=await r.json();if(!r.ok)throw Error(d.error);return d}
async function files(){try{let d=await get('/api/files?repo='+encodeURIComponent($('repo').value));$('seed').replaceChildren(...d.map(p=>new Option(p,p)))}catch(e){$('status').textContent=e.message}}
$('repo').onchange=files;$('run').onclick=async()=>{ $('status').textContent='Reconstructing snapshot…';$('run').disabled=true;try{let q=new URLSearchParams({repo:$('repo').value,seed:$('seed').value});if($('commit').value)q.set('target',$('commit').value);let d=await get('/api/analyze?'+q);$('status').textContent='Revision '+d.graph_revision+' · '+d.graph.nodes.length+' entities';$('results').replaceChildren(...d.candidates.map(c=>{let li=document.createElement('li');li.textContent=c.path+' — proximity '+c.score.toFixed(3);return li}));$('graph').textContent=JSON.stringify(d.graph,null,2)}catch(e){$('status').textContent=e.message}finally{$('run').disabled=false}};
async function repos(){let d=await get('/api/repos');$('repo').replaceChildren(...d.map(p=>new Option(p,p)));await files()}
$('add').onclick=async()=>{ $('status').textContent='Ingesting repository…';$('add').disabled=true;try{let d=await fetch('/api/ingest',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:$('url').value})}).then(async r=>{let x=await r.json();if(!r.ok)throw Error(x.error);return x});$('status').textContent='Ingestion started for '+d.repo+'. Polling…';let timer=setInterval(async()=>{let s=await get('/api/jobs?id='+d.job);if(s.status==='processed'||s.status==='failed'){clearInterval(timer);$('status').textContent=s.status==='processed'?'Repository added.':'Ingestion failed: '+s.error;await repos()}},1000)}catch(e){$('status').textContent=e.message}finally{$('add').disabled=false}};
repos().catch(e=>$('status').textContent=e.message);
</script>"""

JOBS = {}
LOCK = threading.Lock()
PROCESSES = {}
MAX_REPOSITORY_BYTES = 2 * 1024 * 1024 * 1024
JOB_FILE = ROOT / "artifacts/jobs/state.json"


def restore_jobs():
    """Interrupted jobs require explicit retry after a server restart."""
    if JOB_FILE.exists():
        JOBS.update(json.loads(JOB_FILE.read_text()))
        for item in JOBS.values():
            if item["status"] == "running":
                item.update(status="failed", error="Server restarted; retry ingestion")
        write(JOB_FILE, JOBS)


def load_manifests():
    """Read each manifest once; preserve the planned held-out partition."""
    final = ROOT / "artifacts/reports/final-heldout.json"
    released = (
        final.is_file()
        and json.loads(final.read_text()).get("status") == "frozen held-out evaluation"
    )
    manifests = {}
    for path in (ROOT / "data/manifests").glob("*.json"):
        manifest = json.loads(path.read_text())
        if manifest["split"] != "test" or released:
            manifests[manifest["repo"]] = manifest
    return manifests


def validate_submission(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
        raise ValueError("Expected a JSON object with a string url")
    url = payload["url"].strip()
    return url, public_repo_id(url)


def ingest_job(job, url, repo):
    process = None
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                str(ROOT / "scripts/ingest.py"),
                "--public-url",
                url,
                "--clone",
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        with LOCK:
            PROCESSES[job] = process
        try:
            deadline = time.monotonic() + 3600
            while True:
                try:
                    stdout, stderr = process.communicate(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    raw = ROOT / "data/raw" / repo.replace("/", "__")
                    size = (
                        sum(
                            path.stat().st_size
                            for path in raw.rglob("*")
                            if path.is_file() and not path.is_symlink()
                        )
                        if raw.exists()
                        else 0
                    )
                    if size > MAX_REPOSITORY_BYTES or time.monotonic() >= deadline:
                        raise subprocess.TimeoutExpired(process.args, 3600)
        except subprocess.TimeoutExpired:
            stop_process_tree(process)
            process.communicate()
            raise TimeoutError(
                "Ingestion exceeded the one-hour or 2 GiB repository limit; process group stopped"
            )
        if process.returncode:
            raise subprocess.CalledProcessError(
                process.returncode, process.args, stdout, stderr
            )
        result = {"status": "processed", "repo": repo}
    except subprocess.CalledProcessError as exc:
        result = {
            "status": "failed",
            "repo": repo,
            "error": (exc.stdout + exc.stderr)[-2000:],
        }
    except Exception as exc:
        result = {"status": "failed", "repo": repo, "error": str(exc)}
    finally:
        if process is not None and process.poll() is None:
            stop_process_tree(process)
            process.communicate()
    with LOCK:
        PROCESSES.pop(job, None)
        if JOBS[job]["status"] != "cancelled":
            JOBS[job] = result
        write(JOB_FILE, JOBS)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PAGE.encode())
            return
        try:
            manifests = load_manifests()
            query = parse_qs(url.query)
            repo = query.get("repo", [""])[0]
            if url.path == "/api/repos":
                data = sorted(manifests)
            elif url.path == "/api/jobs":
                with LOCK:
                    data = JOBS.get(query.get("id", [""])[0], {"status": "unknown"})
            elif repo not in manifests:
                raise ValueError("Select an ingested repository")
            elif url.path == "/api/files":
                m = manifests[repo]
                graph = (
                    ROOT
                    / "data/processed"
                    / repo.replace("/", "__")
                    / m["revision"]
                    / "graph.json"
                )
                data = sorted(
                    n["path"]
                    for n in json.loads(graph.read_text())["nodes"]
                    if n["kind"] == "file"
                )
            elif url.path == "/api/analyze":
                data = analyze(
                    repo, query.get("seed", [""])[0], query.get("target", [None])[0]
                )
            else:
                raise ValueError("Unknown endpoint")
            status = 200
        except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
            data, status = {"error": str(exc)}, 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_POST(self):
        if urlsplit(self.path).path != "/api/ingest":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError("Request body must contain 1–4096 bytes")
            payload = json.loads(self.rfile.read(length))
            raw_url, repo = validate_submission(payload)
            if repo in {
                json.loads(p.read_text())["repo"]
                for p in (ROOT / "data/manifests").glob("*.json")
            }:
                raise ValueError("Repository is already ingested")
            job = uuid.uuid4().hex
            with LOCK:
                active = [item for item in JOBS.values() if item["status"] == "running"]
                if any(item["repo"].lower() == repo.lower() for item in active):
                    raise ValueError("Repository ingestion is already running")
                if len(active) >= 2:
                    raise ValueError(
                        "Two ingestion jobs are running; retry when one completes"
                    )
                if len(JOBS) >= 100:
                    completed = next(
                        key
                        for key, value in JOBS.items()
                        if value["status"] != "running"
                    )
                    del JOBS[completed]
                JOBS[job] = {"status": "running", "repo": repo}
                write(JOB_FILE, JOBS)
            threading.Thread(
                target=ingest_job, args=(job, raw_url, repo), daemon=True
            ).start()
            data, status = {"job": job, "repo": repo, "status": "running"}, 202
        except (ValueError, json.JSONDecodeError) as exc:
            data, status = {"error": str(exc)}, 400
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())


if __name__ == "__main__":
    restore_jobs()
    print("Neural Cartographer: http://127.0.0.1:8080", flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
