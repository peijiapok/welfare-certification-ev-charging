"""Prospective projection comparison. Importing performs no study draws."""
from __future__ import annotations
import hashlib
import itertools
import json
import math
import os
import platform
import signal
import time
from pathlib import Path
from decimal import Decimal
import numpy as np
from personalized_charging.two_driver_exploratory_v1.gate import (
    evaluate, prior_only, probability_band, benefit_service_bounds,
    two_theta_outer, three_theta_outer, two_witness, three_witness)
from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.variable_physics_exploratory_v1.gate import coefficients
from personalized_charging.logit_polytope_exploratory_v1.projector import (
    evaluate as projection_evaluate, project_driver)

ROOT = Path(__file__).resolve().parents[2]
SEED, BOOT_SEED = 71960431, 71960432
PAIRS, DEPLOYMENT, BOOTSTRAPS = 60, 32, 2000
CHECKPOINTS = (16, 64, 256, 1024, 4096, 12288, 100000, 1000000, 3000000)
CATEGORIES = tuple(itertools.product(range(3), range(2), range(2)))
REQUIRED = tuple(sorted((
    'personalized_charging/projection_comparison_study_v1/PROTOCOL.md',
    'personalized_charging/projection_comparison_study_v1/run.py',
    'personalized_charging/projection_comparison_study_v1/test_run.py',
    'personalized_charging/projection_comparison_study_v1/test_audit_regressions.py',
    'personalized_charging/logit_polytope_exploratory_v1/projector.py',
    'personalized_charging/logit_polytope_exploratory_v1/test_projector.py',
    'personalized_charging/logit_polytope_exploratory_v1/test_independent_geometry.py',
    'personalized_charging/two_driver_study_v1/PROTOCOL.md',
    'personalized_charging/two_driver_study_v1/run.py',
    'personalized_charging/two_driver_study_v1/test_run.py',
    'personalized_charging/two_driver_exploratory_v1/gate.py',
    'personalized_charging/two_driver_exploratory_v1/physical.py',
    'personalized_charging/two_driver_exploratory_v1/schedule.py',
    'personalized_charging/two_driver_exploratory_v1/test_prototype.py',
    'personalized_charging/variable_physics_exploratory_v1/physical.py',
    'personalized_charging/sequential_identification_v1/physical.py',
    'personalized_charging/variable_physics_exploratory_v1/test_extension.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/test_gate.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/test_gate.py',
    'personalized_charging/two_driver_exploratory_v1/test_independent_fraction.py',
    'personalized_charging/__init__.py', 'personalized_charging/core.py',
    'personalized_charging/choices.py', 'personalized_charging/observations.py',
    'personalized_charging/profiles.py', 'personalized_charging/reservations.py',
    'personalized_charging/bridge.py',
    'personalized_charging/variable_physics_exploratory_v1/gate.py',
    'personalized_charging/variable_physics_exploratory_v1/prior_gate.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/gate.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/gate.py',
    'personalized_charging/p3d_diagnostic_v1/interval.py',
)))
SCHEDULES = ('natural', 'forced')
DATA_METHODS = ('two', 'three', 'projection_three')
OFFERS = ('p', 'r', 'third')

def physics(g0,g1,g2,delta,W,epsilon):
    return dict(g0=g0,g1=g1,g2=g2,delta=delta,W=W,epsilon=epsilon)

GROUPS = (
    ('prior_positive', physics('.8','.65','.4','.005','20','.005'), (0.,.25), 'ordinary'),
    ('positive_mixed', physics('.568','.548','.4','.005','20','.005'), (0.,.12), 'ordinary'),
    ('harmful', physics('.568','.548','.4','.005','20','.005'), (.15,.25), 'ordinary'),
    ('tight', physics('.75','.65','.45','.01','10','.0085'), (0.,.25), 'ordinary'),
    ('B', physics('.568','.548','.4','.005','20','.005'), None, 'B'),
    ('A_prime', physics('.568','.548','.4','.005','20','.005'), None, 'A_prime'),
)

def rng(key):
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(key)))

