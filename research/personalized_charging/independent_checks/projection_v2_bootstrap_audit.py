#!/usr/bin/env python3
"""Post-completion bootstrap cross-check; does not import study source.

Example: python projection_v2_bootstrap_audit.py RUN_DIR --manifest MANIFEST
Requires the NumPy version recorded in the completion receipt. No data file is
opened until a completion receipt has been parsed and marked complete.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

ANALYSIS_SEED = 71960434
STUDY_SEED = 71960433
GROUPS = ('prior_positive','positive_mixed','harmful','tight','B','A_prime')
CHECKPOINTS = (16,64,256,1024,4096,12288,100000,1000000,3000000)
SCHEDULES = ('natural','forced')
GATES = ('two','three','projection_three')
PAIRS = 60
SAMPLES = 2000
ABS_TOL = 1e-10
REL_TOL = 1e-12


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1 << 20),b''):
            sha.update(block)
    return sha.hexdigest()


def comparisons():
    result=[]
    for schedule in SCHEDULES:
        result.extend((schedule+'_'+a,schedule+'_'+b) for a,b in
                      (('two','three'),('two','projection_three'),('three','projection_three')))
        result.extend((schedule+'_'+gate,baseline) for gate in GATES for baseline in ('prior','default'))
    result.extend(('natural_'+gate,'forced_'+gate) for gate in GATES)
    result.append(('prior','default'))
    return result


def percentile(values, fraction):
    """Linear percentile from a sorted vector, independently of np.quantile."""
    ordered=np.sort(np.asarray(values,dtype=float))
    position=(len(ordered)-1)*fraction
    lo=int(math.floor(position)); hi=int(math.ceil(position)); weight=position-lo
    return float(ordered[lo]+weight*(ordered[hi]-ordered[lo]))


def paired_metrics(rows, a, b, indices):
    """Recompute differences, point means and three unadjusted paired CIs."""
    differences=[]; certificates=[]; stop=[]
    for row in rows:
        left=row['methods'][a]; right=row['methods'][b]
        if type(left['certified']) is not bool or type(right['certified']) is not bool:
            raise ValueError('invalid certification flag')
        diffs=(float(left['lifecycle_gain'])-float(right['lifecycle_gain']),
               int(left['certified'])-int(right['certified']),
               float(left['stop_lifecycle_gain'])-float(right['stop_lifecycle_gain']))
        if not all(math.isfinite(x) for x in diffs): raise ValueError('nonfinite paired values')
        differences.append(diffs[0]); certificates.append(diffs[1]); stop.append(diffs[2])
    result={}
    for values,point_key,interval_key in (
        (differences,'mean','bootstrap_95'),
        (certificates,'certified_difference','certified_bootstrap_95'),
        (stop,'stop_gain_difference','stop_gain_bootstrap_95')):
        values=np.asarray(values,dtype=float)
        sample_means=values[indices].mean(axis=1)
        result[point_key]=math.fsum(values)/len(values)
        result[interval_key]=[percentile(sample_means,.025),percentile(sample_means,.975)]
    return result


def close(actual, expected):
    return math.isfinite(actual) and math.isclose(actual,expected,rel_tol=REL_TOL,abs_tol=ABS_TOL)


def audit(directory, manifest=None):
    directory=Path(directory)
    # This file is the commit marker. Do not inspect other run files first.
    receipt_path=directory/'completed.json'
    if not receipt_path.is_file(): raise ValueError('no completion receipt; refusing to read run files')
    receipt=json.loads(receipt_path.read_text())
    if receipt.get('status')!='complete': raise ValueError('incomplete receipt; refusing to read run files')
    if receipt.get('numpy')!=np.__version__:
        raise ValueError('NumPy version differs from the receipt; cannot reproduce PCG64/quantiles')
    if manifest is not None:
        manifest=Path(manifest)
        if digest(manifest)!=receipt.get('manifest_sha256'): raise ValueError('manifest digest mismatch')
        if json.loads(manifest.read_text()).get('sha256')!=receipt.get('source_sha256'):
            raise ValueError('manifest and receipt source digests differ')
    expected_files={'started.json','summary.json','checkpoints.jsonl'}
    outputs=receipt.get('output_sha256')
    if not isinstance(outputs,dict) or set(outputs)!=expected_files:
        raise ValueError('unexpected receipt output set')
    for name in expected_files:
        if digest(directory/name)!=outputs[name]: raise ValueError('output digest mismatch: '+name)
    started=json.loads((directory/'started.json').read_text())
    if started.get('seed')!=STUDY_SEED or started.get('manifest_sha256')!=receipt.get('manifest_sha256'):
        raise ValueError('wrong study seed or inconsistent manifest')
    summary=json.loads((directory/'summary.json').read_text())
    if set(summary)!=set(GROUPS): raise ValueError('unexpected groups')
    grouped={(g,h):{} for g in GROUPS for h in CHECKPOINTS}
    chain='00'*32; row_count=0
    with (directory/'checkpoints.jsonl').open(encoding='utf-8') as handle:
        for line in handle:
            record=json.loads(line)
            if set(record)!={'previous_sha256','sha256','row'} or record['previous_sha256']!=chain:
                raise ValueError('invalid checkpoint hash chain')
            row=record['row']
            body=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
            chain=hashlib.sha256(bytes.fromhex(chain)+body).hexdigest()
            if chain!=record['sha256']: raise ValueError('checkpoint hash mismatch')
            group,h,pair=row['group'],row['checkpoint'],row['pair']
            if (group,h) not in grouped or type(pair) is not int or not 0<=pair<PAIRS:
                raise ValueError('unexpected checkpoint row identity')
            if row['group_index']!=GROUPS.index(group) or pair in grouped[group,h]:
                raise ValueError('duplicate pair or group index mismatch')
            grouped[group,h][pair]=row; row_count+=1
    expected_rows=len(GROUPS)*len(CHECKPOINTS)*PAIRS
    if row_count!=expected_rows or receipt.get('row_count')!=row_count or chain!=receipt.get('chain_head'):
        raise ValueError('incomplete checkpoint rows or mismatched chain head')
    if any(set(pairs)!=set(range(PAIRS)) for pairs in grouped.values()):
        raise ValueError('missing pair at checkpoint')
    failures=[]; comparison_count=0; interval_count=0
    expected_comparisons=comparisons()
    for gi,group in enumerate(GROUPS):
        if set(summary[group])!={str(h) for h in CHECKPOINTS}:
            raise ValueError('checkpoint summary set mismatch')
        for ci,h in enumerate(CHECKPOINTS):
            rows=[grouped[group,h][pair] for pair in range(PAIRS)]
            saved=summary[group][str(h)]['paired']
            keys={a+'_minus_'+b for a,b in expected_comparisons}
            if set(saved)!=keys: raise ValueError('comparison summary set mismatch')
            # Same prespecified analysis stream, generated only after completion
            # and output integrity checks; does not touch scientific streams.
            generator=np.random.Generator(np.random.PCG64(np.random.SeedSequence([ANALYSIS_SEED,gi,ci])))
            indices=generator.integers(0,PAIRS,size=(SAMPLES,PAIRS))
            for a,b in expected_comparisons:
                key=a+'_minus_'+b; actual=paired_metrics(rows,a,b,indices); reported=saved[key]
                if set(reported)!=set(actual): raise ValueError('unexpected paired summary schema')
                for metric,value in actual.items():
                    if isinstance(value,list):
                        other=reported[metric]
                        if not isinstance(other,list) or len(other)!=2 or not all(close(float(x),y) for x,y in zip(other,value)):
                            failures.append({'group':group,'checkpoint':h,'comparison':key,'metric':metric})
                        interval_count+=1
                    elif not close(float(reported[metric]),value):
                        failures.append({'group':group,'checkpoint':h,'comparison':key,'metric':metric})
                comparison_count+=1
    return {'status':'PASS' if not failures else 'FAIL','rows':row_count,'groups':len(GROUPS),
            'checkpoints_per_group':len(CHECKPOINTS),'bootstrap_matrices':len(GROUPS)*len(CHECKPOINTS),
            'resamples_per_matrix':SAMPLES,'pairs_per_resample':PAIRS,'comparisons':comparison_count,
            'intervals':interval_count,'source_manifest_checked':manifest is not None,
            'completion_receipt_sha256':digest(receipt_path),
            'manifest_sha256':receipt.get('manifest_sha256'),
            'checkpoint_sha256':outputs['checkpoints.jsonl'],'summary_sha256':outputs['summary.json'],
            'checker_sha256':digest(Path(__file__)),'numpy_version':np.__version__,
            'absolute_tolerance':ABS_TOL,'relative_tolerance':REL_TOL,'discrepancies':failures,
            'limitations':'Same NumPy PCG64 streams and saved records; checks computation and integrity, not independence of arithmetic, model validity, source authenticity or causal claims.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir'); parser.add_argument('--manifest')
    args=parser.parse_args()
    try:
        report=audit(args.run_dir,args.manifest)
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as error:
        print(json.dumps({'status':'ERROR','error':str(error)}),file=sys.stderr)
        return 2
    print(json.dumps(report,indent=2,sort_keys=True,allow_nan=False))
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__': sys.exit(main())
