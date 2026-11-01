"""Reproducible offline Git ingestion. Never imports or executes target code."""

import argparse
import ast
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import uuid
from functools import lru_cache
import warnings
import importlib
import time
from urllib.parse import urlsplit

try:
    import tree_sitter
    import tree_sitter_python
except ImportError:
    tree_sitter = tree_sitter_python = None

ROOT = Path(
    os.environ.get("NEURAL_CARTOGRAPHER_HOME", Path(__file__).resolve().parents[4])
).resolve()
VERSION = "5"
EXCLUDED = {"vendor", "vendored", "_vendor", "node_modules", ".venv", "build", "dist"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], timeout=600)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    # Windows indexers/virus scanners may briefly hold a newly read report.
    # Retain atomic publication and only retry sharing/access violations.
    for attempt in range(8):
        try:
            tmp.replace(path)
            break
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.05 * (2**attempt))


def eligible(path):
    return path.endswith(".py") and not EXCLUDED.intersection(Path(path).parts)


def public_repo_id(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Only public https://github.com/owner/repo URLs are accepted")
    repo_id = parsed.path.strip("/")
    if repo_id.endswith(".git"):
        repo_id = repo_id[:-4]
    if not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9_-]*/[A-Za-z0-9_.-]+", repo_id
    ) or repo_id.split("/")[-1] in (".", ".."):
        raise ValueError("Expected a GitHub owner/repository URL")
    return repo_id


def history(repo, revision):
    from neural_cartographer.graph.snapshots import blob_reader
    from neural_cartographer.ingest.signatures import SignatureCache

    with blob_reader(repo) as read, SignatureCache(repo, VERSION) as cache:
        yield from _history(repo, revision, read, cache)


def _history(repo, revision, read, cache):
    """Raw blob identities plus AST comparison; never compute unrelated text diffs."""

    @lru_cache(maxsize=8192)
    def signature(blob):
        try:
            return cache.get(blob)
        except KeyError:
            pass
        source = read(blob)
        digest = None
        if source is not None:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    digest = hashlib.sha256(
                        ast.dump(ast.parse(source)).encode()
                    ).digest()
            except (SyntaxError, ValueError, UnicodeError):
                pass
        cache.put(blob, digest)
        return digest

    tokens = iter(
        git(
            repo,
            "log",
            revision,
            "--no-merges",
            "--reverse",
            "--topo-order",
            "--format=NC_COMMIT %H %P %ct",
            "--raw",
            "-z",
            "--no-renames",
            "--no-abbrev",
        ).split(b"\0")
    )
    event, statuses, substantive, blobs = None, {}, set(), {}

    def finish():
        if event is not None:
            for path, status in statuses.items():
                if eligible(path) and status == "M":
                    if len(statuses) > 50:
                        substantive.add(path)
                        continue  # bulk events are excluded from query labels
                    # Whitespace can change Python block structure or string values.
                    try:
                        before = signature(blobs[path][0])
                        after = signature(blobs[path][1])
                        if before is None or after is None:
                            substantive.add(path)
                            continue
                        if before != after:
                            substantive.add(path)
                        else:
                            substantive.discard(path)
                    except (
                        SyntaxError,
                        ValueError,
                        UnicodeError,
                        subprocess.SubprocessError,
                    ):
                        substantive.add(
                            path
                        )  # retain uncertain changes, never silently drop
            event["changes"] = [
                {"status": status, "path": path}
                for path, status in statuses.items()
                if path in substantive and eligible(path)
            ]
        return event

    for token in tokens:
        token = token.lstrip(b"\n")
        if token.startswith(b"NC_COMMIT "):
            if event is not None:
                yield finish()
            fields = token.decode().split()[1:]
            event = (
                {"commit": fields[0], "parent": fields[1], "timestamp": int(fields[2])}
                if len(fields) == 3
                else None
            )
            statuses, substantive, blobs = {}, set(), {}
        elif token.startswith(b":"):
            path = next(tokens).decode("utf-8", "surrogateescape")
            statuses[path] = token.split()[-1].decode()
            blobs[path] = token.split()[2:4]
            substantive.add(path)
    if event is not None:
        yield finish()


