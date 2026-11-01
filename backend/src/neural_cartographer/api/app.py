"""Versioned FastAPI adapter for local repository analysis."""

import json
import re
import shutil
import subprocess
import threading
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from neural_cartographer.api import legacy as serve
from neural_cartographer.candidates.ranking import analyze
from neural_cartographer.contracts.api_models import (
    AnalysisResponse,
    CatalogEntry,
    JobStatus,
    SourceResponse,
)
from neural_cartographer.contracts.schema import entity_records
from neural_cartographer.features.history import FEATURE_VERSION, RANKERS
from neural_cartographer.ingest.pipeline import (
    ROOT,
    VERSION,
    eligible,
    git,
    public_repo_id,
)
from neural_cartographer.jobs.store import JobError
from neural_cartographer.jobs.worker import STORE as JOB_STORE
from neural_cartographer.jobs.worker import run as run_ingestion_job


class Submission(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


class Analysis(BaseModel):
    repo: str = Field(min_length=3, max_length=256)
    seed: str = Field(min_length=1, max_length=4096)
    target: str = Field(default="", max_length=40)
    top_k: int = Field(default=10, ge=1, le=100)
    ranker: str = Field(default="path-distance-v1", max_length=64)


class Explanation(Analysis):
    candidate: str = Field(min_length=1, max_length=4096)
    use_gemini: bool = False


@asynccontextmanager
async def lifespan(app):
    with JOB_STORE.transaction():
        pass
    yield


app = FastAPI(title="Neural Cartographer", version="1.0.0", lifespan=lifespan)


@app.get("/api/v1/research")
def research_status():
    report_path = ROOT / "artifacts/reports/heterogeneous-development.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    metadata = report.get("metadata", {})
    config_path = ROOT / "configs/experiments/heterogeneous.json"
    configuration = json.loads(config_path.read_text()) if config_path.is_file() else {}
    compatible = (
        metadata.get("provenance", {}).get("parser_version") == VERSION
        and metadata.get("config", {}) == configuration
    )
    entries = [
        entry for entry in catalog() if entry["split"] in ("train", "validation")
    ]
    return {
        "split": {"train": 7, "validation": 2, "test": 3},
        "ready_repositories": sum(entry["available"] for entry in entries),
        "development_repositories": len(entries),
        "semantic_snapshots": len(
            list((ROOT / "data/processed").glob("*/*/embeddings-*/manifest.json"))
        ),
        "checkpoint_available": (
            ROOT / "artifacts/models/heterogeneous-development/model.pt"
        ).is_file(),
        "frozen": (
            ROOT / "artifacts/models/heterogeneous-development/freeze.json"
        ).is_file(),
        "held_out_evaluated": (ROOT / "artifacts/reports/final-heldout.json").is_file(),
        "experiment_compatible": compatible,
        "parser_version": VERSION,
        "experiment_parser_version": metadata.get("provenance", {}).get(
            "parser_version"
        ),
        "status": report.get("status", "No experiment recorded"),
        "metrics": report.get("macro_recall_at_5", {}) if compatible else {},
        "confidence_intervals": report.get("confidence_intervals", {})
        if compatible
        else {},
        "samples": {
            name: len(metadata.get(name, []))
            for name in ("train_queries", "selection_queries", "calibration_queries")
        },
        "limitations": metadata.get("config", {}).get("limitations", []),
    }


FRONTEND_DIST = ROOT / "frontend/dist"
if (FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets"
    )


@app.get("/api/v1/models")
def models():
    from neural_cartographer.learning.inference import checkpoint_path

    learned = checkpoint_path().is_file()
    return {
        "rankers": list(RANKERS)
        + ["semantic-v1"]
        + (["heterogeneous-v1"] if learned else []),
        "default": "heterogeneous-v1" if learned else "combined-v1",
        "feature_version": FEATURE_VERSION,
        "score_is_probability": False,
        "learned_models_available": learned,
    }


@app.get("/", response_class=HTMLResponse)
def index():
    if (FRONTEND_DIST / "index.html").is_file():
        return FileResponse(FRONTEND_DIST / "index.html")
    return '<h1>Neural Cartographer</h1><p>Build the frontend with <code>cd frontend &amp;&amp; npm ci &amp;&amp; npm run build</code>, then restart the server.</p><a href="/docs">API documentation</a>'


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "schema_version": 1,
        "frontend_ready": (FRONTEND_DIST / "index.html").is_file(),
    }


@app.get("/api/repos")
@app.get("/api/v1/repositories")
def repositories():
    return sorted(serve.load_manifests())


@app.get("/api/v1/catalog", response_model=list[CatalogEntry])
def catalog():
    entries = []
    for repo, manifest in sorted(serve.load_manifests().items()):
        directory = (
            ROOT / "data/processed" / repo.replace("/", "__") / manifest["revision"]
        )
        available = (directory / "summary.json").is_file() and (
            directory / "graph.json"
        ).is_file()
        summary = (
            json.loads((directory / "summary.json").read_text()) if available else {}
        )
        entries.append(
            {
                "repo": repo,
                "revision": manifest["revision"],
                "split": manifest["split"],
                "source_url": "https://github.com/" + repo,
                "deletable": manifest["split"] == "submitted",
                "available": available,
                "summary": summary,
            }
        )
    return entries


