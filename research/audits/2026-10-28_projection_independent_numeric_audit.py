#!/usr/bin/env python3
"""Read-only high-precision cross-check of a completed projection study.

This independent numeric diagnostic uses mpmath, not the study's interval or
projection code. It consumes observed counts, known physics and recorded gate
outputs, and uses no RNG. It is NOT a rigorous directed-rounding proof or an
audit of sampling, physical ledgers, confidence coverage or source provenance.
Run --self-test for synthetic deterministic controls. Actual outputs may be read
only after the operator has received the study completion notice; the script
also requires a valid completion receipt and verifies the recorded data hash.
"""
import argparse
import hashlib
import itertools
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

import mpmath as mp

mp.mp.dps = 100
TOL = mp.mpf('1e-28')
OFFSETS = {'p': (mp.mpf('0'), mp.mpf('0')),
           'r': (mp.mpf('0'), mp.mpf('0.5')),
           'third': (mp.mpf('0.1'), mp.mpf('0'))}


def num(value):
    text = str(value)
    if '/' in text:
        f = Fraction(text)
        return mp.mpf(f.numerator) / f.denominator
    return mp.mpf(text)


def close(a, b):
    return abs(a-b) <= TOL * max(1, abs(a), abs(b))


def le(a, b):
    return a <= b or close(a, b)


def band(counts):
    k, n = counts
    if type(k) is not int or type(n) is not int or n < 0 or k < 0 or k > n:
        raise ValueError('invalid observed counts')
    if n == 0:
        return mp.mpf('0'), mp.mpf('1')
    r = mp.sqrt(mp.log(240 * mp.mpf(n) * (n + 1)) / (2*n))
    p = mp.mpf(k)/n
    return max(mp.mpf('0'), p-r), min(mp.mpf('1'), p+r)


def logit(p):
    return mp.log(p/(1-p))


def constraints(bands):
    """Four priors plus all finite lower/upper cross-contrast pairs."""
    result = [(mp.mpf('-1'), mp.mpf('0'), mp.mpf('-2.5')),
              (mp.mpf('1'), mp.mpf('0'), mp.mpf('20')),
              (mp.mpf('0'), mp.mpf('-1'), mp.mpf('0')),
              (mp.mpf('-.25'), mp.mpf('1'), mp.mpf('0'))]
    lower = {k: logit(a) for k, (a,b) in bands.items() if a > 0}
    upper = {k: logit(b) for k, (a,b) in bands.items() if b < 1}
    for lower_key, l in lower.items():
        for upper_key, u in upper.items():
            al, bl = OFFSETS[lower_key]
            au, bu = OFFSETS[upper_key]
            result.append((au-al, bu-bl, u-l))
    return result


def polygon_vertices(cons):
    points = []
    for (a,b,c), (d,e,f) in itertools.combinations(cons, 2):
        determinant = a*e-b*d
        if abs(determinant) < mp.mpf('1e-85'):
            continue
        x, y = (c*e-b*f)/determinant, (a*f-c*d)/determinant
        if all(le(u*x+v*y,w) for u,v,w in cons):
            if not any(close(x,oldx) and close(y,oldy) for oldx,oldy in points):
                points.append((x,y))
    return points


def ratio_bounds(points):
    ratios = [v/lam for lam,v in points if lam > 0]
    if len(ratios) != len(points) or not ratios:
        raise ValueError('missing or nonpositive-lambda polygon vertices')
    return min(ratios), max(ratios)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


