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
from urllib.parse import urlsplit
try:
    import tree_sitter
    import tree_sitter_python
except ImportError:
    tree_sitter = tree_sitter_python = None

ROOT = Path(__file__).resolve().parents[1]
VERSION = "4"
EXCLUDED = {"vendor", "vendored", "_vendor", "node_modules", ".venv", "build", "dist"}


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], timeout=600)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def eligible(path):
    return path.endswith(".py") and not EXCLUDED.intersection(Path(path).parts)


def public_repo_id(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or
            parsed.fragment or parsed.username or parsed.password):
        raise ValueError("Only public https://github.com/owner/repo URLs are accepted")
    repo_id = parsed.path.strip("/")
    if repo_id.endswith(".git"):
        repo_id = repo_id[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_id):
        raise ValueError("Expected a GitHub owner/repository URL")
    return repo_id


def history(repo, revision):
    """One Git traversal; raw statuses plus whitespace-aware numeric diffs."""
    tokens = iter(git(repo, "log", revision, "--no-merges", "--reverse", "--topo-order",
                      "--format=NC_COMMIT %H %P %ct", "--raw", "--numstat", "-z", "-w",
                      "--no-renames").split(b"\0"))
    event, statuses, substantive = None, {}, set()
    def finish():
        if event is not None:
            for path, status in statuses.items():
                if eligible(path) and path not in substantive and status == "M":
                    if len(statuses) > 50:
                        substantive.add(path)
                        continue  # bulk events are excluded from query labels
                    # Whitespace can change Python block structure or string values.
                    try:
                        before_source = git(repo, "show", event["parent"] + ":" + path)
                        after_source = git(repo, "show", event["commit"] + ":" + path)
                        if max(len(before_source), len(after_source)) > 2_000_000:
                            substantive.add(path)
                            continue
                        before = ast.dump(ast.parse(before_source))
                        after = ast.dump(ast.parse(after_source))
                        if before != after:
                            substantive.add(path)
                    except (SyntaxError, ValueError, UnicodeError, subprocess.SubprocessError):
                        substantive.add(path)  # retain uncertain changes, never silently drop
            event["changes"] = [{"status": status, "path": path}
                                for path, status in statuses.items() if path in substantive and eligible(path)]
        return event
    for token in tokens:
        token = token.lstrip(b"\n")
        if token.startswith(b"NC_COMMIT "):
            if event is not None:
                yield finish()
            fields = token.decode().split()[1:]
            event = ({"commit": fields[0], "parent": fields[1], "timestamp": int(fields[2])}
                     if len(fields) == 3 else None)
            statuses, substantive = {}, set()
        elif token.startswith(b":"):
            path = next(tokens).decode("utf-8", "surrogateescape")
            statuses[path] = token.split()[-1].decode()
        elif b"\t" in token:
            added, removed, path = token.split(b"\t", 2)
            if added not in (b"0", b"-") or removed not in (b"0", b"-"):
                substantive.add(path.decode("utf-8", "surrogateescape"))
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
                    name = source[name_node.start_byte:name_node.end_byte].decode("utf-8", "replace")
                    identifier = f"{parent}::{name}@{node.start_point.row + 1}"
                    kind = "class" if node.type == "class_definition" else "function"
                    if kind == "function" and name.startswith("test_"):
                        kind = "test"
                    nodes.append({"id": identifier, "kind": kind, "path": path,
                                  "start": node.start_point.row + 1, "end": node.end_point.row + 1})
                    edges.append({"source": parent, "target": identifier, "relation": "CONTAINS"})
                    parent = identifier
            if node.type in ("import_statement", "import_from_statement"):
                edges.append({"source": path, "target": source[node.start_byte:node.end_byte].decode("utf-8", "replace"),
                              "relation": "IMPORTS", "resolution": "statement_text", "line": node.start_point.row + 1})
            for child in node.named_children:
                fallback(child, parent)
        fallback(parsed.root_node, path)
        return nodes, edges, ("tree-sitter syntax errors: " + str(exc)) if parsed.root_node.has_error else None

    def visit(parent, children):
        for item in children:
            if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                identifier = f"{parent}::{item.name}@{item.lineno}"
                kind = "class" if isinstance(item, ast.ClassDef) else "function"
                if kind == "function" and item.name.startswith("test_"):
                    kind = "test"
                nodes.append({"id": identifier, "kind": kind, "path": path,
                              "start": item.lineno, "end": item.end_lineno})
                edges.append({"source": parent, "target": identifier, "relation": "CONTAINS"})
                visit(identifier, item.body)
            else:
                visit(parent, list(ast.iter_child_nodes(item)))
    visit(path, tree.body)
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            for name in item.names:
                edges.append({"source": path, "target": name.name, "relation": "IMPORTS",
                              "resolution": "module_name", "line": item.lineno})
        elif isinstance(item, ast.ImportFrom):
            edges.append({"source": path, "target": "." * item.level + (item.module or ""),
                          "relation": "IMPORTS", "resolution": "module_name", "line": item.lineno})
    return nodes, edges, None