@app.get("/api/v1/snapshots")
def snapshots(repo: str):
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, "Repository unavailable")
    return [{"revision": manifest["revision"], "pinned": True}]


@app.get("/api/v1/source", response_model=SourceResponse)
def source(repo: str, revision: str, path: str, start: int = 1, lines: int = 80):
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, "Repository unavailable")
    if (
        not re.fullmatch("[0-9a-f]{40}", revision)
        or not eligible(path)
        or path.startswith(("/", "\\"))
        or ".." in path.replace("\\", "/").split("/")
        or not 1 <= start <= 1000000
        or not 1 <= lines <= 200
    ):
        raise HTTPException(422, "Invalid source revision, path or line range")
    clone = ROOT / "data/raw" / repo.replace("/", "__")
    check = subprocess.run(
        [
            "git",
            "-C",
            str(clone),
            "merge-base",
            "--is-ancestor",
            revision,
            manifest["revision"],
        ],
        capture_output=True,
        timeout=60,
    )
    if check.returncode:
        raise HTTPException(422, "Revision outside pinned history")
    try:
        size = int(git(clone, "cat-file", "-s", revision + ":" + path))
        if size > 2 * 1024 * 1024:
            raise HTTPException(413, "Source exceeds preview size limit")
        content = git(clone, "show", revision + ":" + path)
    except subprocess.SubprocessError as exc:
        raise HTTPException(404, "Source unavailable at this revision") from exc
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Source exceeds preview size limit")
    rows = content.decode("utf-8", "replace").splitlines()
    return {
        "repo": repo,
        "revision": revision,
        "path": path,
        "start": start,
        "total_lines": len(rows),
        "lines": rows[start - 1 : start - 1 + lines],
    }


@app.get("/api/v1/seeds")
def seeds(repo: str, search: str = "", kind: str = "file", limit: int = 100):
    if not 1 <= limit <= 1000 or kind not in (
        "file",
        "function",
        "class",
        "test",
        "all",
    ):
        raise HTTPException(422, "Invalid seed kind or limit")
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, "Repository unavailable")
    path = (
        ROOT
        / "data/processed"
        / repo.replace("/", "__")
        / manifest["revision"]
        / "graph.json"
    )
    if not path.is_file():
        raise HTTPException(
            409, "Snapshot data is missing. Restore or index this repository first."
        )
    graph = json.loads(path.read_text())
    return [
        node
        for node in entity_records(graph, repo, manifest["revision"])
        if (kind == "all" or node["kind"] == kind)
        and search.casefold() in (node["path"] + node["qualified_name"]).casefold()
    ][:limit]


@app.get("/api/files")
def files(repo: str, target: str = ""):
    manifest = serve.load_manifests().get(repo)
    if manifest is None:
        raise HTTPException(404, "Repository unavailable")
    if target:
        if not re.fullmatch("[0-9a-f]{40}", target):
            raise HTTPException(422, "Historical commit must be a full SHA")
        clone = ROOT / "data/raw" / repo.replace("/", "__")
        ancestry = subprocess.run(
            [
                "git",
                "-C",
                str(clone),
                "merge-base",
                "--is-ancestor",
                target,
                manifest["revision"],
            ],
            capture_output=True,
            timeout=60,
        )
        if ancestry.returncode:
            raise HTTPException(422, "Commit outside pinned history")
        parents = (
            git(clone, "rev-list", "--parents", "-n", "1", target).decode().split()
        )
        if len(parents) != 2:
            raise HTTPException(422, "Select a single-parent commit")
        entries = git(clone, "ls-tree", "-r", "-z", parents[1]).split(b"\0")
        names = []
        for entry in entries:
            if not entry:
                continue
            metadata, raw = entry.split(b"\t", 1)
            path = raw.decode("utf-8", "surrogateescape")
            if metadata.startswith(b"100") and eligible(path):
                names.append(path)
        return sorted(names)
    path = (
        ROOT
        / "data/processed"
        / repo.replace("/", "__")
        / manifest["revision"]
        / "graph.json"
    )
    if not path.is_file():
        raise HTTPException(
            409, "Snapshot data is missing. Restore or index this repository first."
        )
    return sorted(
        n["path"] for n in json.loads(path.read_text())["nodes"] if n["kind"] == "file"
    )


