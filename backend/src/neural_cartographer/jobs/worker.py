"""Bounded subprocess ingestion with cross-worker cancellation and heartbeat."""

import json
import os
import subprocess
import sys
import time

from neural_cartographer.ingest.pipeline import ROOT
from neural_cartographer.jobs.processes import stop_process_tree
from neural_cartographer.jobs.store import JobStore

STORE = JobStore(ROOT / "artifacts/jobs/jobs.sqlite")
MAX_REPOSITORY_BYTES = 2 * 1024 * 1024 * 1024


def execute(identifier, arguments, repo, started, stage):
    process = None
    try:
        if STORE.get(identifier)["status"] != "running":
            STORE.update(identifier, status="cancelled")
            return False
        process = subprocess.Popen(
            [sys.executable, "-u", *arguments],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        while True:
            if STORE.get(identifier)["status"] != "running":
                stop_process_tree(process)
                process.communicate()
                STORE.update(identifier, status="cancelled")
                return False
            try:
                stdout, stderr = process.communicate(timeout=2)
                break
            except subprocess.TimeoutExpired as exc:
                raw = ROOT / "data/raw" / repo.replace("/", "__")
                directories = [raw] + list(raw.parent.glob(raw.name + ".cloning-*"))
                size = sum(
                    path.stat().st_size
                    for directory in directories
                    if directory.exists()
                    for path in directory.rglob("*")
                    if path.is_file() and not path.is_symlink()
                )
                elapsed = time.monotonic() - started
                if size > MAX_REPOSITORY_BYTES or elapsed > 3600:
                    raise TimeoutError(
                        "Ingestion exceeded the one-hour or 2 GiB repository limit"
                    )
                progress = {
                    "stage": stage,
                    "repository_bytes": size,
                    "elapsed_seconds": round(elapsed),
                }
                partial = exc.output or b""
                if isinstance(partial, bytes):
                    partial = partial.decode("utf-8", "replace")
                for line in reversed(partial.splitlines()):
                    try:
                        item = json.loads(line)
                        if item.get("stage") == "history":
                            progress.update(
                                {
                                    key: item[key]
                                    for key in ("stage", "commits_scanned", "queries")
                                }
                            )
                            break
                    except (ValueError, AttributeError):
                        continue
                STORE.update(identifier, progress=progress)
        if process.returncode:
            raise RuntimeError((stdout + stderr)[-2000:] or "Ingestion process failed")
        return True
    finally:
        if process is not None and process.poll() is None:
            stop_process_tree(process)
            process.communicate()


def run(identifier, url, repo):
    started = time.monotonic()
    try:
        if not execute(
            identifier,
            [
                str(ROOT / "scripts/ingest.py"),
                "--public-url",
                url,
                "--clone",
                "--reuse",
            ],
            repo,
            started,
            "cloning or parsing",
        ):
            return
        learned = (
            ROOT / "artifacts/models/heterogeneous-development/model.pt"
        ).is_file()
        if learned:
            manifest = json.loads(
                (
                    ROOT / "data/manifests" / (repo.replace("/", "__") + ".json")
                ).read_text()
            )
            if not execute(
                identifier,
                [
                    str(ROOT / "scripts/embeddings.py"),
                    "--repo",
                    repo,
                    "--revision",
                    manifest["revision"],
                ],
                repo,
                started,
                "semantic indexing",
            ):
                return
        STORE.update(
            identifier,
            status="processed",
            semantic_ready=learned,
            progress={
                "stage": "complete",
                "elapsed_seconds": round(time.monotonic() - started),
            },
        )
    except Exception as exc:  # Persist unexpected worker failures for explicit retry.
        STORE.update(identifier, status="failed", error=str(exc))