def sigmoid(x):
    return 1/(1+math.exp(-x)) if x>=0 else math.exp(x)/(1+math.exp(x))

def world(gi, pair):
    name, phys, theta_range, mode = GROUPS[gi]
    users = {}
    for index, label in enumerate(('A','B')):
        if mode == 'B':
            theta,tau,c = ((2/35,1/7,0.) if label=='A' else (1/14,1/7,0.))
            keys = None
        elif mode in ('A','A_prime'):
            theta,tau,c = ((.08,.2,.2) if label=='A' else (.10,.2,.2))
            keys = None
        else:
            keys = [[SEED,0,gi,pair,index,j] for j in range(3)]
            theta = float(rng(keys[0]).uniform(*theta_range))
            tau = float(rng(keys[1]).uniform(.08,.3))
            c = float(rng(keys[2]).uniform(-.2,.2))
        probs = dict(p=sigmoid((.1-theta)/tau+c), r=sigmoid((.1-theta/2)/tau+c),
                     third=sigmoid((.2-theta)/tau+c+(.2 if mode=='A_prime' else 0.)))
        if mode in ('A','B','A_prime'):
            # Mathematically equal target probabilities use identical floats.
            p_log,r_log,t_log = ((.3,.5,.8) if label=='A' else (.2,.45,.7))
            if mode in ('B','A_prime'): t_log += .2
            probs = dict(p=sigmoid(p_log),r=sigmoid(r_log),third=sigmoid(t_log))
        users[label] = dict(theta=theta,tau=tau,c=c,keys=keys,**probs)
    pa, rb = users['A']['p'], users['B']['r']
    g0,g1,g2,d,W=(float(phys[k]) for k in ('g0','g1','g2','delta','W'))
    a,b=g0-g2-d*(W-g2),g1-g2-d*(W-g2)
    benefit=pa*(a-users['A']['theta'])+(1-pa)*rb*(b-users['B']['theta']/2)
    unmet=d*(pa+(1-pa)*rb)
    return dict(name=name,physics=phys,users=users,benefit=benefit,unmet=unmet,
                truth_eligible=benefit>0 and unmet<=float(phys['epsilon']))

def schedule_count(start,end,pos):
    if not 0<=start<=end or pos not in range(6): raise ValueError('bad schedule range')
    return (end+5-pos)//6-(start+5-pos)//6

def cells_for(w, role, count, key):
    first,second=('A','B') if role=='AB' else ('B','A')
    p,t=w['users'][first]['p'],w['users'][first]['third']
    r=w['users'][second]['r']; d=float(w['physics']['delta'])
    if not 0<=p<t<=1 or not 0<=r<=1 or not 0<=d<=1: raise ValueError('bad probabilities')
    probs=[x*(r if rb else 1-r)*(d if u else 1-d)
           for x,rb,u in (([p,t-p,1-t][f],rbit,urgent) for f,rbit,urgent in CATEGORIES)]
    total=math.fsum(probs)
    if abs(total-1)>1e-12 or any(x<0 for x in probs): raise ValueError('bad multinomial')
    cells=[int(x) for x in rng(key).multinomial(count,[x/total for x in probs])]
    if sum(cells)!=count: raise ValueError('bad multinomial count')
    return cells

