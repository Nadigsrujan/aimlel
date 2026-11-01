"""Friendly local launcher; never installs packages, trains models or stops a server."""

import argparse
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import json
import webbrowser

ROOT = Path(__file__).resolve().parents[1]


def ready(url):
    try:
        with urlopen(url + "/api/v1/health", timeout=2) as response:
            value = json.load(response)
        return (
            value.get("status") == "ok"
            and value.get("schema_version") == 1
            and value.get("frontend_ready") is True
        )
    except (OSError, URLError, ValueError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--open", action="store_true", help="Open the website in your default browser"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild the frontend using already-installed npm packages",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be 1 to 65535")
    if not ((3, 10) <= sys.version_info[:2] < (3, 13)):
        parser.error(
            "Use the workspace .venv Python (supported versions 3.10 to 3.12)."
        )
    url = f"http://127.0.0.1:{args.port}"
    if ready(url):
        print("Neural Cartographer is already running: " + url, flush=True)
        if args.rebuild:
            print("Stop the existing server before using --rebuild.", flush=True)
        if args.open:
            webbrowser.open(url)
        return
    if args.rebuild:
        import shutil

        npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
        if not npm:
            parser.error("Node.js/npm is missing. See docs/RUN_SERVER.md.")
        subprocess.run(
            [npm, "run", "build", "--prefix", "frontend"], cwd=ROOT, check=True
        )
    if not (ROOT / "frontend/dist/index.html").is_file():
        parser.error(
            "Frontend build missing. Run npm ci --prefix frontend, then npm run build --prefix frontend."
        )
    print(
        "Neural Cartographer: "
        + url
        + "\nKeep this terminal open. Press Ctrl+C to stop.\nNo training or repository re-ingestion is required.",
        flush=True,
    )
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts/start.py"), "--port", str(args.port)],
        cwd=ROOT,
    )
    try:
        if args.open:
            for _ in range(30):
                if process.poll() is not None:
                    break
                if ready(url):
                    webbrowser.open(url)
                    break
                time.sleep(0.5)
        raise SystemExit(process.wait())
    except KeyboardInterrupt:
        # Ctrl+C reaches the foreground server in the same console process group.
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
