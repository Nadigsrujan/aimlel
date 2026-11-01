"""Exercise a real public URL job through frozen learned inference on localhost."""

import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def api(path, payload=None):
    request = Request(
        "http://127.0.0.1:8080" + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://github.com/pallets/markupsafe")
    args = parser.parse_args()
    repo = urlsplit(args.url).path.strip("/").removesuffix(".git")
    job = None
    try:
        submitted = api("/api/v1/jobs", {"url": args.url})
        repo = submitted["repo"]
        deadline = time.monotonic() + 600
        phase = None
        while time.monotonic() < deadline:
            job = api("/api/v1/jobs/" + submitted["job"])
            current = job.get("progress", {}).get("stage", job["status"])
            if current != phase:
                print(repo, current, flush=True)
                phase = current
            if job["status"] == "processed":
                assert job.get("semantic_ready"), job
                break
            if job["status"] not in ("running", "cancelling"):
                raise RuntimeError(json.dumps(job))
            time.sleep(2)
        else:
            raise TimeoutError("Public workflow smoke exceeded ten minutes")
    except HTTPError as error:
        if error.code != 409:
            raise
        print(
            "Repository already present; verifying existing learned inference",
            flush=True,
        )
    files = api("/api/files?" + urlencode({"repo": repo}))
    seed = next(
        (
            path
            for path in files
            if path.startswith("src/") and path.endswith("/__init__.py")
        ),
        files[0],
    )
    response = api(
        "/api/v1/analysis",
        {"repo": repo, "seed": seed, "ranker": "heterogeneous-v1", "top_k": 5},
    )
    assert response["model_status"] == "frozen checkpoint"
    assert len(response["candidates"]) == min(5, len(files) - 1)
    assert all(
        row["path"] != seed and "semantic" in row["channels"]
        for row in response["candidates"]
    )
    report = {"job": job, "analysis": response}
    (ROOT / "artifacts/reports/public-neural-smoke.json").write_text(
        json.dumps(report, indent=2)
    )
    print(
        "Public URL → persisted job → semantic index → frozen neural ranking passed:",
        repo,
        flush=True,
    )


if __name__ == "__main__":
    main()
