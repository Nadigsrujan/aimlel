"""Check frozen artifacts on any checkout without rewriting the freeze records.

Git may check text files out with CRLF line endings on Windows, which changes
their bytes but not their content. Each frozen file is classified as an exact
match, a line-ending-only difference, missing local data, or a real change.
Only a real change fails verification.
"""

import argparse
import hashlib
import json
import sys

from neural_cartographer.ingest.pipeline import ROOT

RECORDS = (
    "artifacts/models/heterogeneous-development/freeze.json",
    "artifacts/models/leave-one-out/freeze.json",
)
TEXT_SUFFIXES = {".py", ".json", ".jsonl", ".md", ".txt", ".csv", ".cypher"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def portable_digest(path):
    """Checksum that ignores CRLF/LF differences in text files only."""
    data = path.read_bytes()
    if path.suffix in TEXT_SUFFIXES:
        data = data.replace(b"\r\n", b"\n")
    return digest(data)


def matches(data, expected, name):
    """Return the kind of match between stored bytes and a frozen checksum."""
    if digest(data) == expected:
        return "exact"
    if any(name.endswith(suffix) for suffix in TEXT_SUFFIXES):
        unix = data.replace(b"\r\n", b"\n")
        if expected in (digest(unix), digest(unix.replace(b"\n", b"\r\n"))):
            return "line_endings"
    return "changed"


def classify(hashes, root=ROOT, base=None):
    """Bare file names are relative to the record's own directory (base)."""
    status = {"exact": [], "line_endings": [], "missing": [], "changed": []}
    for name, expected in sorted(hashes.items()):
        path = (base or root) / name if "/" not in name else root / name
        if not path.is_file():
            status["missing"].append(name)
        else:
            status[matches(path.read_bytes(), expected, name)].append(name)
    return status


def verify(root=ROOT, require_complete=False):
    report = {}
    for record_path in RECORDS:
        record = json.loads((root / record_path).read_text())
        report[record_path] = classify(
            record["hashes"], root, (root / record_path).parent
        )
    failed = any(
        status["changed"] or (require_complete and status["missing"])
        for status in report.values()
    )
    return report, failed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Also fail when frozen local data files are missing",
    )
    parser.add_argument("--list", action="store_true", help="Print every file name")
    args = parser.parse_args()
    report, failed = verify(require_complete=args.require_complete)
    for record_path, status in report.items():
        print(record_path)
        for kind, names in status.items():
            print(f"  {kind}: {len(names)}")
            if names and (args.list or kind == "changed"):
                for name in names:
                    print("    " + name)
    print("FAILED" if failed else "OK: no frozen content has changed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
