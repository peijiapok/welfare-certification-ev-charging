"""Read-only audit of completed two-driver artifacts; never draws randomness.

Gate replay reuses the original gate and Decimal interval implementation, so
it checks reproducibility and is not an independent numerical proof.
"""
import itertools, json, math, sys
from collections import Counter
from hashlib import sha256
from pathlib import Path
from personalized_charging.two_driver_exploratory_v1.gate import evaluate, prior_only
from personalized_charging.logit_polytope_exploratory_v1.projector import evaluate as projection_evaluate
from personalized_charging.p3d_diagnostic_v1.interval import I, sigmoid
from fractions import Fraction
from decimal import Decimal

out=Path(sys.argv[1]);manifest=Path(sys.argv[2]);root=Path(__file__).resolve().parents[2]
errors=Counter();tested=Counter();groups=Counter()
names=('prior_positive','positive_mixed','harmful','tight','B','A_prime')
offs=('p','r','third');schedules=('natural','forced');cps=(16,64,256,1024,4096,12288,100000,1000000,3000000)
cats=tuple(itertools.product(range(3),range(2),range(2)));seed=71960433
def check(ok,label):
    if not ok:errors[label]+=1
def near(a,b):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7)
def sig(x):return 1/(1+math.exp(-x))
def sha(path):
    h=sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
complete=json.loads((out/'completed.json').read_text());frozen=json.loads(manifest.read_text())['sha256']
check(len(frozen)==30,'manifest_source_count');check(complete['status']=='complete','completed_status');check(complete['manifest_sha256']==sha(manifest),'manifest_receipt')
check(complete['source_sha256']==frozen,'source_receipt')
for name,value in frozen.items():check(sha(root/name)==value,'source_'+name)
for name,value in complete['output_sha256'].items():check(sha(out/name)==value,'output_'+name)
actual={str(p.relative_to(out)) for p in out.iterdir() if p.is_file() and p.name!='completed.json'}
check(set(complete['output_sha256'])==actual,'output_inventory')

rows={};worlds={};chain='00'*32
with (out/'checkpoints.jsonl').open() as f:
    for line in f:
        record=json.loads(line);r=record['row']
        body=json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        calculated=sha256(bytes.fromhex(chain)+body).hexdigest()
        check(record['previous_sha256']==chain and record['sha256']==calculated,'row_chain')
        chain=calculated
        key=(r['group'],r['pair'],r['checkpoint'])
        check(key not in rows,'duplicate_row');rows[key]=r;groups[r['group']]+=1
        worlds.setdefault((r['group'],r['pair']),r['world_evaluator_only'])
        check(worlds[(r['group'],r['pair'])]==r['world_evaluator_only'],'world_changed')
check(complete['chain_head']==chain,'chain_head');check(complete['row_count']==len(rows)==3240,'row_count');check(len(worlds)==360,'pair_count');check(groups==Counter({n:540 for n in names}),'group_counts')

def count_position(start,end,pos):
    first=start+(pos-start)%6
    return 0 if first>=end else 1+(end-1-first)//6