def ledger(w,role,pos,cells,variant):
    """Map potential joint cells to only physically offered feedback and costs."""
    first,second=('A','B') if role=='AB' else ('B','A')
    phys=w['physics']; g0,g1,g2,W=(float(phys[k]) for k in ('g0','g1','g2','W'))
    th0=w['users'][first]['theta']; th1=w['users'][second]['theta']
    observed={i:{j:[0,0] for j in OFFERS} for i in ('A','B')}
    result=dict(gain=0.,unmet=0,delay=0.,candidate_gain=0.,candidate_unmet=0,
                candidate_delay=0.,suppressed=0,urgent=0,expected_unmet=0.,candidate_expected_unmet=0.)
    for n,(f,rb,urgent) in zip(cells,CATEGORIES):
        p=(f==0); third=(f!=2); r=bool(rb)
        # All candidate potentials shown here are only for AB calendar positions.
        c0=p; c1=(not p and r); occ=c0 or c1
        cg=(g0-g2-th0 if c0 else g1-g2-th1/2 if c1 else 0.)-(W-g2)*occ*urgent
        if role=='AB':
            result['candidate_gain']+=n*cg; result['candidate_unmet']+=n*int(occ)*urgent
            result['candidate_delay']+=n*(th0*int(c0)+th1/2*int(c1))
        offered=[]
        if pos in (0,3): offered=[(first,'p',p)]
        elif pos in (2,5): offered=[(first,'third',third)]
        elif pos==1 or (pos==4 and variant=='forced'): offered=[(second,'r',r)]
        elif pos==4:
            offered=[(first,'p',p)]
            if not p: offered.append((second,'r',r))
            else: result['suppressed']+=n
        else: raise ValueError('bad schedule position')
        chosen_first=any(i==first and yes for i,_,yes in offered)
        chosen_second=any(i==second and yes for i,_,yes in offered)
        if chosen_first and chosen_second: raise ValueError('port over capacity')
        selected=chosen_first or chosen_second
        gain=(g0-g2-th0 if chosen_first else g1-g2-th1/2 if chosen_second else 0.)-(W-g2)*selected*urgent
        result['gain']+=n*gain; result['unmet']+=n*int(selected)*urgent
        result['delay']+=n*(th0*int(chosen_first)+th1/2*int(chosen_second))
        result['urgent']+=n*urgent
        for who,offer,yes in offered:
            observed[who][offer][0]+=n*int(yes); observed[who][offer][1]+=n
    d=float(phys['delta']); fuser=w['users'][first]; suser=w['users'][second]
    q=(fuser['p'] if pos in (0,3) else fuser['third'] if pos in (2,5) else
       suser['r'] if pos==1 or variant=='forced' else fuser['p']+(1-fuser['p'])*suser['r'])
    result['expected_unmet']=sum(cells)*d*q
    if role=='AB': result['candidate_expected_unmet']=sum(cells)*d*(fuser['p']+(1-fuser['p'])*suser['r'])
    result['observed']=observed
    return result

def empty_total():
    return dict(gain=0.,unmet=0,delay=0.,candidate_gain=0.,candidate_unmet=0,
                candidate_delay=0.,suppressed=0,urgent=0,expected_unmet=0.,candidate_expected_unmet=0.)

def validate_prior(result, phys):
    if not isinstance(result,dict) or result.get('decision') not in ('ALLOW','ABSTAIN'):
        raise ValueError('invalid prior decision')
    a,b=coefficients(*(Decimal(phys[k]) for k in ('g0','g1','g2','delta','W')))
    if result.get('a')!=a.json() or result.get('b')!=b.json() or result.get('service_upper')!=str(Decimal(phys['delta'])):
        raise ValueError('invalid prior physical bounds')
    enough=a.lo>=Decimal('.25') and b.lo>=Decimal('.125') and (a.lo>Decimal('.25') or b.lo>Decimal('.125'))
    service=Decimal(phys['delta'])<=Decimal(phys['epsilon'])
    reason=('service_not_certified' if not service else 'prior_pointwise_positive' if enough else 'prior_not_certified')
    if result.get('reason')!=reason or (result['decision']=='ALLOW')!=(service and enough):
        raise ValueError('invalid prior certificate')


