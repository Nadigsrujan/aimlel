"""Finish publication automatically after the already-running frozen evaluation."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "artifacts/reports/finalization-progress.json"


def record(stage, status):
    value = {"stage": stage, "status": status, "observed_at": time.time()}
    temporary = STATUS.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(STATUS)


def run(stage, args):
    record(stage, "running")
    print(stage, flush=True)
    subprocess.run(args, cwd=ROOT, check=True)
    record(stage, "complete")


def main():
    deadline = time.monotonic() + 7200
    report = ROOT / "artifacts/reports/final-heldout.json"
    record("waiting-for-frozen-heldout-report", "running")
    while not report.is_file():
        progress = json.loads(
            (ROOT / "artifacts/reports/study-progress.json").read_text()
        )
        if progress.get("status") == "failed":
            raise RuntimeError("Primary study failed; inspect its recorded stage log")
        if time.monotonic() > deadline:
            raise TimeoutError("Primary result not available within two hours")
        time.sleep(10)
    run("publish-query-audit", [sys.executable, "scripts/publish_study_report.py"])
    extra = ROOT / "artifacts/reports/leave-one-out-heldout.json"
    if extra.is_file():
        value = json.loads(extra.read_text())
        freeze = json.loads(
            (ROOT / "artifacts/models/leave-one-out/freeze.json").read_text()
        )
        if value.get("freeze") != freeze:
            raise ValueError("Additional evaluation belongs to different frozen models")
    else:
        run(
            "additional-frozen-ablations",
            [sys.executable, "scripts/remaining_ablations.py", "evaluate"],
        )
    if not (ROOT / "artifacts/reports/frozen-comparators-heldout.json").is_file():
        run(
            "all-frozen-comparators",
            [sys.executable, "scripts/evaluate_frozen_comparators.py"],
        )
    run("publish-complete-report", [sys.executable, "scripts/publish_study_report.py"])
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("npm is required to publish the frontend report")
    run("build-help-pages", [sys.executable, "scripts/build_guides.py"])
    run("build-final-interface", [npm, "run", "build", "--prefix", "frontend"])
    run("package-matching-deliverables", [sys.executable, "scripts/package_demo.py"])
    record("publication-and-package", "complete")
    print(
        "Frozen study, ablations, model card, UI report and release bundle published.",
        flush=True,
    )


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        record("publication", "failed")
        raise
