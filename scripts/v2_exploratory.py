"""Exploratory comparisons on the saved v2 test rows (not pre-registered).

Reads artifacts/reports/v2-final.json and never re-runs a model. Answers the
question the primary gate leaves open: do the GNNs beat the history baselines?
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend/src'))
from neural_cartographer.evaluation.significance import compare, holm
from neural_cartographer.ingest.pipeline import ROOT, write

PAIRS = [
    ('full-gnn', 'rose-v1'), ('full-gnn', 'cochange-v1'),
    ('history-gnn', 'rose-v1'), ('history-gnn', 'cochange-v1'),
    ('xgboost', 'rose-v1'), ('rose-v1', 'cochange-v1'),
]

if __name__ == '__main__':
    final = json.loads((ROOT / 'artifacts/reports/v2-final.json').read_text())
    report = {'status': 'exploratory; not pre-registered; Holm-corrected within this family',
              'comparisons': {}}
    for metric in ('recall_at_5', 'ndcg_at_10'):
        results = {f'{a} vs {b}': compare(final['rows'][a], final['rows'][b], metric)
                   for a, b in PAIRS}
        adjusted = holm({name: row['sign_flip_p'] for name, row in results.items()})
        for name, row in results.items():
            row['holm_p'] = adjusted[name]
        report['comparisons'][metric] = results
    write(ROOT / 'artifacts/reports/v2-exploratory.json', report)
    for name, row in report['comparisons']['recall_at_5'].items():
        ci = row['ci_fixed_repositories']
        print(f"{name:28s} {row['difference']:+.3f} [{ci['lower']:+.3f}, {ci['upper']:+.3f}] "
              f"p={row['sign_flip_p']:.4f} holm={row['holm_p']:.4f} W/T/L {row['wins']}/{row['ties']}/{row['losses']}")