def validate_gate(result, counts, method, phys):
    if not isinstance(result,dict) or result.get('decision') not in ('ALLOW','ABSTAIN'):
        raise ValueError('invalid gate decision')
    reason=result.get('reason')
    early=('missing_stream','noninterior_probability_band','empty_or_unresolved_outer','central_witness_not_verified')
    if reason in early:
        if result['decision']!='ABSTAIN' or result!=evaluate(counts,method=method,**phys):
            raise ValueError('invalid early gate diagnostic')
        return
    if reason not in ('outward_bounds','benefit_not_positive','service_not_certified'):
        raise ValueError('unknown gate or numerical failure')
    keys=('p','r') if method=='two' else OFFERS
    pairs={d:{k:probability_band(*counts[d][k]) for k in keys} for d in ('A','B')}
    bands={d:{k:pairs[d][k][0] for k in keys} for d in ('A','B')}
    empirical={d:{k:pairs[d][k][1] for k in keys} for d in ('A','B')}
    if result.get('bands')!={d:{k:bands[d][k].json() for k in keys} for d in ('A','B')}:
        raise ValueError('confidence bands mismatch')
    outer_function=two_theta_outer if method=='two' else three_theta_outer
    witness_function=two_witness if method=='two' else three_witness
    outer={d:outer_function(bands[d]) for d in ('A','B')}
    witness={d:witness_function(empirical[d]) for d in ('A','B')}
    if any(outer[d] is None or witness[d] is None for d in ('A','B')):
        raise ValueError('missing feasible witness')
    if result.get('theta_outer')!={d:outer[d].json() for d in ('A','B')} or result.get('witness')!=witness:
        raise ValueError('outer set or witness mismatch')
    a,b=coefficients(*(Decimal(phys[k]) for k in ('g0','g1','g2','delta','W')))
    benefit,service=benefit_service_bounds(bands['A']['p'],bands['B']['r'],outer['A'],outer['B'],a,b,I(phys['delta']))
    if (result.get('a')!=a.json() or result.get('b')!=b.json() or
        result.get('benefit_interval')!=benefit.json() or result.get('candidate_service_upper')!=str(service) or
        result.get('baseline_service_upper')!='0'):
        raise ValueError('physical certificate bounds mismatch')
    eligible=benefit.lo>0 and service<=Decimal(phys['epsilon'])
    expected=('outward_bounds' if eligible else 'benefit_not_positive' if benefit.lo<=0 else 'service_not_certified')
    if reason!=expected or (result['decision']=='ALLOW')!=eligible: raise ValueError('inconsistent gate result')

def validate_projection_gate(result, counts, phys):
    """Recompute driver projections and physical bounds from observed data.

    This is a consistency check, not an independent arithmetic implementation
    or proof replay: it shares the same project_driver and interval code.
    """
    if not isinstance(result,dict) or result.get('decision') not in ('ALLOW','ABSTAIN'):
        raise ValueError('invalid projection decision')
    projections=result.get('projections')
    if not isinstance(projections,dict) or set(projections)!={'A','B'}:
        raise ValueError('invalid projection records')
    for driver in ('A','B'):
        actual=projections[driver]
        expected=project_driver(counts[driver],method='three')
        if not isinstance(actual,dict) or actual != expected:
            raise ValueError('projection record mismatch')
        if actual.get('status')=='PROJECTED':
            if set(actual)!={'status','reason','bands','theta_outer','theta_bounds_exact_outer','vertices','witness'} or actual['reason']!='verified_witness':
                raise ValueError('invalid projected schema')
            expected_bands={k:(I('0','1') if counts[driver][k][1]==0 else
                               probability_band(*counts[driver][k])[0]).json() for k in OFFERS}
            if actual['bands']!=expected_bands:
                raise ValueError('projection confidence bands mismatch')
            theta=I(*actual['theta_outer'])
            if not 0<=theta.lo<=theta.hi<=Decimal('.25'):
                raise ValueError('invalid projected theta')
            if not isinstance(actual['witness'],dict) or set(actual['witness'])!={'h','lambda','v','theta','tau','common_shift'}:
                raise ValueError('invalid witness schema')
        elif (actual.get('status')!='ABSTAIN' or set(actual)!={'status','reason'} or
              actual.get('reason') not in ('empty_outer','unverified_feasibility')):
            raise ValueError('invalid or numerical projection failure')
    unresolved=any(projections[d]['status']!='PROJECTED' for d in ('A','B'))
    if unresolved:
        if (set(result)!={'decision','reason','projections'} or result['decision']!='ABSTAIN' or
            result.get('reason')!='projection_unresolved'):
            raise ValueError('invalid unresolved projection')
        return
    if set(result)!={'decision','reason','benefit_interval','candidate_service_upper','baseline_service_upper','a','b','projections'}:
        raise ValueError('invalid projection decision schema')
    a,b=coefficients(*(Decimal(phys[k]) for k in ('g0','g1','g2','delta','W')))
    p=I(*projections['A']['bands']['p']); r=I(*projections['B']['bands']['r'])
    ta=I(*projections['A']['theta_outer']); tb=I(*projections['B']['theta_outer'])
    benefit,service=benefit_service_bounds(p,r,ta,tb,a,b,I(phys['delta']))
    if (result['a']!=a.json() or result['b']!=b.json() or
        result['benefit_interval']!=benefit.json() or result['candidate_service_upper']!=str(service) or
        result['baseline_service_upper']!='0'):
        raise ValueError('projection physical bounds mismatch')
    eligible=benefit.lo>0 and service<=Decimal(phys['epsilon'])
    expected_reason='outward_bounds' if eligible else 'benefit_not_positive' if benefit.lo<=0 else 'service_not_certified'
    if (result['decision']=='ALLOW')!=eligible or result['reason']!=expected_reason:
        raise ValueError('inconsistent projection decision')


