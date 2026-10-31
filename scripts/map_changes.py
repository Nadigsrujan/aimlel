"""Compatibility entrypoint for neural_cartographer.labels.diffs."""
import importlib
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend/src'))
if __name__ == '__main__':
    runpy.run_module('neural_cartographer.labels.diffs', run_name='__main__')
else:
    sys.modules[__name__] = importlib.import_module('neural_cartographer.labels.diffs')
