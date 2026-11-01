"""Export revision-aware resolved graph records for optional Neo4j import."""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.ingest.pipeline import ROOT, write
from neural_cartographer.contracts.schema import entity_records
from neural_cartographer.graph.relations import enrich_relations
from neural_cartographer.graph.structure import resolve_imports


def export(repo, revision):
    source = ROOT / "data/processed" / repo.replace("/", "__") / revision / "graph.json"
    graph, audit = enrich_relations(repo, revision, json.loads(source.read_text()))
    nodes = entity_records(graph, repo, revision)
    ids = {node["legacy_id"]: node["id"] for node in nodes}
    files = {node["path"]: node["id"] for node in nodes if node["kind"] == "file"}
    resolved, unresolved = resolve_imports(graph)
    edges = [
        {
            "source": ids[edge["source"]],
            "target": ids[edge["target"]],
            "relation": edge["relation"],
            "line": edge.get("line", ""),
            "resolution": edge.get("resolution", "extracted"),
        }
        for edge in graph["edges"]
        if edge["source"] in ids and edge["target"] in ids
    ]
    edges += [
        {
            "source": files[edge["source"]],
            "target": files[edge["target"]],
            "relation": "IMPORTS",
            "line": edge.get("line", ""),
            "resolution": "resolved-module",
        }
        for edge in resolved
    ]
    destination = ROOT / "artifacts/exports" / repo.replace("/", "__") / revision
    destination.mkdir(parents=True, exist_ok=True)
    for name, rows, fields in [
        (
            "nodes.csv",
            nodes,
            [
                "id",
                "repo",
                "revision",
                "kind",
                "path",
                "qualified_name",
                "start",
                "end",
            ],
        ),
        ("edges.csv", edges, ["source", "target", "relation", "line", "resolution"]),
    ]:
        with (destination / name).open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    # Known relationship literals only; no repository text enters Cypher code.
    cypher = """// Set $nodes_uri and $edges_uri to CSV files in your Neo4j import directory.
CREATE CONSTRAINT code_entity_id IF NOT EXISTS FOR (n:CodeEntity) REQUIRE n.id IS UNIQUE;
LOAD CSV WITH HEADERS FROM $nodes_uri AS row
MERGE (n:CodeEntity {id: row.id})
SET n.repo=row.repo, n.revision=row.revision, n.kind=row.kind,
    n.path=row.path, n.qualified_name=row.qualified_name,
    n.start=toInteger(row.start), n.end=toInteger(row.end);
LOAD CSV WITH HEADERS FROM $edges_uri AS row
MATCH (a:CodeEntity {id:row.source}), (b:CodeEntity {id:row.target})
"""
    relations = sorted({edge["relation"] for edge in edges})
    if not set(relations).issubset({"CONTAINS", "IMPORTS", "CALLS", "INHERITS"}):
        raise ValueError("Unsupported graph relation")
    cypher += (
        "\n".join(
            "FOREACH (_ IN CASE row.relation WHEN '"
            + relation
            + "' THEN [1] ELSE [] END | MERGE (a)-[r:"
            + relation
            + "]->(b) SET r.line=toInteger(row.line), r.resolution=row.resolution)"
            for relation in relations
        )
        + ";\n"
    )
    (destination / "import.cypher").write_text(cypher, encoding="utf-8")
    write(
        destination / "audit.json",
        {
            "repo": repo,
            "revision": revision,
            "nodes": len(nodes),
            "edges": len(edges),
            "unresolved_imports": len(unresolved),
            "lexical_resolution": audit,
            "limitations": [
                "Optional export; the local API reads JSON graphs",
                "Unresolved dynamic imports/calls are not invented",
                "Past co-change is query-cutoff-specific and is not exported as a static dependency",
            ],
        },
    )
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    from neural_cartographer.api.legacy import load_manifests

    manifest = load_manifests().get(args.repo)
    if manifest is None:
        parser.error("Repository is unavailable or held out")
    print(export(args.repo, manifest["revision"]))


if __name__ == "__main__":
    main()