def call_gate(counts, method, phys):
    """Pass strictly observed counts and known physics; never pass the world or cells."""
    if method not in DATA_METHODS or set(counts) != {'A','B'}:
        raise ValueError('bad gate input')
    offers = ('p','r') if method == 'two' else OFFERS
    if any(set(counts[d]) != set(offers) for d in ('A','B')):
        raise ValueError('unexpected or missing observed data')
    observed = {d:{k:tuple(counts[d][k]) for k in offers} for d in ('A','B')}
    if set(phys) != {'g0','g1','g2','delta','W','epsilon'}:
        raise ValueError('unexpected physics input')
    known = dict(phys)
    if method != 'projection_three':
        result = evaluate(observed,method=method,**known)
        validate_gate(result,observed,method,known)
        return result
    result = projection_evaluate(observed,method='three',**known)
    validate_projection_gate(result,observed,known)
    return result


def rows_for_pair(gi,pair):
    w=world(gi,pair); phys=w['physics']; prior=prior_only(**phys)
    validate_prior(prior,phys)
    counts={v:{i:{j:[0,0] for j in OFFERS} for i in ('A','B')} for v in SCHEDULES}
    totals={v:empty_total() for v in SCHEDULES}
    latch={v:{m:None for m in DATA_METHODS} for v in SCHEDULES}
    snapshots={v:{m:None for m in DATA_METHODS} for v in SCHEDULES}
    previous=0; rows=[]
    for ci,H in enumerate(CHECKPOINTS):
        blocks=[]
        for pos in range(6):
            count=schedule_count(previous,H,pos); role='AB' if pos%2==0 else 'BA'
            key=[SEED,1,gi,pair,ci,pos]; cells=cells_for(w,role,count,key)
            per={v:ledger(w,role,pos,cells,v) for v in SCHEDULES}
            for v in SCHEDULES:
                for k in totals[v]: totals[v][k]+=per[v][k]
                for i in ('A','B'):
                    for j in OFFERS:
                        for k in (0,1): counts[v][i][j][k]+=per[v]['observed'][i][j][k]
            blocks.append(dict(position=pos,role=role,count=count,key=key,cells_evaluator_only=cells,ledgers=per))
        depkey=[SEED,2,gi,pair,ci,0]
        dcells=cells_for(w,'AB',DEPLOYMENT,depkey)
        dep=ledger(w,'AB',4,dcells,'natural')
        methods={}
        for v in SCHEDULES:
            for m in DATA_METHODS:
                observed={i:{j:tuple(counts[v][i][j]) for j in (('p','r') if m=='two' else OFFERS)} for i in ('A','B')}
                t=time.monotonic(); decision=call_gate(observed,m,phys); elapsed=time.monotonic()-t
                if decision['decision']=='ALLOW' and latch[v][m] is None:
                    latch[v][m]=H; snapshots[v][m]=dict(totals[v])
                yes=latch[v][m] is not None; snap=snapshots[v][m]; cur=totals[v]
                stop_gain=cur['gain'] if snap is None else snap['gain']+cur['candidate_gain']-snap['candidate_gain']
                stop_unmet=cur['unmet'] if snap is None else snap['unmet']+cur['candidate_unmet']-snap['candidate_unmet']
                stop_expected=cur['expected_unmet'] if snap is None else snap['expected_unmet']+cur['candidate_expected_unmet']-snap['candidate_expected_unmet']
                stop_delay=cur['delay'] if snap is None else snap['delay']+cur['candidate_delay']-snap['candidate_delay']
                methods[v+'_'+m]=dict(raw=decision,elapsed_seconds=elapsed,first_crossing=latch[v][m],
                    certified=yes,false_declaration=bool(yes and not w['truth_eligible']),
                    collection_gain=cur['gain'],collection_unmet=cur['unmet'],collection_expected_unmet=cur['expected_unmet'],collection_delay=cur['delay'],
                    deployment_gain=dep['candidate_gain'] if yes else 0.,deployment_unmet=dep['candidate_unmet'] if yes else 0,
                    deployment_delay=dep['candidate_delay'] if yes else 0.,
                    lifecycle_gain=cur['gain']+(dep['candidate_gain'] if yes else 0.),
                    lifecycle_unmet=cur['unmet']+(dep['candidate_unmet'] if yes else 0),
                    lifecycle_expected_unmet=cur['expected_unmet']+(dep['candidate_expected_unmet'] if yes else 0.),
                    lifecycle_delay=cur['delay']+(dep['candidate_delay'] if yes else 0.),
                    stop_lifecycle_gain=stop_gain+(dep['candidate_gain'] if yes else 0.),
                    stop_lifecycle_unmet=stop_unmet+(dep['candidate_unmet'] if yes else 0),
                    stop_lifecycle_expected_unmet=stop_expected+(dep['candidate_expected_unmet'] if yes else 0.),
                    stop_lifecycle_delay=stop_delay+(dep['candidate_delay'] if yes else 0.))
        yes=prior['decision']=='ALLOW'; cur=totals['natural']
        methods['prior']=dict(raw=prior,first_crossing=0 if yes else None,certified=yes,
            false_declaration=bool(yes and not w['truth_eligible']),
            collection_gain=cur['candidate_gain'] if yes else 0.,collection_unmet=cur['candidate_unmet'] if yes else 0,
            collection_expected_unmet=cur['candidate_expected_unmet'] if yes else 0.,
            collection_delay=cur['candidate_delay'] if yes else 0.,
            deployment_gain=dep['candidate_gain'] if yes else 0.,deployment_unmet=dep['candidate_unmet'] if yes else 0,
            deployment_delay=dep['candidate_delay'] if yes else 0.,
            lifecycle_gain=cur['candidate_gain']+dep['candidate_gain'] if yes else 0.,
            lifecycle_unmet=cur['candidate_unmet']+dep['candidate_unmet'] if yes else 0,
            lifecycle_expected_unmet=cur['candidate_expected_unmet']+dep['candidate_expected_unmet'] if yes else 0.,
            lifecycle_delay=cur['candidate_delay']+dep['candidate_delay'] if yes else 0.,
            stop_lifecycle_gain=cur['candidate_gain']+dep['candidate_gain'] if yes else 0.,
            stop_lifecycle_unmet=cur['candidate_unmet']+dep['candidate_unmet'] if yes else 0,
            stop_lifecycle_expected_unmet=cur['candidate_expected_unmet']+dep['candidate_expected_unmet'] if yes else 0.,
            stop_lifecycle_delay=cur['candidate_delay']+dep['candidate_delay'] if yes else 0.)
        methods['default']=dict(certified=False,false_declaration=False,collection_gain=0.,collection_unmet=0,
            deployment_gain=0.,deployment_unmet=0,lifecycle_gain=0.,lifecycle_unmet=0,
            collection_expected_unmet=0.,lifecycle_expected_unmet=0.,
            collection_delay=0.,deployment_delay=0.,lifecycle_delay=0.,
            stop_lifecycle_gain=0.,stop_lifecycle_unmet=0,stop_lifecycle_expected_unmet=0.,stop_lifecycle_delay=0.)
        rows.append(dict(group=w['name'],group_index=gi,pair=pair,checkpoint=H,block_start=previous,
            world_evaluator_only=w,block_evaluator_only=blocks,counts=counts,totals=totals,
            deployment_evaluator_only=dict(key=depkey,cells=dcells,ledger=dep),methods=methods))
        # Counts and totals are mutable across checkpoints; freeze each record now.
        rows[-1]=json.loads(json.dumps(rows[-1],allow_nan=False))
        previous=H
    return rows

