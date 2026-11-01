"""Compatibility entrypoint for neural_cartographer.api.app."""

import importlib
import os
from pathlib import Path
import runpy
import sys

# Load only the documented provider settings; never execute/interpolate .env text.
environment_file = Path(__file__).resolve().parents[1] / ".env"
if environment_file.is_file():
    for line in environment_file.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if separator and key in {
            "GROQ_API_KEY",
            "GROQ_MODEL",
            "GEMINI_API_KEY",
            "GEMINI_MODEL",
        }:
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                os.environ.setdefault(key, value)

sys.setrecursionlimit(10000)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
if __name__ == "__main__":
    runpy.run_module("neural_cartographer.api.app", run_name="__main__")
else:
    module = importlib.import_module("neural_cartographer.api.app")
    from observatory import install

    install(module)
    sys.modules[__name__] = module