def empty():return {k:0 for k in ('gain','unmet','delay','candidate_gain','candidate_unmet','candidate_delay','suppressed','urgent','expected_unmet','candidate_expected_unmet')}
def empty_counts():return {i:{j:[0,0] for j in offs} for i in ('A','B')}
def derive_ledger(w,role,pos,cells,variant):
    first,second=('A','B') if role=='AB' else ('B','A')
    phys=w['physics'];g0,g1,g2,W=map(float,(phys['g0'],phys['g1'],phys['g2'],phys['W']))
    t0=w['users'][first]['theta'];t1=w['users'][second]['theta'];result=empty();observed=empty_counts()
    for n,(f,rb,urgent) in zip(cells,cats):
        p=f==0;third=f!=2;r=bool(rb);c0=p;c1=(not p and r);occupied=c0 or c1
        if role=='AB':
            result['candidate_gain']+=n*((g0-g2-t0 if c0 else g1-g2-t1/2 if c1 else 0)-(W-g2)*occupied*urgent)
            result['candidate_unmet']+=n*occupied*urgent;result['candidate_delay']+=n*(t0*c0+t1/2*c1)
        if pos in (0,3):offered=[(first,'p',p)]
        elif pos in (2,5):offered=[(first,'third',third)]
        elif pos==1 or (pos==4 and variant=='forced'):offered=[(second,'r',r)]
        elif pos==4:
            offered=[(first,'p',p)]
            if not p:offered.append((second,'r',r))
            else:result['suppressed']+=n
        else:raise ValueError('unknown position')
        use0=any(d==first and yes for d,_,yes in offered);use1=any(d==second and yes for d,_,yes in offered)
        check(not(use0 and use1),'double_commitment');active=use0 or use1
        result['gain']+=n*((g0-g2-t0 if use0 else g1-g2-t1/2 if use1 else 0)-(W-g2)*active*urgent)
        result['unmet']+=n*active*urgent;result['delay']+=n*(t0*use0+t1/2*use1);result['urgent']+=n*urgent
        for driver,offer,yes in offered:observed[driver][offer][0]+=n*yes;observed[driver][offer][1]+=n
    d=float(phys['delta']);q0=w['users'][first];q1=w['users'][second]
    expected=q0['p'] if pos in (0,3) else q0['third'] if pos in (2,5) else q1['r'] if pos==1 or variant=='forced' else q0['p']+(1-q0['p'])*q1['r']
    result['expected_unmet']=sum(cells)*d*expected
    if role=='AB':result['candidate_expected_unmet']=sum(cells)*d*(q0['p']+(1-q0['p'])*q1['r'])
    result['observed']=observed
    return result