def extract(path, source):
    if isinstance(source, str):
        source = source.encode("utf-8")
    nodes = [{"id": path, "kind": "file", "path": path}]
    edges = []
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, UnicodeError) as exc:
        if tree_sitter is None:
            return nodes, edges, str(exc)
        parser = tree_sitter.Parser(tree_sitter.Language(tree_sitter_python.language()))
        parsed = parser.parse(source)

        def fallback(node, parent):
            if node.type in ("class_definition", "function_definition"):
                name_node = node.child_by_field_name("name")
                if name_node is not None:
                    name = source[name_node.start_byte : name_node.end_byte].decode(
                        "utf-8", "replace"
                    )
                    identifier = f"{parent}::{name}@{node.start_point.row + 1}"
                    kind = "class" if node.type == "class_definition" else "function"
                    if kind == "function" and name.startswith("test_"):
                        kind = "test"
                    nodes.append(
                        {
                            "id": identifier,
                            "kind": kind,
                            "path": path,
                            "start": node.start_point.row + 1,
                            "end": node.end_point.row + 1,
                        }
                    )
                    edges.append(
                        {"source": parent, "target": identifier, "relation": "CONTAINS"}
                    )
                    parent = identifier
            if node.type in ("import_statement", "import_from_statement"):
                edges.append(
                    {
                        "source": path,
                        "target": source[node.start_byte : node.end_byte].decode(
                            "utf-8", "replace"
                        ),
                        "relation": "IMPORTS",
                        "resolution": "statement_text",
                        "line": node.start_point.row + 1,
                    }
                )
            for child in node.named_children:
                fallback(child, parent)

        fallback(parsed.root_node, path)
        return (
            nodes,
            edges,
            ("tree-sitter syntax errors: " + str(exc))
            if parsed.root_node.has_error
            else None,
        )

    def visit(parent, children):
        for item in children:
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                identifier = f"{parent}::{item.name}@{item.lineno}"
                kind = "class" if isinstance(item, ast.ClassDef) else "function"
                if kind == "function" and item.name.startswith("test_"):
                    kind = "test"
                nodes.append(
                    {
                        "id": identifier,
                        "kind": kind,
                        "path": path,
                        "start": item.lineno,
                        "end": item.end_lineno,
                    }
                )
                edges.append(
                    {"source": parent, "target": identifier, "relation": "CONTAINS"}
                )
                visit(identifier, item.body)
            else:
                visit(parent, list(ast.iter_child_nodes(item)))

    visit(path, tree.body)
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            for name in item.names:
                edges.append(
                    {
                        "source": path,
                        "target": name.name,
                        "relation": "IMPORTS",
                        "resolution": "module_name",
                        "line": item.lineno,
                    }
                )
        elif isinstance(item, ast.ImportFrom):
            edges.append(
                {
                    "source": path,
                    "target": "." * item.level + (item.module or ""),
                    "relation": "IMPORTS",
                    "resolution": "module_name",
                    "line": item.lineno,
                }
            )
    return nodes, edges, None


