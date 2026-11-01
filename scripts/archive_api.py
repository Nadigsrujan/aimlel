"""Bounded ZIP inspection. Never extracts paths or executes archive contents."""

import hashlib
import io
import json
import re
from collections import defaultdict, deque
from pydantic import BaseModel, Field
from pathlib import PurePosixPath
import stat
import zipfile
from fastapi import HTTPException, Request
from starlette.concurrency import run_in_threadpool


def inspect_archive(body):
    from neural_cartographer.ingest.pipeline import extract, eligible
    from neural_cartographer.contracts.schema import entity_records
    from neural_cartographer.graph.structure import resolve_imports
    from neural_cartographer.graph.relations import lexical_edges

    if len(body) > 20 * 1024 * 1024:
        raise ValueError("Compressed archive exceeds 20 MiB")
    revision = hashlib.sha256(body).hexdigest()
    nodes, edges, errors, sources = [], [], [], {}
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        entries = archive.infolist()
        if len(entries) > 5000:
            raise ValueError("Archive exceeds 5000 entries")
        if sum(e.file_size for e in entries) > 50 * 1024 * 1024:
            raise ValueError("Expanded archive exceeds 50 MiB")
        seen = set()
        for entry in entries:
            name = entry.orig_filename
            parts = PurePosixPath(name).parts
            mode = (entry.external_attr >> 16) & 0xFFFF
            if (
                "\\" in name
                or name.startswith("/")
                or any(p in ("..", ".") or ":" in p for p in parts)
                or "\x00" in name
                or stat.S_ISLNK(mode)
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
            ):
                raise ValueError("Unsafe archive path or special entry")
            if name.casefold() in seen:
                raise ValueError("Duplicate archive paths")
            seen.add(name.casefold())
            if entry.flag_bits & 1:
                raise ValueError("Encrypted ZIP is unsupported")
            if entry.file_size / max(1, entry.compress_size) > 200:
                raise ValueError("Suspicious archive compression ratio")
            if entry.is_dir() or not eligible(name):
                continue
            if entry.file_size > 2_000_000:
                raise ValueError("Source file exceeds 2 MB")
            with archive.open(entry) as stream:
                content = stream.read(2_000_001)
            if len(content) > 2_000_000:
                raise ValueError("Expanded source exceeds limit")
            if b"\0" in content:
                continue
            n, e, error = extract(name, content)
            extra, _ = lexical_edges(name, content, n)
            nodes.extend(n)
            edges.extend(e + extra)
            sources[name] = content.decode("utf-8", "replace")
            if error:
                errors.append({"path": name, "error": error})
    if not sources:
        raise ValueError("Archive contains no supported Python source")
    raw = {"nodes": nodes, "edges": edges}
    imports, unresolved = resolve_imports(raw)
    edges = [e for e in edges if e["relation"] != "IMPORTS"] + imports
    entities = entity_records(raw, "archive/upload", revision)
    ids = {n["legacy_id"]: n["id"] for n in entities}
    return {
        "repo": "archive/upload",
        "revision": revision,
        "nodes": entities,
        "edges": [
            {**e, "source": ids[e["source"]], "target": ids[e["target"]]}
            for e in edges
            if e["source"] in ids and e["target"] in ids
        ],
        "quality": {
            "entities": len(entities),
            "unresolved_edges": len(unresolved),
            "parse_failures": errors,
        },
        "provenance": "Uploaded ZIP content hash; source snapshot only, no Git history or trained forecast",
        "sources": sources,
    }


class ArchiveForecast(BaseModel):
    seed: str = Field(min_length=1, max_length=4096)


def install(app, root):
    directory = root / "artifacts/archive-snapshots"

    @app.post("/api/v1/observatory/archives")
    async def upload(request: Request):
        body = bytearray()
        async for part in request.stream():
            body.extend(part)
            if len(body) > 20 * 1024 * 1024:
                raise HTTPException(413, "Compressed archive exceeds 20 MiB")
        try:
            value = await run_in_threadpool(inspect_archive, bytes(body))
        except (
            ValueError,
            zipfile.BadZipFile,
            RuntimeError,
            RecursionError,
            NotImplementedError,
        ) as exc:
            raise HTTPException(
                422, "Invalid or unsupported archive: " + str(exc)
            ) from exc
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / (value["revision"] + ".json")
        existing = list(directory.glob("*.json"))
        if (
            not destination.exists()
            and sum(p.stat().st_size for p in existing) > 500 * 1024 * 1024
        ):
            raise HTTPException(413, "Local archive retention quota reached")
        from neural_cartographer.ingest.pipeline import write

        await run_in_threadpool(write, destination, value)
        return value

    @app.post("/api/v1/observatory/archives/{revision}/forecast")
    def forecast(revision: str, request: ArchiveForecast):
        if not re.fullmatch(r"[0-9a-f]{64}", revision):
            raise HTTPException(422, "Invalid archive content hash")
        path = directory / (revision + ".json")
        if not path.is_file():
            raise HTTPException(404, "Archive snapshot unavailable")
        graph = json.loads(path.read_text())
        files = {n["id"]: n["path"] for n in graph["nodes"] if n["kind"] == "file"}
        if request.seed not in files.values():
            raise HTTPException(422, "Seed must exist in the uploaded source snapshot")
        adjacency = defaultdict(set)
        for edge in graph["edges"]:
            if (
                edge["relation"] == "IMPORTS"
                and edge["source"] in files
                and edge["target"] in files
            ):
                a, b = files[edge["source"]], files[edge["target"]]
                adjacency[a].add(b)
                adjacency[b].add(a)
        paths = {request.seed: [request.seed]}
        queue = deque([request.seed])
        while queue:
            current = queue.popleft()
            if len(paths[current]) > 3:
                continue
            for neighbor in sorted(adjacency[current]):
                if neighbor not in paths:
                    paths[neighbor] = paths[current] + [neighbor]
                    queue.append(neighbor)
        from neural_cartographer.candidates.ranking import rank

        rows = rank(list(files.values()), request.seed)
        for row in rows:
            route = paths.get(row["path"], [])
            structural = 1 / len(route) if route else 0
            row.update(
                score=(row["score"] + structural) / 2,
                channels=["directory"] + (["structural"] if route else []),
                evidence={"import_path": route, "past_commits": []},
            )
        rows.sort(key=lambda r: (-r["score"], r["path"]))
        return {
            "repo": graph["repo"],
            "graph_revision": revision,
            "seed": request.seed,
            "ranker": "archive-static-directory-v1",
            "model_status": "BASELINE / NOT TRAINED",
            "score_is_probability": False,
            "candidate_count": len(rows),
            "candidates": rows[:100],
            "limitation": "Static import proximity plus directory distance only. No Git evolution, CodeBERT inference, learned weights, runtime failure or coverage claim.",
        }