for (group,pair),w in worlds.items():
    gi=names.index(group);p=w['physics'];g0,g1,g2,d,W=map(float,(p['g0'],p['g1'],p['g2'],p['delta'],p['W']))
    a=g0-g2-d*(W-g2);b=g1-g2-d*(W-g2)
    for label in ('A','B'):
        user=w['users'][label];theta,tau,c=user['theta'],user['tau'],user['c']
        for k,q in [('p',sig((.1-theta)/tau+c)),('r',sig((.1-theta/2)/tau+c)),('third',sig((.2-theta)/tau+c+(.2 if group=='A_prime' else 0)))]:check(near(user[k],q),'truth_'+k)
    pa=w['users']['A']['p'];rb=w['users']['B']['r'];ta=w['users']['A']['theta'];tb=w['users']['B']['theta']
    benefit=pa*(a-ta)+(1-pa)*rb*(b-tb/2);unmet=d*(pa+(1-pa)*rb);eligible=benefit>0 and unmet<=float(p['epsilon'])
    check(near(w['benefit'],benefit) and near(w['unmet'],unmet) and w['truth_eligible']==eligible,'truth_target')
    prior=prior_only(**p);enabled=prior['decision']=='ALLOW'
    counts={v:empty_counts() for v in schedules};totals={v:empty() for v in schedules};latch={v:{m:None for m in ('two','three','projection_three')} for v in schedules};snap={v:{m:None for m in ('two','three','projection_three')} for v in schedules}
    previous=0
    for ci,H in enumerate(cps):
        row=rows[(group,pair,H)];check(row['group_index']==gi and row['block_start']==previous,'row_metadata')
        blocks=row['block_evaluator_only'];check(len(blocks)==6,'block_count')
        for pos,block in enumerate(blocks):
            role='AB' if pos%2==0 else 'BA';m=count_position(previous,H,pos)
            check(block['position']==pos and block['role']==role and block['count']==m and block['key']==[seed,1,gi,pair,ci,pos],'block_key_schedule')
            cells=block['cells_evaluator_only'];check(len(cells)==12 and all(type(x) is int and x>=0 for x in cells) and sum(cells)==m,'cell_domain')
            for variant in schedules:
                calc=derive_ledger(w,role,pos,cells,variant);stored=block['ledgers'][variant]
                for k,value in calc.items():
                    if k=='observed':check(stored[k]==value,'observed_labels')
                    else:check(near(stored[k],value),'block_'+k);totals[variant][k]+=value
                for who in ('A','B'):
                    for offer in offs:
                        for j in (0,1):counts[variant][who][offer][j]+=calc['observed'][who][offer][j]
            tested['calendar_blocks']+=1
        check(row['counts']==counts,'selected_counts')
        for v in schedules:
            for k,value in totals[v].items():check(near(row['totals'][v][k],value),'total_'+k)
            check(totals[v]['expected_unmet']<=H*d+1e-8,'collection_service_bound')
        dep=row['deployment_evaluator_only'];check(dep['key']==[seed,2,gi,pair,ci,0] and len(dep['cells'])==12 and all(type(x) is int and x>=0 for x in dep['cells']) and sum(dep['cells'])==32,'deployment_metadata')
        derived=derive_ledger(w,'AB',4,dep['cells'],'natural')
        for k,value in derived.items():
            if k=='observed':check(dep['ledger'][k]==value,'deployment_observed')
            else:check(near(dep['ledger'][k],value),'deployment_'+k)
        tested['deployment_blocks']+=1
        for variant in schedules:
            for method in ('two','three','projection_three'):
                name=variant+'_'+method;given=row['methods'][name]
                data={who:{offer:tuple(counts[variant][who][offer]) for offer in (('p','r') if method=='two' else offs)} for who in ('A','B')}
                replayed=(projection_evaluate(data,method='three',**p) if method=='projection_three' else evaluate(data,method=method,**p));check(given['raw']==replayed,'gate_replay_'+name)
                if method=='projection_three':
                    for projected in replayed.get('projections',{}).values():
                        if projected['status']!='PROJECTED':continue
                        witness=projected['witness'];h,lam,v=map(Fraction,(witness['h'],witness['lambda'],witness['v']))
                        check(Fraction(5,2)<=lam<=20 and 0<=v<=lam/4,'witness_prior')
                        check(Fraction(witness['theta'])==v/lam and Fraction(witness['tau'])==1/lam and Fraction(witness['common_shift'])==h-lam/10+v,'witness_mapping')
                        for contrast,offset in [('p',0),('r',v/2),('third',lam/10)]:
                            z=h+offset;z_interval=I(str(z.numerator))/I(str(z.denominator))
                            q=sigmoid(z_interval);lo,hi=map(Decimal,projected['bands'][contrast])
                            check(q.lo>=lo and q.hi<=hi,'witness_band')
                        tested['verified_witnesses']+=1
                if replayed['decision']=='ALLOW' and latch[variant][method] is None:latch[variant][method]=H;snap[variant][method]=dict(totals[variant])
                first=latch[variant][method];yes=first is not None;cur=totals[variant];ss=snap[variant][method]
                check(given['first_crossing']==first and given['certified']==yes,'latch_'+name)
                check(given['false_declaration']==(yes and not eligible),'false_'+name)
                stop_gain=cur['gain'] if ss is None else ss['gain']+cur['candidate_gain']-ss['candidate_gain']
                stop_unmet=cur['unmet'] if ss is None else ss['unmet']+cur['candidate_unmet']-ss['candidate_unmet']
                stop_expected=cur['expected_unmet'] if ss is None else ss['expected_unmet']+cur['candidate_expected_unmet']-ss['candidate_expected_unmet']
                stop_delay=cur['delay'] if ss is None else ss['delay']+cur['candidate_delay']-ss['candidate_delay']
                expected={'collection_gain':cur['gain'],'collection_unmet':cur['unmet'],'collection_expected_unmet':cur['expected_unmet'],'collection_delay':cur['delay'],
                          'deployment_gain':derived['candidate_gain'] if yes else 0,'deployment_unmet':derived['candidate_unmet'] if yes else 0,
                          'lifecycle_gain':cur['gain']+(derived['candidate_gain'] if yes else 0),'lifecycle_unmet':cur['unmet']+(derived['candidate_unmet'] if yes else 0),
                          'lifecycle_expected_unmet':cur['expected_unmet']+(derived['candidate_expected_unmet'] if yes else 0),
                          'stop_lifecycle_gain':stop_gain+(derived['candidate_gain'] if yes else 0),'stop_lifecycle_unmet':stop_unmet+(derived['candidate_unmet'] if yes else 0),
                          'deployment_delay':derived['candidate_delay'] if yes else 0,
                          'lifecycle_delay':cur['delay']+(derived['candidate_delay'] if yes else 0),
                          'stop_lifecycle_expected_unmet':stop_expected+(derived['candidate_expected_unmet'] if yes else 0),
                          'stop_lifecycle_delay':stop_delay+(derived['candidate_delay'] if yes else 0)}
                for k,value in expected.items():check(near(given[k],value),'method_'+k)
                tested['gate_replays']+=1
        cur=totals['natural'];given=row['methods']['prior'];yes=enabled
        check(given['raw']==prior and given['certified']==yes and given['first_crossing']==(0 if yes else None),'prior_status')
        check(given['false_declaration']==(yes and not eligible),'prior_false')
        expected={'collection_gain':cur['candidate_gain'] if yes else 0,'collection_unmet':cur['candidate_unmet'] if yes else 0,'collection_expected_unmet':cur['candidate_expected_unmet'] if yes else 0,
                  'deployment_gain':derived['candidate_gain'] if yes else 0,'deployment_unmet':derived['candidate_unmet'] if yes else 0,
                  'lifecycle_gain':cur['candidate_gain']+derived['candidate_gain'] if yes else 0,'lifecycle_unmet':cur['candidate_unmet']+derived['candidate_unmet'] if yes else 0,
                  'lifecycle_expected_unmet':cur['candidate_expected_unmet']+derived['candidate_expected_unmet'] if yes else 0,
                  'stop_lifecycle_gain':cur['candidate_gain']+derived['candidate_gain'] if yes else 0,'stop_lifecycle_unmet':cur['candidate_unmet']+derived['candidate_unmet'] if yes else 0,
                  'collection_delay':cur['candidate_delay'] if yes else 0,'deployment_delay':derived['candidate_delay'] if yes else 0,
                  'lifecycle_delay':cur['candidate_delay']+derived['candidate_delay'] if yes else 0,
                  'stop_lifecycle_delay':cur['candidate_delay']+derived['candidate_delay'] if yes else 0,
                  'stop_lifecycle_expected_unmet':cur['candidate_expected_unmet']+derived['candidate_expected_unmet'] if yes else 0}
        for k,value in expected.items():check(near(given[k],value),'prior_'+k)
        given=row['methods']['default'];check(not given['certified'] and not given['false_declaration'] and near(given['lifecycle_gain'],0) and given['lifecycle_unmet']==0,'default')
        previous=H