def process(repo_id, split, clone=False, reuse=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_id):
        raise ValueError("Expected owner/repository")
    key = repo_id.replace("/", "__")
    repo = ROOT / "data/raw" / key
    url = f"https://github.com/{repo_id}.git"
    if not repo.exists():
        if not clone:
            raise RuntimeError(f"Missing clone: {repo}; run with --clone")
        repo.parent.mkdir(parents=True, exist_ok=True)
        staging = repo.with_name(repo.name + ".cloning-" + uuid.uuid4().hex)
        staging.relative_to(ROOT / "data/raw")
        repo.relative_to(ROOT / "data/raw")
        subprocess.run(
            [
                "git",
                "-c",
                "http.followRedirects=false",
                "clone",
                "--single-branch",
                "--no-checkout",
                url,
                str(staging),
            ],
            check=True,
            timeout=3600,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        # Interrupted clones never become the canonical repository. A retry
        # starts a new staging clone; incomplete staging is retained for audit.
        staging.rename(repo)
    if git(repo, "remote", "get-url", "origin").decode().strip() != url:
        raise ValueError("Unexpected clone origin")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Full history required")
    pin_path = ROOT / "data/manifests" / f"{key}.json"
    prior = json.loads(pin_path.read_text()) if pin_path.exists() else None
    sha = (
        prior["revision"] if prior else git(repo, "rev-parse", "HEAD").decode().strip()
    )
    try:
        git(repo, "cat-file", "-e", sha + "^{commit}")
    except subprocess.CalledProcessError:
        if not clone:
            raise ValueError(
                "Pinned revision is missing; rerun with --clone to recover the clone"
            )
        subprocess.run(
            [
                "git",
                "-c",
                "http.followRedirects=false",
                "-C",
                str(repo),
                "fetch",
                "origin",
                sha,
            ],
            check=True,
            timeout=3600,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    out = ROOT / "data/processed" / key / sha
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    if reuse and summary_path.is_file():
        saved = json.loads(summary_path.read_text())
        if saved["pipeline_version"] == VERSION and all(
            (out / name).is_file()
            and hashlib.sha256((out / name).read_bytes()).hexdigest() == checksum
            for name, checksum in saved["checksums"].items()
        ):
            return {
                "repo": repo_id,
                "status": "processed",
                "summary": str(summary_path),
                "reused": True,
                **saved["counts"],
            }
    paths = git(repo, "ls-tree", "-r", "-z", sha).split(b"\0")
    nodes, edges, failures, skipped, licenses = [], [], [], [], []
    batch = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    try:
        for entry in paths:
            if not entry:
                continue
            metadata, rawpath = entry.split(b"\t", 1)
            mode, kind, blob = metadata.split()
            path = rawpath.decode("utf-8", "surrogateescape")
            if kind != b"blob" or mode == b"120000":
                continue
            if Path(path).name.lower().startswith(("license", "copying")):
                licenses.append({"path": path, "blob": blob.decode()})
            if not eligible(path):
                continue
            batch.stdin.write(blob + b"\n")
            batch.stdin.flush()
            header = batch.stdout.readline().split()
            if len(header) != 3 or header[1] != b"blob":
                raise RuntimeError("Unexpected Git blob response")
            size = int(header[2])
            if size > 2_000_000:
                remaining = size + 1
                while remaining:
                    remaining -= len(batch.stdout.read(min(remaining, 65536)))
                skipped.append({"path": path, "reason": "over_2MB"})
                continue
            content = batch.stdout.read(size)
            batch.stdout.read(1)  # batch separator
            n, e, error = extract(path, content)
            nodes.extend(n)
            edges.extend(e)
            if error:
                failures.append({"path": path, "error": error})
    finally:
        batch.stdin.close()
        batch.stdout.close()
        if batch.wait(timeout=60):
            raise RuntimeError("Git batch reader failed")
    write(
        out / "graph.json",
        {"revision": sha, "nodes": nodes, "edges": edges, "unresolved_imports": True},
    )
    # All non-merge ancestors, parent references preserved. No future features built here.
    counts = {
        "commits": int(git(repo, "rev-list", "--count", "--no-merges", sha)),
        "eligible_events": 0,
        "queries": 0,
        "bulk_events": 0,
    }
    run_id = uuid.uuid4().hex
    events_tmp = out / ("events.jsonl." + run_id + ".tmp")
    queries_tmp = out / ("queries.jsonl." + run_id + ".tmp")
    with events_tmp.open("w") as events, queries_tmp.open("w") as queries:
        for scanned, event in enumerate(history(repo, sha), 1):
            if scanned % 1000 == 0:
                print(
                    json.dumps(
                        {
                            "repo": repo_id,
                            "stage": "history",
                            "commits_scanned": scanned,
                            "queries": counts["queries"],
                        }
                    ),
                    flush=True,
                )
            commit, parent = event["commit"], event["parent"]
            records = event["changes"]
            if not records:
                continue
            events.write(json.dumps(event) + "\n")
            if len(records) > 50:
                counts["bulk_events"] += 1
                continue
            # Only modified files have an unambiguous entity in the parent snapshot.
            labels = sorted(r["path"] for r in records if r["status"] == "M")
            if len(labels) < 2:
                continue
            counts["eligible_events"] += 1
            for seed in labels:
                queries.write(
                    json.dumps(
                        {
                            "repo": repo_id,
                            "split": split,
                            "commit": commit,
                            "graph_revision": parent,
                            "seed": seed,
                            "positives": [p for p in labels if p != seed],
                            "features_materialized": False,
                        }
                    )
                    + "\n"
                )
                counts["queries"] += 1
    events_tmp.replace(out / "events.jsonl")
    queries_tmp.replace(out / "queries.jsonl")
    summary = {
        "repo": repo_id,
        "url": url,
        "split": split,
        "revision": sha,
        "pipeline_version": VERSION,
        "parser": "python-stdlib-ast+tree-sitter-fallback"
        if tree_sitter
        else "python-stdlib-ast",
        "counts": counts,
        "nodes": len(nodes),
        "edges": len(edges),
        "parse_failures": failures,
        "skipped_files": skipped,
        "license_files": licenses,
        "limitations": [
            "Imports not resolved",
            "No historical graph/features materialized",
            "File-level modified-file labels only; no rename/function labels",
            "Tree-sitter fallback requires the pinned virtual environment",
        ],
    }
    summary["checksums"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.iterdir()
        if p.suffix in (".json", ".jsonl") and p.name != "summary.json"
    }
    write(out / "summary.json", summary)
    write(pin_path, {"repo": repo_id, "split": split, "revision": sha, "url": url})
    return {
        "repo": repo_id,
        "status": "processed",
        "summary": str(out / "summary.json"),
        **counts,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clone", action="store_true")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Reuse checksum-verified artifacts at the current pipeline version",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--repo", help="Process one owner/repo from catalog")
    selection.add_argument("--public-url", help="Ingest a submitted public GitHub URL")
    parser.add_argument(
        "--split", action="append", choices=["train", "validation", "test"]
    )
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error("workers must be between 1 and 4")
    config = json.loads((ROOT / "configs/repositories.json").read_text())
    catalog = {repo for repos in config.values() for repo in repos}
    if args.public_url:
        if args.split:
            parser.error("--split only applies to catalog repositories")
        repo_id = public_repo_id(args.public_url)
        if repo_id in catalog:
            parser.error("This repository is in the pinned catalog; use --repo")
        jobs = [(repo_id, "submitted")]
    else:
        jobs = [
            (repo, split)
            for split, repos in config.items()
            for repo in repos
            if (not args.repo or repo == args.repo)
            and (not args.split or split in args.split)
        ]
    if not jobs:
        parser.error("Unknown repository")
    results = []
    # AST signatures are CPU work; separate processes avoid serializing it on the GIL.
    worker = importlib.import_module("neural_cartographer.ingest.pipeline").process
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(worker, repo, split, args.clone, args.reuse): repo
            for repo, split in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {
                    "repo": futures[future],
                    "status": "failed",
                    "error": str(exc),
                }
            results.append(result)
            print(json.dumps(result), flush=True)
            write(ROOT / "artifacts/reports/ingestion.json", results)
    raise SystemExit(any(r["status"] == "failed" for r in results))


if __name__ == "__main__":
    main()
