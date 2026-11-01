"""Conservative same-file lexical calls and inheritance at an exact Git revision."""

import ast
from collections import Counter
import hashlib
import json
from neural_cartographer.ingest.pipeline import ROOT, VERSION, eligible, git, write
from neural_cartographer.graph.snapshots import blob_reader

RELATION_VERSION = "lexical-relations-v1"


class Bindings(ast.NodeVisitor):
    def __init__(self):
        self.names = set()
        self.globals = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_arg(self, node):
        self.names.add(node.arg)

    def visit_Import(self, node):
        self.names.update(
            alias.asname or alias.name.split(".")[0] for alias in node.names
        )

    def visit_ImportFrom(self, node):
        self.names.update(alias.asname or alias.name for alias in node.names)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.names.add(node.name)

    def visit_Nonlocal(self, node):
        self.names.update(node.names)

    def visit_Global(self, node):
        self.globals.update(node.names)

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest:
            self.names.add(node.rest)
        self.generic_visit(node)


def lexical_edges(path, source, nodes):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, UnicodeError):
        return [], {"calls": 0, "resolved_calls": 0, "syntax_unavailable": 1}
    by_line = {
        n["start"]: n for n in nodes if n["path"] == path and n["kind"] != "file"
    }
    scope_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    definitions = [n for n in tree.body if isinstance(n, scope_types[:3])]
    counts = Counter(n.name for n in definitions)
    module_bindings = Bindings()
    for item in tree.body:
        if not isinstance(item, scope_types[:3]):
            module_bindings.visit(item)
    bindings = {}
    for scope in (n for n in ast.walk(tree) if isinstance(n, scope_types)):
        names = Bindings()
        if not isinstance(scope, ast.ClassDef):
            names.visit(scope.args)
        body = [scope.body] if isinstance(scope, ast.Lambda) else scope.body
        for item in body:
            names.visit(item)
        module_bindings.names.update(names.globals & names.names)
        bindings[id(scope)] = names.names
    declarations = {
        n.name: by_line[n.lineno]
        for n in definitions
        if counts[n.name] == 1
        and not n.decorator_list
        and n.lineno in by_line
        and n.name not in module_bindings.names
        and "*" not in module_bindings.names
    }
    edges = []
    audit = {"calls": 0, "resolved_calls": 0, "syntax_unavailable": 0}

    class Calls(ast.NodeVisitor):
        def __init__(self):
            self.scopes = []
            self.owners = [path]

        def resolve(self, name, line):
            target = declarations.get(name)
            if not target:
                return None
            seen_scope = False
            for kind, names in reversed(self.scopes):
                if kind == "function" or not seen_scope:
                    if name in names:
                        return None
                seen_scope = True
            if (
                not any(kind == "function" for kind, _ in self.scopes)
                and line < target["start"]
            ):
                return None
            return target

        def visit_Call(self, node):
            audit["calls"] += 1
            target = (
                self.resolve(node.func.id, node.lineno)
                if isinstance(node.func, ast.Name)
                else None
            )
            if target:
                edges.append(
                    {
                        "source": self.owners[-1],
                        "target": target["id"],
                        "relation": "CALLS",
                        "resolution": "unshadowed-module-symbol",
                        "line": node.lineno,
                    }
                )
                audit["resolved_calls"] += 1
            self.generic_visit(node)

        def visit_FunctionDef(self, node):
            for decorator in node.decorator_list:
                self.visit(decorator)
            self.visit(node.args)
            if node.returns:
                self.visit(node.returns)
            self.scopes.append(("function", bindings[id(node)]))
            self.owners.append(by_line.get(node.lineno, {"id": self.owners[-1]})["id"])
            for item in node.body:
                self.visit(item)
            self.owners.pop()
            self.scopes.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Lambda(self, node):
            self.visit(node.args)
            self.scopes.append(("function", bindings[id(node)]))
            self.visit(node.body)
            self.scopes.pop()

        def visit_ClassDef(self, node):
            for base in node.bases:
                self.visit(base)
                target = (
                    self.resolve(base.id, node.lineno)
                    if isinstance(base, ast.Name)
                    else None
                )
                if target and target["kind"] == "class" and node.lineno in by_line:
                    edges.append(
                        {
                            "source": by_line[node.lineno]["id"],
                            "target": target["id"],
                            "relation": "INHERITS",
                            "resolution": "unshadowed-module-symbol",
                            "line": node.lineno,
                        }
                    )
            for item in node.keywords:
                self.visit(item)
            for item in node.decorator_list:
                self.visit(item)
            self.scopes.append(("class", bindings[id(node)]))
            self.owners.append(by_line.get(node.lineno, {"id": self.owners[-1]})["id"])
            for item in node.body:
                self.visit(item)
            self.owners.pop()
            self.scopes.pop()

    Calls().visit(tree)
    return edges, audit


def enrich_relations(repo_id, revision, graph, root=ROOT):
    node_key = hashlib.sha256(
        json.dumps(sorted(n["id"] for n in graph["nodes"])).encode()
    ).hexdigest()[:16]
    destination = (
        root
        / "data/interim/relation-evidence"
        / repo_id.replace("/", "__")
        / (revision + "-" + VERSION + "-" + RELATION_VERSION + "-" + node_key + ".json")
    )
    if destination.is_file():
        result = json.loads(destination.read_text())
    else:
        edges = []
        audit = {"calls": 0, "resolved_calls": 0, "syntax_unavailable": 0}
        paths = {n["path"] for n in graph["nodes"] if n["kind"] == "file"}
        clone = root / "data/raw" / repo_id.replace("/", "__")
        with blob_reader(clone) as read:
            for entry in git(clone, "ls-tree", "-r", "-z", revision).split(b"\0"):
                if not entry:
                    continue
                metadata, rawpath = entry.split(b"\t", 1)
                mode, kind, blob = metadata.split()
                path = rawpath.decode("utf-8", "surrogateescape")
                if (
                    mode == b"120000"
                    or kind != b"blob"
                    or path not in paths
                    or not eligible(path)
                ):
                    continue
                source = read(blob)
                if source is None:
                    continue
                found, counts = lexical_edges(path, source, graph["nodes"])
                edges.extend(found)
                for key, value in counts.items():
                    audit[key] += value
        result = {
            "version": RELATION_VERSION,
            "revision": revision,
            "edges": edges,
            "audit": audit,
        }
        write(destination, result)
    ids = {n["id"] for n in graph["nodes"]}
    if any(
        edge["source"] not in ids or edge["target"] not in ids
        for edge in result["edges"]
    ):
        raise ValueError("Relation evidence contains an invalid entity reference")
    return {**graph, "edges": graph["edges"] + result["edges"]}, result["audit"]
