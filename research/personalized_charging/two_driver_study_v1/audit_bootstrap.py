"""Replay only frozen pair-level bootstrap analyses from saved records."""
import hashlib,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np

out=Path(sys.argv[1]);summary=json.loads((out/'summary.json').read_text());receipt=json.loads((out/'completed.json').read_text())
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
for name in ('summary.json','checkpoints.jsonl'):
    if sha(out/name)!=receipt['output_sha256'][name]:raise RuntimeError('saved output digest mismatch: '+name)
groups=('prior_positive','positive_mixed','harmful','tight','A','B','A_prime')
cps=(16,64,256,1024,4096,12288,100000,1000000,3000000)
rows={}
with (out/'checkpoints.jsonl').open() as f:
    for line in f:
        x=json.loads(line);rows.setdefault((x['group'],x['checkpoint']),[]).append(x)
fail=Counter();max_error=0.;intervals=means=endpoints=0
for gi,group in enumerate(groups):
    for ci,cp in enumerate(cps):
        subset=rows[(group,cp)]
        if [r['pair'] for r in subset]!=list(range(60)):raise RuntimeError('saved pair order mismatch')
        indices=np.random.Generator(np.random.PCG64(np.random.SeedSequence([55821762,gi,ci]))).integers(0,60,size=(2000,60))
        paired=summary[group][str(cp)]['paired']
        if len(paired)!=6:raise RuntimeError('paired comparison count mismatch')
        for name,saved in paired.items():
            first,second=name.split('_minus_')
            for field,mean_key,interval_key in (
                ('lifecycle_gain','mean','bootstrap_95'),
                ('certified','certified_difference','certified_bootstrap_95'),
                ('stop_lifecycle_gain','stop_gain_difference','stop_gain_bootstrap_95')):
                x=np.array([float(r['methods'][first][field])-float(r['methods'][second][field]) for r in subset])
                mu=float(x.mean()); bounds=[float(q) for q in np.quantile(x[indices].mean(axis=1),[.025,.975])]
                diff=abs(mu-saved[mean_key]);max_error=max(max_error,diff);means+=1
                if diff>1e-12:fail['mean']+=1
                for actual,stored in zip(bounds,saved[interval_key]):
                    diff=abs(actual-stored);max_error=max(max_error,diff);endpoints+=1
                    if diff>1e-12:fail['endpoint']+=1
                intervals+=1
                if len(saved[interval_key])!=2 or not all(math.isfinite(v) for v in saved[interval_key]):fail['interval_schema']+=1
print(json.dumps({'status':'pass' if not fail else 'fail','groups':len(groups),'checkpoints':len(cps),
    'pair_group_checkpoints':len(groups)*len(cps),'pairs_per_checkpoint':60,'replicates_per_checkpoint':2000,
    'seed':55821762,'comparison_types_per_checkpoint':6,'replayed_means':means,'replayed_intervals':intervals,
    'replayed_endpoints':endpoints,'max_absolute_difference':max_error,'failures':dict(fail),
    'checkpoint_sha256':sha(out/'checkpoints.jsonl'),'summary_sha256':sha(out/'summary.json'),
    'completed_sha256':sha(out/'completed.json'),'numpy_replay_version':np.__version__},indent=2))
if fail:raise SystemExit(1)
