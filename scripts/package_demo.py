"""Package the matching source, model, built UI and measured reports for handoff."""

import hashlib
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/src"))
from neural_cartographer.learning.research import verify_freeze


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen = verify_freeze()
    report = json.loads((ROOT / "artifacts/reports/final-heldout.json").read_text())
    if report.get("freeze") != frozen:
        raise ValueError("The result does not match the installed frozen model")
    expected = [
        "heterogeneous-development.json",
        "final-heldout.json",
        "final-study-audit.json",
        "checkpoint-reproduction.json",
        "candidate-coverage.json",
        "development-mapping-audit.json",
        "external-swebench.json",
        "external-overlap-audit.json",
        "external-dataset-pin.json",
        "external-bugsinpy.json",
        "external-bugsinpy-audit.json",
        "leave-one-out-heldout.json",
        "leave-one-out-validation.json",
        "frozen-comparators-heldout.json",
        "observatory-checks.json",
    ]
    required = [ROOT / "artifacts/reports" / name for name in expected]
    required += [
        ROOT / "frontend/dist/index.html",
        ROOT / "frontend/dist/assets/study-results.json",
        ROOT / "docs/model-card.md",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(
                "Missing handoff artifact: " + str(path.relative_to(ROOT))
            )
    extra = ROOT / "artifacts/models/leave-one-out"
    extra_freeze = json.loads((extra / "freeze.json").read_text())
    for name, checksum in extra_freeze["hashes"].items():
        if digest(extra / name) != checksum:
            raise ValueError("Additional ablation artifact changed")
    files = set(required)
    for folder, patterns in [
        ("backend/src", ["*.py"]),
        ("backend/tests", ["*.py"]),
        ("scripts", ["*.py"]),
        ("frontend/src", ["*.jsx", "*.js", "*.css"]),
        ("frontend/dist", ["*"]),
        ("frontend/public", ["*.json"]),
        ("configs", ["*.json"]),
        ("docs", ["*.md"]),
        ("data/manifests", ["*.json"]),
        (".github", ["*.yml"]),
    ]:
        for pattern in patterns:
            files.update(
                path
                for path in (ROOT / folder).rglob(pattern)
                if path.is_file() and not path.is_symlink()
            )
    for path in (ROOT / "artifacts/models/heterogeneous-development").iterdir():
        if path.is_file() and path.suffix in (".json", ".pt"):
            files.add(path)
    files.update(
        path
        for path in extra.iterdir()
        if path.is_file() and path.suffix in (".json", ".pt")
    )
    files.update(ROOT.glob("requirements*.txt"))
    for name in (
        "README.md",
        ".env.example",
        "NEURAL_CARTOGRAPHER_MASTER_CODING_AGENT_PROMPT.md",
        "NEURAL_CARTOGRAPHER_VISUALIZATION_PROMPTS.md",
        "NEURAL_CARTOGRAPHER_COMPLETE_AGENT_BRIEF.md",
        "artifacts/reports/interface-observatory.jpg",
        "pyproject.toml",
        "Dockerfile",
        "compose.yaml",
        ".dockerignore",
        "PROJECT_REVIEW_AND_IMPLEMENTATION_PLAN.md",
        "PENDING_WORK.md",
        "tasks/todo.md",
        "frontend/package.json",
        "frontend/package-lock.json",
        "frontend/index.html",
        "frontend/vite.config.js",
        "artifacts/reports/interface-neural.jpg",
        "artifacts/reports/public-neural-smoke.json",
    ):
        path = ROOT / name
        if path.is_file():
            files.add(path)
    model_sha = frozen["hashes"]["artifacts/models/heterogeneous-development/model.pt"]
    output = ROOT / "artifacts/releases"
    output.mkdir(parents=True, exist_ok=True)
    destination = output / ("neural-cartographer-" + model_sha[:12] + ".zip")
    temporary = destination.with_suffix(".tmp")
    hashes = {path.relative_to(ROOT).as_posix(): digest(path) for path in sorted(files)}
    manifest = {
        "model_sha256": model_sha,
        "primary_result_sha256": digest(ROOT / "artifacts/reports/final-heldout.json"),
        "files": hashes,
        "omitted": [
            "Git clones and prepared datasets",
            "CodeBERT encoder weights",
            "Python/Node runtimes and installed dependencies",
        ],
        "setup": "Follow README.md; restore pinned data/encoder artifacts before analysis. Source/model/report versions in this bundle match.",
    }
    with ZipFile(temporary, "w", ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(files):
            path.resolve().relative_to(ROOT.resolve())
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.writestr("BUNDLE_MANIFEST.json", json.dumps(manifest, indent=2))
    temporary.replace(destination)
    with ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError("Release archive integrity check failed")
    print(
        json.dumps(
            {
                "bundle": str(destination),
                "files": len(files),
                "bytes": destination.stat().st_size,
                "sha256": digest(destination),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