class Audit:
    def __init__(self):
        self.stats = Counter()
        self.errors = []
        self.latches = {}
        self.last_horizon = {}

    def check(self, condition, where, message):
        self.stats['checks'] += 1
        if not condition:
            self.stats['failures'] += 1
            if len(self.errors) < 50:
                self.errors.append({'where': where, 'error': message})

    def driver(self, entry, counts, where):
        self.stats['driver_projections'] += 1
        nominal = {k: band(counts[k]) for k in OFFSETS}
        status = entry.get('status')
        self.stats['projection_status_' + str(status)] += 1
        if status == 'ABSTAIN':
            reason = entry.get('reason')
            self.check(reason in ('empty_outer', 'unverified_feasibility'), where, 'unexpected abstention reason')
            if reason == 'empty_outer':
                pts = polygon_vertices(constraints(nominal))
                self.check(not pts, where, 'empty_outer despite a numerically feasible nominal polygon')
            return None
        if status != 'PROJECTED':
            self.check(False, where, 'unexpected projection status')
            return None
        self.check(entry.get('reason') == 'verified_witness', where, 'unexpected projection reason')
        rawbands = entry['bands']
        self.check(set(rawbands) == set(OFFSETS), where, 'wrong band keys')
        reported = {}
        for key in OFFSETS:
            lower, upper = map(num, rawbands[key])
            nominal_lo, nominal_hi = nominal[key]
            self.check(le(0,lower) and le(lower,upper) and le(upper,1), where, key + ' invalid band')
            self.check(le(lower,nominal_lo) and le(nominal_hi,upper), where, key + ' does not enclose ideal band')
            reported[key] = (lower,upper)
        cons = constraints(reported)
        points = polygon_vertices(cons)
        self.check(bool(points), where, 'no feasible independent vertices')
        if not points:
            return None
        low, high = ratio_bounds(points)
        theta_lo, theta_hi = map(num, entry['theta_outer'])
        exact_lo, exact_hi = map(num, entry['theta_bounds_exact_outer'])
        self.check(le(theta_lo,exact_lo) and le(exact_hi,theta_hi), where, 'decimal theta does not enclose recorded rational theta')
        self.check(le(exact_lo,low) and le(high,exact_hi), where, 'reported theta does not enclose independent logit polygon')
        self.check(le(0,theta_lo) and le(theta_hi,mp.mpf('.25')), where, 'theta interval outside prior')
        saved = [(num(pair[0]),num(pair[1])) for pair in entry['vertices']]
        self.check(bool(saved), where, 'no saved vertices')
        for lam,v in saved:
            self.check(all(le(a*lam+b*v,c) for a,b,c in cons), where, 'reported vertex violates logit constraints')
            self.check(le(exact_lo,v/lam) and le(v/lam,exact_hi), where, 'reported vertex ratio outside extrema')
        witness = entry['witness']
        h, lam, v = (num(witness[k]) for k in ('h','lambda','v'))
        theta, tau, shift = (num(witness[k]) for k in ('theta','tau','common_shift'))
        self.check(le(mp.mpf('2.5'),lam) and le(lam,20) and le(0,v) and le(v,lam/4), where, 'witness violates prior')
        self.check(close(theta,v/lam) and close(tau,1/lam) and close(shift,h-lam/10+v), where, 'witness parameter identity fails')
        for key,(al,bl) in OFFSETS.items():
            z = h+al*lam+bl*v
            q = 1/(1+mp.exp(-z))
            self.check(le(reported[key][0],q) and le(q,reported[key][1]), where, key + ' witness outside probability band')
        return {'bands':reported, 'theta':(theta_lo,theta_hi)}

    def row(self, row):
        self.stats['rows'] += 1
        group, pair, horizon = row['group'], row['pair'], row['checkpoint']
        phys = row['world_evaluator_only']['physics']
        g0,g1,g2,delta,penalty,eps = [num(phys[k]) for k in ('g0','g1','g2','delta','W','epsilon')]
        a,b = g0-g2-delta*(penalty-g2),g1-g2-delta*(penalty-g2)
        for schedule in ('natural','forced'):
            self.stats['gates'] += 1
            where = f'{group}/{pair}/{horizon}/{schedule}'
            method = row['methods'][schedule+'_projection_three']
            raw = method['raw']
            gate_decision = raw.get('decision')
            self.check(gate_decision in ('ALLOW','ABSTAIN'),where,'invalid raw decision')
            projections = raw.get('projections',{})
            self.check(set(projections)=={'A','B'},where,'invalid projections')
            if set(projections)!={'A','B'}:
                continue
            results = {driver:self.driver(projections[driver], row['counts'][schedule][driver], where+'/'+driver)
                       for driver in ('A','B')}
            if any(value is None for value in results.values()):
                self.check(gate_decision=='ABSTAIN' and raw.get('reason')=='projection_unresolved',where,'unresolved projection allowed')
            else:
                self.check(le(num(raw['a'][0]),a) and le(a,num(raw['a'][1])),where,'a coefficient outside enclosure')
                self.check(le(num(raw['b'][0]),b) and le(b,num(raw['b'][1])),where,'b coefficient outside enclosure')
                p = results['A']['bands']['p']; r = results['B']['bands']['r']
                ta = results['A']['theta']; tb = results['B']['theta']
                def benefit(x,y,theta_a,theta_b):
                    return x*(a-theta_a)+(1-x)*y*(b-theta_b/2)
                lower = min(benefit(x,y,ta[1],tb[1]) for x,y in itertools.product(p,r))
                upper = max(benefit(x,y,ta[0],tb[0]) for x,y in itertools.product(p,r))
                actual_lo,actual_hi = map(num,raw['benefit_interval'])
                self.check(le(actual_lo,lower) and le(upper,actual_hi),where,'welfare does not enclose independent corners')
                service = delta*(p[1]+(1-p[1])*r[1])
                reported_service = num(raw['candidate_service_upper'])
                self.check(le(service,reported_service) and le(reported_service,delta),where,'service bound invalid')
                self.check(num(raw['baseline_service_upper'])==0,where,'baseline service not zero')
                eligible = actual_lo>0 and reported_service<=eps
                if eligible and lower <= TOL:
                    self.stats['numerically_unresolved_allow_benefit'] += 1
                if eligible and service > eps:
                    self.stats['numerically_unresolved_allow_service'] += 1
                reason = 'outward_bounds' if eligible else 'benefit_not_positive' if actual_lo<=0 else 'service_not_certified'
                self.check((gate_decision=='ALLOW')==eligible and raw.get('reason')==reason,where,'decision/reason mismatch')
            key = (group,pair,schedule)
            self.check(horizon > self.last_horizon.get(key,0),where,'checkpoints not in increasing order')
            self.last_horizon[key] = horizon
            if gate_decision=='ALLOW' and key not in self.latches:
                self.latches[key] = horizon
            first = self.latches.get(key)
            self.check(method['first_crossing']==first,where,'latched first crossing mismatch')
            self.check(method['certified']==(first is not None),where,'certified latch mismatch')


