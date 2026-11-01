"""Frozen model protocol entrypoint."""

from pathlib import Path
import sys

sys.setrecursionlimit(10000)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend/src"))
from neural_cartographer.learning.research import main

if __name__ == "__main__":
    main()