def wilson(s,n):
    if not n: return None
    z=1.959963984540054; p=s/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den; radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0.,center-radius),min(1.,center+radius)]


def summarize(rows):
    result={}
    for gi,(group,*_) in enumerate(GROUPS):
        result[group]={}
        for ci,H in enumerate(CHECKPOINTS):
            subset=[x for x in rows if x['group']==group and x['checkpoint']==H]
            if len(subset)!=PAIRS or len({x['pair'] for x in subset})!=PAIRS: raise ValueError('missing pair')
            sampling=rng([BOOT_SEED,gi,ci]).integers(0,PAIRS,size=(BOOTSTRAPS,PAIRS))
            entry=dict(n=PAIRS,true_benefit_mean=float(np.mean([x['world_evaluator_only']['benefit'] for x in subset])),
                true_unmet_mean=float(np.mean([x['world_evaluator_only']['unmet'] for x in subset])),
                truth_ineligible=sum(not x['world_evaluator_only']['truth_eligible'] for x in subset),methods={},paired={})
            for m in tuple(v+'_'+m for v in SCHEDULES for m in DATA_METHODS)+('prior','default'):
                values=np.array([x['methods'][m]['lifecycle_gain'] for x in subset])
                entry['methods'][m]=dict(certified=sum(x['methods'][m]['certified'] for x in subset),
                    false=sum(x['methods'][m]['false_declaration'] for x in subset),
                    mean_lifecycle_gain=float(values.mean()),
                    mean_collection_gain=float(np.mean([x['methods'][m]['collection_gain'] for x in subset])),
                    mean_lifecycle_unmet=float(np.mean([x['methods'][m]['lifecycle_unmet'] for x in subset])),
                    mean_lifecycle_expected_unmet=float(np.mean([x['methods'][m]['lifecycle_expected_unmet'] for x in subset])),
                    certified_wilson_95=wilson(sum(x['methods'][m]['certified'] for x in subset),PAIRS),
                    strata={f'benefit_positive_{positive}_service_feasible_{service}':dict(
                        n=sum((x['world_evaluator_only']['benefit']>0)==positive and (x['world_evaluator_only']['unmet']<=float(x['world_evaluator_only']['physics']['epsilon']))==service for x in subset),
                        certified=sum(x['methods'][m]['certified'] and (x['world_evaluator_only']['benefit']>0)==positive and (x['world_evaluator_only']['unmet']<=float(x['world_evaluator_only']['physics']['epsilon']))==service for x in subset))
                        for positive in (True,False) for service in (True,False)})
            comparisons = [(v+'_'+a,v+'_'+b) for v in SCHEDULES for a,b in
                           (('two','three'),('two','projection_three'),('three','projection_three'),
                            ('projection_three','prior'),('projection_three','default'))]
            comparisons += [('natural_'+m,'forced_'+m) for m in DATA_METHODS]
            for a,b in comparisons:
                d=np.array([x['methods'][a]['lifecycle_gain']-x['methods'][b]['lifecycle_gain'] for x in subset])
                cert=np.array([int(x['methods'][a]['certified'])-int(x['methods'][b]['certified']) for x in subset])
                stop=np.array([x['methods'][a]['stop_lifecycle_gain']-x['methods'][b]['stop_lifecycle_gain'] for x in subset])
                entry['paired'][a+'_minus_'+b]=dict(mean=float(d.mean()),bootstrap_95=[float(x) for x in np.quantile(d[sampling].mean(axis=1),[.025,.975])],
                    certified_difference=float(cert.mean()),certified_bootstrap_95=[float(x) for x in np.quantile(cert[sampling].mean(axis=1),[.025,.975])],
                    stop_gain_difference=float(stop.mean()),stop_gain_bootstrap_95=[float(x) for x in np.quantile(stop[sampling].mean(axis=1),[.025,.975])])
            entry['mean_offered']={v:{i:{j:float(np.mean([x['counts'][v][i][j][1] for x in subset])) for j in OFFERS} for i in ('A','B')} for v in SCHEDULES}
            entry['mean_accepted']={v:{i:{j:float(np.mean([x['counts'][v][i][j][0] for x in subset])) for j in OFFERS} for i in ('A','B')} for v in SCHEDULES}
            entry['mean_natural_suppressed']=float(np.mean([x['totals']['natural']['suppressed'] for x in subset]))
            result[group][str(H)]=entry
    return result

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def sources(manifest):
    expected=json.loads(Path(manifest).read_text())['sha256']
    if sorted(expected)!=list(REQUIRED) or any(not (ROOT/name).is_file() for name in expected): raise ValueError('invalid manifest')
    actual={name:digest(ROOT/name) for name in expected}
    if actual!=expected: raise ValueError('source hash mismatch')
    return actual