def self_test():
    cons = constraints({k:(mp.mpf('0'),mp.mpf('1')) for k in OFFSETS})
    points = polygon_vertices(cons)
    lo,hi = ratio_bounds(points)
    assert close(lo,0) and close(hi,mp.mpf('.25'))
    impossible = cons + [(mp.mpf('1'),0,mp.mpf('1'))]
    assert not polygon_vertices(impossible)
    segment = cons + [(0,1,mp.mpf('.5')),(0,-1,mp.mpf('-.5')),
                      (1,0,mp.mpf('4')),(-1,0,mp.mpf('-2.5'))]
    points = polygon_vertices(segment)
    lo,hi = ratio_bounds(points)
    assert close(lo,mp.mpf('.125')) and close(hi,mp.mpf('.2'))
    assert band((0,0)) == (mp.mpf('0'),mp.mpf('1'))
    assert band((0,1)) == (mp.mpf('0'),mp.mpf('1'))
    # Exercise the complete saved-record audit with a hand-constructed,
    # zero-observation public-data case, without importing the real gate.
    projection = {'status':'PROJECTED', 'reason':'verified_witness',
                  'bands':{name:['0','1'] for name in OFFSETS},
                  'theta_outer':['0','0.25'], 'theta_bounds_exact_outer':['0','1/4'],
                  'vertices':[['5/2','0'],['5/2','5/8'],['20','0'],['20','5']],
                  'witness':{'h':'0','lambda':'4','v':'0','theta':'0',
                             'tau':'1/4','common_shift':'-2/5'}}
    raw = {'decision':'ABSTAIN','reason':'benefit_not_positive',
           'projections':{'A':projection,'B':projection},
           'a':['0.07','0.07'],'b':['0.05','0.05'],
           'benefit_interval':['-0.18','0.07'],
           'candidate_service_upper':'0.005','baseline_service_upper':'0'}
    empty_counts = {name:[0,0] for name in OFFSETS}
    method = {'raw':raw,'first_crossing':None,'certified':False}
    fixture = {'group':'fixture','pair':0,'checkpoint':16,
               'world_evaluator_only':{'physics':{'g0':'0.568','g1':'0.548','g2':'0.4',
                                                   'delta':'0.005','W':'20','epsilon':'0.005'}},
               'counts':{s:{d:dict(empty_counts) for d in ('A','B')} for s in ('natural','forced')},
               'methods':{s+'_projection_three':dict(method) for s in ('natural','forced')}}
    audit = Audit()
    audit.row(fixture)
    assert not audit.errors, audit.errors
    print('SELF_TEST_PASS: independent no-data, empty, segment and record controls')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--results',type=Path,help='completed v2 run directory')
    parser.add_argument('--manifest',type=Path,default=Path('personalized_charging/projection_comparison_study_v2/freeze_manifest.json'),
                        help='frozen v2 manifest used by the completed run')
    args = parser.parse_args()
    if args.self_test:
        if args.results:
            parser.error('--self-test cannot be combined with --results')
        self_test()
        return 0
    if not args.results:
        parser.error('use --self-test or --results')
    receipt = json.loads((args.results/'completed.json').read_text())
    if receipt.get('status')!='complete':
        raise ValueError('run completion receipt is not complete')
    manifest_hash = sha256(args.manifest)
    if receipt.get('manifest_sha256') != manifest_hash:
        raise ValueError('completion receipt is not bound to the provided v2 manifest')
    if 'personalized_charging/projection_comparison_study_v2/run.py' not in receipt.get('source_sha256', {}):
        raise ValueError('completion receipt is not for the v2 source')
    started_path = args.results/'started.json'
    if sha256(started_path) != receipt['output_sha256']['started.json']:
        raise ValueError('started marker hash mismatch')
    started = json.loads(started_path.read_text())
    if started.get('seed') != 71960433 or started.get('manifest_sha256') != manifest_hash:
        raise ValueError('started marker does not identify the frozen v2 run')
    data = args.results/'checkpoints.jsonl'
    expected = receipt['output_sha256']['checkpoints.jsonl']
    actual = sha256(data)
    if actual != expected:
        raise ValueError('checkpoints hash does not match completion receipt')
    audit = Audit()
    chain = '00'*32
    with data.open(encoding='utf-8') as stream:
        for line_number,line in enumerate(stream,1):
            record = json.loads(line)
            body = json.dumps(record['row'],sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
            current = hashlib.sha256(bytes.fromhex(chain)+body).hexdigest()
            if record['previous_sha256']!=chain or record['sha256']!=current:
                raise ValueError(f'checkpoint chain mismatch at line {line_number}')
            chain = current
            audit.row(record['row'])
    audit.check(chain==receipt['chain_head'],'receipt','checkpoint chain head mismatch')
    audit.check(audit.stats['rows']==receipt['row_count'],'receipt','row count mismatch')
    audit.check(audit.stats['rows']==3240,'receipt','unexpected v2 protocol row count')
    if audit.stats['failures']:
        status = 'FAIL'
    elif audit.stats['numerically_unresolved_allow_benefit'] or audit.stats['numerically_unresolved_allow_service']:
        status = 'INCONCLUSIVE_NEAR_ALLOW_BOUNDARY'
    else:
        status = 'PASS'
    result = {'status': status,
              'scope':'mpmath numerical diagnostic only; not a proof, statistical calibration, or RNG/physical audit',
              'precision_decimal_digits':mp.mp.dps,'relative_or_absolute_tolerance':str(TOL),
              'manifest_sha256':manifest_hash,'checkpoint_sha256':actual,'rows':audit.stats['rows'],'counts':dict(audit.stats),
              'first_errors':audit.errors}
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if result['status']=='PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
