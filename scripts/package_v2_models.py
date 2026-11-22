"""Package the frozen v2 models into a tracked, checksummed release.

artifacts/models/ is gitignored, so this zip is the durable copy. The zip is
deterministic (sorted entries, fixed timestamps), and the manifest lists the
SHA-256 of every packaged file plus the zip itself.

    .venv\\Scripts\\python.exe scripts\\package_v2_models.py           # build
    .venv\\Scripts\\python.exe scripts\\package_v2_models.py --check   # verify
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "models" / "v2"
RELEASE = ROOT / "artifacts" / "releases"
ZIP = RELEASE / "v2-models.zip"
MANIFEST = RELEASE / "v2-models.manifest.json"
EPOCH = (2026, 11, 22, 0, 0, 0)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build():
    files = sorted(p for p in SOURCE.rglob("*") if p.is_file())
    if not files:
        sys.exit(f"no models under {SOURCE}")
    RELEASE.mkdir(parents=True, exist_ok=True)
    entries = {}
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            name = path.relative_to(SOURCE).as_posix()
            data = path.read_bytes()
            entries[name] = {"sha256": sha256(data), "bytes": len(data)}
            info = zipfile.ZipInfo(name, EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)
    manifest = {
        "source": "artifacts/models/v2",
        "freeze_sha256": entries["freeze.json"]["sha256"],
        "zip_sha256": sha256(ZIP.read_bytes()),
        "files": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{ZIP.name}: {len(entries)} files, {ZIP.stat().st_size} bytes, sha256 {manifest['zip_sha256']}")


def check():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    problems = []
    if sha256(ZIP.read_bytes()) != manifest["zip_sha256"]:
        problems.append("zip checksum differs")
    with zipfile.ZipFile(ZIP) as archive:
        names = set(archive.namelist())
        for name, meta in manifest["files"].items():
            if name not in names:
                problems.append(f"missing in zip: {name}")
            elif sha256(archive.read(name)) != meta["sha256"]:
                problems.append(f"changed in zip: {name}")
            live = SOURCE / name
            if live.exists() and sha256(live.read_bytes()) != meta["sha256"]:
                problems.append(f"live model differs: {name}")
    for line in problems:
        print("FAIL", line)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    sys.exit(check() if parser.parse_args().check else build())