def write_json(path,obj):
    with open(path,'x',encoding='utf-8') as f:
        json.dump(obj,f,sort_keys=True,indent=2,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())

def chain_record(previous, row):
    """Bind each row and its predecessor using canonical UTF-8 JSON."""
    body=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    digest_value=hashlib.sha256(bytes.fromhex(previous)+body).hexdigest()
    return {'previous_sha256':previous,'sha256':digest_value,'row':row}

def finish_receipt(out, record, start):
    # The official receipt appears atomically only after complete output and
    # timing checks. An interruption while writing the temporary file cannot
    # create a completion receipt.
    temp=out/'completion_pending.json'
    write_json(temp,record)
    blocked={signal.SIGALRM,signal.SIGINT,signal.SIGTERM}
    oldmask=signal.pthread_sigmask(signal.SIG_BLOCK,blocked)
    try:
        if time.monotonic()-start>=600 or signal.sigpending().intersection(blocked):
            raise TimeoutError('interrupted or expired before completion')
        signal.alarm(0)
        os.replace(temp,out/'completed.json')
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK,oldmask)


def main():
    import argparse
    parser=argparse.ArgumentParser(); parser.add_argument('--manifest',required=True); parser.add_argument('--out',required=True)
    args=parser.parse_args(); start=time.monotonic()
    def expired(*_): raise TimeoutError('600-second study wall limit')
    signal.signal(signal.SIGALRM,expired); signal.alarm(600)
    manifest_hash=digest(args.manifest); before=sources(args.manifest); out=Path(args.out); out.mkdir(parents=True,exist_ok=False)
    write_json(out/'started.json',dict(manifest_sha256=manifest_hash,seed=SEED,started_utc=time.time()))
    rows=[]; chain='00'*32
    with (out/'checkpoints.jsonl').open('x',encoding='utf-8') as f:
        for gi in range(len(GROUPS)):
            for pair in range(PAIRS):
                batch=rows_for_pair(gi,pair); rows.extend(batch)
                for row in batch:
                    record=chain_record(chain,row); chain=record['sha256']
                    f.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n')
                f.flush()
        os.fsync(f.fileno())
    write_json(out/'summary.json',summarize(rows))
    if sources(args.manifest)!=before or digest(args.manifest)!=manifest_hash: raise ValueError('source or manifest changed during study')
    outputs={p.name:digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    finish_receipt(out,dict(status='complete',manifest_sha256=manifest_hash,elapsed_seconds=time.monotonic()-start,source_sha256=before,
        output_sha256=outputs,chain_head=chain,row_count=len(rows),python=platform.python_version(),numpy=np.__version__),start)
    print(json.dumps(dict(out=str(out),rows=len(rows),elapsed_seconds=time.monotonic()-start)))

if __name__=='__main__': main()
