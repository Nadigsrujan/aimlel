"""Serve the built interface and API together on localhost."""

import argparse
import subprocess
import sys
from neural_cartographer.ingest.pipeline import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    if not (ROOT / "frontend/dist/index.html").is_file():
        parser.error("Build the frontend first: cd frontend && npm ci && npm run build")
    # subprocess quotes Windows paths containing spaces correctly; os.execv does
    # not preserve that quoting when the interpreter itself is in the workspace.
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api:app",
                "--app-dir",
                str(ROOT / "scripts"),
                "--host",
                "127.0.0.1",
                "--port",
                str(args.port),
            ]
        )
    )


if __name__ == "__main__":
    main()
