"""Focused checks for additive observatory contracts and unsafe archive rejection."""

import os
from unittest.mock import patch
import io, json, sys, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import api
from fastapi.testclient import TestClient
from archive_api import inspect_archive


def zipped(name, content):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        info = zipfile.ZipInfo("placeholder")
        info.filename = name
        info.orig_filename = name
        z.writestr(info, content)
    return output.getvalue()


graph = inspect_archive(zipped("sample.py", "def hello():\n    return 1\n"))
assert len(graph["nodes"]) == 2 and len(graph["edges"]) == 1
for name in ("../escape.py", "/absolute.py", "C:/drive.py", "a\\evil.py"):
    try:
        inspect_archive(zipped(name, "print(1)"))
    except ValueError:
        pass
    else:
        raise AssertionError("Unsafe archive accepted: " + name)
with TestClient(api.app) as client:
    response = client.get("/api/v1/observatory/graph", params={"repo": "pallets/flask"})
    assert response.status_code == 200, response.text
    value = response.json()
    ids = {n["id"] for n in value["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in value["edges"])
    assert any(e["relation"] == "IMPORTS" for e in value["edges"])
    assert any(n["kind"] == "function" for n in value["nodes"])
    clone = api.ROOT / "data/raw/pallets__flask"
    parent = api.git(clone, "rev-parse", value["revision"] + "^").decode().strip()
    historical = client.get(
        "/api/v1/observatory/graph",
        params={"repo": "pallets/flask", "revision": parent},
    )
    assert historical.status_code == 200, historical.text
    old = historical.json()
    assert old["revision"] == parent and old["historical"] is True
    assert all(node["revision"] == parent for node in old["nodes"])
    assert (
        client.get(
            "/api/v1/observatory/graph",
            params={"repo": "pallets/flask", "revision": "0" * 40},
        ).status_code
        == 422
    )
    current_files = {n["path"]: n for n in value["nodes"] if n["kind"] == "file"}
    old_file = next(
        n for n in old["nodes"] if n["kind"] == "file" and n["path"] in current_files
    )
    assert old_file["logical_id"] == current_files[old_file["path"]]["logical_id"]
    assert old_file["id"] != current_files[old_file["path"]]["id"]

    assert (
        client.get(
            "/api/v1/observatory/history", params={"repo": "pallets/flask"}
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/observatory/graph", params={"repo": "../outside"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/observatory/archives", content=zipped("../bad.py", "pass")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/observatory/archives", content=zipped("safe.py", "pass")
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/observatory/readings",
            json={"run": "missing", "candidate": "nonexistent"},
        ).status_code
        == 404
    )
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("a.py", "import b\ndef first():\n    return b.second()\n")
        archive.writestr("b.py", "def second():\n    return 2\n")
    archive = client.post(
        "/api/v1/observatory/archives", content=archive_bytes.getvalue()
    ).json()
    baseline = client.post(
        "/api/v1/observatory/archives/" + archive["revision"] + "/forecast",
        json={"seed": "a.py"},
    ).json()
    assert baseline["model_status"] == "BASELINE / NOT TRAINED"
    assert baseline["candidates"][0]["path"] == "b.py" and baseline["candidates"][0][
        "evidence"
    ]["import_path"] == ["a.py", "b.py"]
    timeline = client.get(
        "/api/v1/observatory/history", params={"repo": "pallets/flask"}
    ).json()
    assert timeline and all(
        row["observed_file_pairs"]
        == row["changed_python_files"] * (row["changed_python_files"] - 1) // 2
        for row in timeline
    )
    assert client.get("/api/v1/observatory/research").json()["history"]
    graph = client.get(
        "/api/v1/observatory/graph", params={"repo": "pallets/itsdangerous"}
    ).json()
    seeds = [n["path"] for n in graph["nodes"] if n["kind"] == "file"][:2]
    response = client.post(
        "/api/v1/observatory/runs",
        json={
            "repo": "pallets/itsdangerous",
            "seeds": seeds,
            "name": "Verified multi-seed rehearsal",
        },
    )
    assert response.status_code == 200, response.text
    run = response.json()
    assert len(run["results"]) == 2 and all(
        r["ranker"] == "heterogeneous-v1" for r in run["results"]
    )
    assert not any(r["path"] in seeds for r in run["aggregate"])
    assert client.get("/api/v1/observatory/runs/" + run["id"]).json() == run
    candidate = run["results"][0]["candidates"][0]["path"]
    reading = client.post(
        "/api/v1/observatory/readings",
        json={"run": run["id"], "candidate": candidate, "style": "technical"},
    ).json()
    assert reading["mode"] == "deterministic" and reading["evidence_hash"]
    second = run["results"][1]
    second_candidate = second["candidates"][0]["path"]
    per_seed = client.post(
        "/api/v1/observatory/readings",
        json={
            "run": run["id"],
            "candidate": second_candidate,
            "seed": second["seed"],
            "style": "technical",
        },
    ).json()
    assert per_seed["seed"] == second["seed"]
    assert any(
        record["id"] == "model-score"
        and f"{second['candidates'][0]['score']:.6f}" in record["text"]
        for record in per_seed["statements"]
    )
    assert (
        client.post(
            "/api/v1/observatory/readings",
            json={
                "run": run["id"],
                "candidate": second_candidate,
                "seed": "not-a-seed.py",
            },
        ).status_code
        == 422
    )

    assert (
        client.post(
            "/api/v1/observatory/readings",
            json={"run": run["id"], "candidate": candidate, "provider": "groq"},
        ).status_code
        == 422
    )

    class RejectedCitation:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, *args):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps({"ids": ["invented-evidence"]})
                            }
                        }
                    ]
                }
            ).encode()

    with (
        patch.dict(
            os.environ,
            {
                "GROQ_API_KEY": "test-placeholder-no-network",
                "GROQ_MODEL": "mocked-rejection-only",
            },
        ),
        patch("observatory.urlopen", return_value=RejectedCitation()),
    ):
        rejected = client.post(
            "/api/v1/observatory/readings",
            json={
                "run": run["id"],
                "candidate": candidate,
                "provider": "groq",
                "allow_hosted": True,
            },
        ).json()
        assert rejected["mode"] == "deterministic" and "rejected" in rejected["status"]
    print(
        "Saved learned multi-seed forecast and local evidence verified:",
        run["id"],
        flush=True,
    )

from neural_cartographer.learning.research import verify_freeze

record = verify_freeze()
print(
    json.dumps(
        {
            "status": "passed",
            "frozen_hashes_verified": len(record["hashes"]),
            "graph_entities": len(ids),
            "resolved_edges": len(value["edges"]),
            "checks": [
                "archive parser",
                "ZIP traversal/absolute/drive/backslash rejection",
                "graph identity",
                "resolved imports",
                "Git history",
                "API errors",
                "freeze integrity",
            ],
        }
    )
)
