"""Resume the declared study through development, freeze, and held-out evaluation.

Completed artifact-verified ingestion/indexes, examples and training epochs are
reused by the stage entrypoints. No stage changes model choices using test data.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.ingest.pipeline import write
from neural_cartographer.learning.research import verify_freeze


def stage(name, arguments):
    state = {"stage": name, "status": "running", "started_at_unix": time.time()}
    write(ROOT / "artifacts/reports/study-progress.json", state)
    print("\nSTUDY:", name, flush=True)
    logs = ROOT / "artifacts/reports/study-logs"
    logs.mkdir(parents=True, exist_ok=True)
    with (logs / (name + ".log")).open("a", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-u", *arguments],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        for line in process.stdout:
            print(line, end="", flush=True)
            log.write(line)
            log.flush()
        returncode = process.wait()
    state.update(
        status="complete" if returncode == 0 else "failed",
        finished_at_unix=time.time(),
        returncode=returncode,
    )
    write(ROOT / "artifacts/reports/study-progress.json", state)
    if returncode:
        raise SystemExit(returncode)


def main():
    if not (ROOT / "artifacts/models/heterogeneous-development/freeze.json").is_file():
        stage(
            "development-ingestion",
            [
                "scripts/ingest.py",
                "--clone",
                "--reuse",
                "--split",
                "train",
                "--split",
                "validation",
                "--workers",
                "2",
            ],
        )
        stage(
            "development-verification",
            ["scripts/verify_dataset.py", "--split", "train", "--split", "validation"],
        )
        stage("development-semantics", ["scripts/prepare_semantics.py", "--download"])
        stage("development-training", ["scripts/train_heterogeneous.py"])
        stage("model-freeze", ["scripts/research.py", "freeze"])
    verify_freeze()
    if not (ROOT / "artifacts/reports/final-heldout.json").is_file():
        stage(
            "heldout-ingestion",
            [
                "scripts/ingest.py",
                "--clone",
                "--reuse",
                "--split",
                "test",
                "--workers",
                "3",
            ],
        )
        stage("heldout-verification", ["scripts/verify_dataset.py", "--split", "test"])
        stage(
            "heldout-catalog-semantics",
            ["scripts/prepare_catalog_semantics.py", "--split", "test"],
        )
        # Evaluation builds only the declared test-parent semantic indexes.
        stage("heldout-evaluation", ["scripts/research.py", "evaluate"])
    record = verify_freeze()
    report = json.loads((ROOT / "artifacts/reports/final-heldout.json").read_text())
    if report.get("freeze") != record:
        raise ValueError(
            "Existing held-out results belong to a different freeze; restore their matching model bundle or use an isolated study workspace"
        )
    write(
        ROOT / "artifacts/reports/study-progress.json",
        {
            "status": "complete",
            "stage": "heldout-evaluation",
            "success_gate_met": report["success_gate_met"],
            "finished_at_unix": time.time(),
        },
    )
    print("Study recorded. Success gate:", report["success_gate_met"], flush=True)


if __name__ == "__main__":
    main()