@app.post("/api/v1/analysis", response_model=AnalysisResponse)
def analysis(request: Analysis):
    if request.repo not in serve.load_manifests():
        raise HTTPException(404, "Repository unavailable")
    try:
        result = analyze(
            request.repo,
            request.seed,
            request.target or None,
            request.top_k,
            include_evidence=True,
            ranker=request.ranker,
        )
        paths = {request.seed} | {row["path"] for row in result["candidates"]}
        for row in result["candidates"]:
            paths.update(row["evidence"]["import_path"])
        graph = result["graph"]
        selected = [node for node in graph["nodes"] if node["path"] in paths]
        selected.sort(key=lambda node: (node["kind"] != "file", node["id"]))
        selected = selected[:500]
        ids = {node["id"] for node in selected}
        result["graph"] = {
            "nodes": selected,
            "edges": [
                edge
                for edge in graph["edges"]
                if edge["source"] in ids and edge["target"] in ids
            ],
            "total_nodes": len(graph["nodes"]),
            "truncated": len(selected) < len(graph["nodes"]),
            "node_limit": 500,
        }
        result["entities"] = [
            node for node in result["entities"] if node["legacy_id"] in ids
        ]
        return result
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            409,
            "Snapshot data is missing. Restore or index the repository before analysis.",
        ) from exc


@app.get("/api/analyze")
def legacy_analysis(repo: str, seed: str, target: str = ""):
    return analysis(Analysis(repo=repo, seed=seed, target=target))


@app.post("/api/v1/explanations")
def explanation(request: Explanation):
    from neural_cartographer.evidence.explain import explain

    result = analysis(
        Analysis(
            **{**request.model_dump(exclude={"candidate", "use_gemini"}), "top_k": 100}
        )
    )
    rows = result["candidates"] + result.get("recommended_tests", [])
    candidate = next((row for row in rows if row["path"] == request.candidate), None)
    if candidate is None:
        raise HTTPException(422, "Candidate is outside the displayed evidence pool")
    return explain(result, candidate, request.use_gemini)


@app.post("/api/ingest", status_code=202)
@app.post("/api/v1/jobs", status_code=202, response_model=JobStatus)
def submit(request: Submission):
    try:
        repo = public_repo_id(request.url.strip())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    manifests = [
        json.loads(p.read_text()) for p in (ROOT / "data/manifests").glob("*.json")
    ]
    if any(m["repo"].lower() == repo.lower() for m in manifests):
        raise HTTPException(409, "Repository already ingested")
    return launch_job(repo, request.url.strip())


def launch_job(repo, url):
    try:
        job, _ = JOB_STORE.create(repo)
    except JobError as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    threading.Thread(
        target=run_ingestion_job, args=(job, url, repo), daemon=True
    ).start()
    return {"job": job, "repo": repo, "status": "running"}


@app.get("/api/jobs")
def job_status(id: str):
    try:
        return JOB_STORE.get(id)
    except JobError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.get("/api/v1/jobs", response_model=list[JobStatus])
def recent_jobs():
    return JOB_STORE.list()


@app.post("/api/v1/jobs/{job_id}/retry", status_code=202, response_model=JobStatus)
def retry_job(job_id: str):
    previous = job_status(job_id)
    if previous["status"] not in ("failed", "cancelled"):
        raise HTTPException(409, "Only failed or cancelled jobs can be retried")
    repo = previous["repo"]
    public_repo_id("https://github.com/" + repo)
    manifest_path = ROOT / "data/manifests" / (repo.replace("/", "__") + ".json")
    if (
        manifest_path.is_file()
        and json.loads(manifest_path.read_text())["split"] != "submitted"
    ):
        raise HTTPException(
            409, "Pinned study repositories cannot be retried as submissions"
        )
    return launch_job(repo, "https://github.com/" + repo)


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatus)
def versioned_job_status(job_id: str):
    return job_status(job_id)


@app.post("/api/v1/jobs/{job_id}/cancel", response_model=JobStatus)
def cancel_job(job_id: str):
    try:
        return JOB_STORE.cancel(job_id)
    except JobError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


@app.delete("/api/v1/repositories/{owner}/{name}")
def delete_repository(owner: str, name: str):
    try:
        repo = public_repo_id(f"https://github.com/{owner}/{name}")
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    key = repo.replace("/", "__")
    manifest_path = ROOT / "data/manifests" / (key + ".json")
    if not manifest_path.exists():
        raise HTTPException(404, "Repository unavailable")
    manifest = json.loads(manifest_path.read_text())
    if manifest["split"] != "submitted":
        raise HTTPException(
            409, "Pinned research repositories cannot be deleted through the API"
        )
    with serve.LOCK:
        if JOB_STORE.running(repo):
            raise HTTPException(409, "Cancel active ingestion before deletion")
        destination = ROOT / "data/deleted" / (key + "-" + uuid.uuid4().hex)
        destination.mkdir(parents=True)
        for label, source in [
            ("manifest.json", manifest_path),
            ("raw", ROOT / "data/raw" / key),
            ("processed", ROOT / "data/processed" / key),
        ]:
            if source.exists():
                shutil.move(str(source), str(destination / label))
    return {
        "status": "archived",
        "repo": repo,
        "recovery_path": str(destination.relative_to(ROOT)),
    }
