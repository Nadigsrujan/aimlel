"""Report every already-frozen comparator on the primary audited test pool.

This supplemental report is produced after the primary report; it does not
select, fit, tune or alter the primary baseline/model/success gate.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend/src'))
from neural_cartographer.learning.research import verify_freeze
from neural_cartographer.ingest.pipeline import write

def main():
    import torch
    from xgboost import XGBClassifier
    from neural_cartographer.learning.train import measure,macro
    from neural_cartographer.features.history import RANKERS,rerank
    from neural_cartographer.evaluation.metrics import metrics,macro_bootstrap
    destination=ROOT/'artifacts/reports/frozen-comparators-heldout.json'
    if destination.exists():raise ValueError('Supplemental report already exists; refusing overwrite')
    frozen=verify_freeze()
    audit=json.loads((ROOT/'artifacts/reports/final-study-audit.json').read_text())
    test=[]
    for query in audit['queries']:
        path=ROOT/'data/interim/learning-examples'/query['repo'].replace('/','__')/(query['example_cache_key']+'.pt')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=query['example_sha256']:raise ValueError('Primary test tensor changed')
        test.append(torch.load(path,map_location='cpu',weights_only=True))
    torch.set_num_threads(2)
    baseline=XGBClassifier()
    baseline.load_model(ROOT/'artifacts/models/heterogeneous-development/xgboost.json')
    comparison={'xgboost':measure(torch.nn.Identity(),test,baseline)}
    for name in [*RANKERS,'semantic-v1']:
        rows=[]
        for example in test:
            start=time.perf_counter()
            ranked=(sorted(example['rows'],key=lambda r:(-r['features']['semantic_cosine'],r['path'])) if name=='semantic-v1' else rerank(example['rows'],name,example['seed']))
            values=metrics([r['path'] for r in ranked],example['positives'])
            rows.append({'repo':example['repo'],'commit':example['commit'],'inference_seconds':time.perf_counter()-start,**values})
        comparison[name]=rows
    keys=('recall_at_5','recall_at_10','precision_at_5','map_at_10','ndcg_at_10','mrr','candidate_ceiling')
    report={'status':'supplemental evaluation of models/comparators frozen before primary test results; reporting performed afterward; no tuning or reselection','primary_model_sha256':audit['model_sha256'],'query_count':len(test),'comparison':comparison,'macro':{name:{key:macro(rows,key) for key in keys} for name,rows in comparison.items()},'confidence_intervals':{name:{key:macro_bootstrap(rows,key) for key in ('recall_at_5','ndcg_at_10')} for name,rows in comparison.items()}}
    primary=json.loads((ROOT/'artifacts/reports/final-heldout.json').read_text())
    for key in keys:
        if abs(report['macro']['cochange-v1'][key]-primary['macro']['cochange-v1'][key])>1e-12:raise ValueError('Comparator pool differs from primary report')
    verify_freeze();write(destination,report)
    print(json.dumps(report['macro'],indent=2),flush=True)
if __name__=='__main__':main()