def process(repo_id, split, clone=False):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo_id):
        raise ValueError("Expected owner/repository")
    key = repo_id.replace("/", "__")
    repo = ROOT / "data/raw" / key
    url = f"https://github.com/{repo_id}.git"
    if not repo.exists():
        if not clone:
            raise RuntimeError(f"Missing clone: {repo}; run with --clone")
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "-c", "http.followRedirects=false", "clone", "--single-branch",
                        "--no-checkout", url, str(repo)], check=True, timeout=3600,
                       env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if git(repo, "remote", "get-url", "origin").decode().strip() != url:
        raise ValueError("Unexpected clone origin")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Full history required")
    pin_path = ROOT / "data/manifests" / f"{key}.json"
    prior = json.loads(pin_path.read_text()) if pin_path.exists() else None
    sha = prior["revision"] if prior else git(repo, "rev-parse", "HEAD").decode().strip()
    out = ROOT / "data/processed" / key / sha
    out.mkdir(parents=True, exist_ok=True)
    paths = git(repo, "ls-tree", "-r", "-z", sha).split(b"\0")
    nodes, edges, failures, skipped, licenses = [], [], [], [], []
    batch = subprocess.Popen(["git", "-C", str(repo), "cat-file", "--batch"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE)
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
    write(out / "graph.json", {"revision": sha, "nodes": nodes, "edges": edges,
                               "unresolved_imports": True})
    # All non-merge ancestors, parent references preserved. No future features built here.
    counts = {"commits": int(git(repo, "rev-list", "--count", "--no-merges", sha)),
              "eligible_events": 0, "queries": 0, "bulk_events": 0}
    run_id = uuid.uuid4().hex
    events_tmp = out / ("events.jsonl." + run_id + ".tmp")
    queries_tmp = out / ("queries.jsonl." + run_id + ".tmp")
    with events_tmp.open("w") as events, queries_tmp.open("w") as queries:
        for event in history(repo, sha):
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
                queries.write(json.dumps({"repo": repo_id, "split": split, "commit": commit,
                                          "graph_revision": parent, "seed": seed,
                                          "positives": [p for p in labels if p != seed],
                                          "features_materialized": False}) + "\n")
                counts["queries"] += 1
    events_tmp.replace(out / "events.jsonl")
    queries_tmp.replace(out / "queries.jsonl")
    summary = {"repo": repo_id, "url": url, "split": split, "revision": sha,
               "pipeline_version": VERSION, "parser": "python-stdlib-ast+tree-sitter-fallback" if tree_sitter else "python-stdlib-ast", "counts": counts,
               "nodes": len(nodes), "edges": len(edges), "parse_failures": failures,
               "skipped_files": skipped, "license_files": licenses,
               "limitations": ["Imports not resolved", "No historical graph/features materialized",
                               "File-level modified-file labels only; no rename/function labels",
                               "Tree-sitter fallback requires the pinned virtual environment"]}
    summary["checksums"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in out.iterdir() if p.suffix in (".json", ".jsonl") and p.name != "summary.json"}
    write(out / "summary.json", summary)
    write(pin_path, {"repo": repo_id, "split": split, "revision": sha, "url": url})
    return {"repo": repo_id, "status": "processed", "summary": str(out / "summary.json"), **counts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clone", action="store_true")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--repo", help="Process one owner/repo from catalog")
    selection.add_argument("--public-url", help="Ingest a submitted public GitHub URL")
    parser.add_argument("--split", action="append", choices=["train", "validation", "test"])
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
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
        jobs = [(repo, split) for split, repos in config.items() for repo in repos
                if (not args.repo or repo == args.repo) and (not args.split or split in args.split)]
    if not jobs:
        parser.error("Unknown repository")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, repo, split, args.clone): repo for repo, split in jobs}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:
                result = {"repo": futures[future], "status": "failed", "error": str(exc)}
            results.append(result)
            print(json.dumps(result), flush=True)
            write(ROOT / "artifacts/reports/ingestion.json", results)
    raise SystemExit(any(r["status"] == "failed" for r in results))


if __name__ == "__main__":
    main()