for i in range(60):
    wb,wap=[worlds[(x,i)] for x in ('B','A_prime')]
    for d in ('A','B'):
        for q in ('p','r','third'):check(wb['users'][d][q]==wap['users'][d][q],'B_Aprime_'+q)

summary=json.loads((out/'summary.json').read_text())
methodnames=('natural_two','natural_three','natural_projection_three','forced_two','forced_three','forced_projection_three','prior','default')
for group in names:
    for H in cps:
        subset=[rows[(group,i,H)] for i in range(60)];entry=summary[group][str(H)]
        check(entry['n']==60,'summary_n');check(entry['truth_ineligible']==sum(not x['world_evaluator_only']['truth_eligible'] for x in subset),'summary_null')
        check(near(entry['true_benefit_mean'],sum(x['world_evaluator_only']['benefit'] for x in subset)/60),'summary_truth_benefit')
        check(near(entry['true_unmet_mean'],sum(x['world_evaluator_only']['unmet'] for x in subset)/60),'summary_truth_unmet')
        expected_comparisons={(v+'_'+a,v+'_'+b) for v in schedules for a,b in (('two','three'),('two','projection_three'),('three','projection_three'))}
        expected_comparisons|={(v+'_'+m,b) for v in schedules for m in ('two','three','projection_three') for b in ('prior','default')}
        expected_comparisons|={('natural_'+m,'forced_'+m) for m in ('two','three','projection_three')}
        expected_comparisons.add(('prior','default'))
        check(set(entry['paired'])=={a+'_minus_'+b for a,b in expected_comparisons} and len(entry['paired'])==22,'summary_comparison_set')
        for method in methodnames:
            value=entry['methods'][method];yes=sum(x['methods'][method]['certified'] for x in subset);bad=sum(x['methods'][method]['false_declaration'] for x in subset)
            check(value['certified']==yes and value['false']==bad,'summary_counts')
            z=1.959963984540054;prop=yes/60;den=1+z*z/60;center=(prop+z*z/120)/den;radius=z*math.sqrt(prop*(1-prop)/60+z*z/(4*60*60))/den
            check(all(near(a,b) for a,b in zip(value['certified_wilson_95'],[max(0,center-radius),min(1,center+radius)])),'summary_wilson')
            for positive in (True,False):
                for feasible in (True,False):
                    sub=[x for x in subset if (x['world_evaluator_only']['benefit']>0)==positive and (x['world_evaluator_only']['unmet']<=float(x['world_evaluator_only']['physics']['epsilon']))==feasible]
                    s=value['strata'][f'benefit_positive_{positive}_service_feasible_{feasible}']
                    check(s['n']==len(sub) and s['certified']==sum(x['methods'][method]['certified'] for x in sub),'summary_stratum')
            for field,outfield in (('lifecycle_gain','mean_lifecycle_gain'),('collection_gain','mean_collection_gain'),('lifecycle_unmet','mean_lifecycle_unmet'),('lifecycle_expected_unmet','mean_lifecycle_expected_unmet')):
                check(near(value[outfield],sum(x['methods'][method][field] for x in subset)/60),'summary_'+field)
        for key,stat in entry['paired'].items():
            first,second=key.split('_minus_')
            for field,name in (('lifecycle_gain','mean'),('certified','certified_difference'),('stop_lifecycle_gain','stop_gain_difference')):
                expected=sum(float(x['methods'][first][field])-float(x['methods'][second][field]) for x in subset)/60
                check(near(stat[name],expected),'summary_paired_'+field)
            for interval in ('bootstrap_95','certified_bootstrap_95','stop_gain_bootstrap_95'):
                x=stat[interval];check(len(x)==2 and all(math.isfinite(v) for v in x) and x[0]<=x[1],'bootstrap_interval_shape')
        for variant in schedules:
            for driver in ('A','B'):
                for offer in offs:
                    for j,field in ((0,'mean_accepted'),(1,'mean_offered')):
                        check(near(entry[field][variant][driver][offer],sum(x['counts'][variant][driver][offer][j] for x in subset)/60),'summary_'+field)
        check(near(entry['mean_natural_suppressed'],sum(x['totals']['natural']['suppressed'] for x in subset)/60),'summary_suppressed')
        if H in (12288,100000,1000000,3000000):
            print(group,H,' '.join(f'{m}:{entry["methods"][m]["certified"]}/{entry["methods"][m]["false"]}' for m in methodnames))
print('groups',dict(groups),'rows',len(rows),'pairs',len(worlds),'tested',dict(tested),'FAILURES',dict(errors))
if errors:raise SystemExit(1)
