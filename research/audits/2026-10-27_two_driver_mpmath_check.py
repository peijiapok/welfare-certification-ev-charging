"""independent non-rigorous numeric cross-check of stored gate outputs.

Only saved offered-response counts and known physical inputs are read. This
script imports mpmath, not the study's interval/gate/solver code. It does not
generate, re-run, or modify scientific data. High precision is a numerical
cross-check, not a directed-rounding proof.
"""
import argparse
import json
from collections import Counter
from pathlib import Path

import mpmath as mp

mp.mp.dps = 110
TOL = mp.mpf('1e-75')
DRIVERS = ('A', 'B')
SCHEDULES = ('natural', 'forced')
METHODS = ('two', 'three')
OFFERS = ('p', 'r', 'third')
failures, tested, reasons, examples = Counter(), Counter(), Counter(), []


def check(condition, name, where):
    tested[name] += 1
    if not condition:
        failures[name] += 1
        if len(examples) < 20:
            examples.append({'check': name, 'where': where})


def m(value):
    return mp.mpf(str(value))


def encloses(interval, low, high):
    return m(interval[0]) <= low+TOL and m(interval[1]) >= high-TOL


def band(successes, total):
    mean = mp.mpf(successes)/total
    radius = mp.sqrt(mp.log(240*mp.mpf(total)*(total+1))/(2*total))
    return max(mp.mpf(0), mean-radius), min(mp.mpf(1), mean+radius), mean


def logit(probability):
    return mp.log(probability/(1-probability))


def theta_bounds(probability_bands, method):
    lp_lo, lp_hi = map(logit, probability_bands['p'])
    lr_lo, lr_hi = map(logit, probability_bands['r'])
    v_lo = max(mp.mpf(0), 2*(lr_lo-lp_hi))
    v_hi = min(mp.mpf(5), 2*(lr_hi-lp_lo))
    if v_lo > v_hi:
        return None
    if method == 'two':
        return v_lo/20, min(mp.mpf('.25'), mp.mpf('.4')*v_hi)
    lt_lo, lt_hi = map(logit, probability_bands['third'])
    lam_lo = max(mp.mpf('2.5'), 10*(lt_lo-lp_hi))
    lam_hi = min(mp.mpf('20'), 10*(lt_hi-lp_lo))
    if lam_lo > lam_hi or lam_lo <= 0:
        return None
    low = max(mp.mpf(0), v_lo/lam_hi)
    high = min(mp.mpf('.25'), v_hi/lam_lo)
    return None if low > high else (low, high)


def witness_values(centers, method):
    lp, lr = logit(centers['p']), logit(centers['r'])
    v = 2*(lr-lp)
    if method == 'two':
        lam = mp.mpf(20)
    else:
        lam = 10*(logit(centers['third'])-lp)
    if lam <= 0:
        return None
    values = {'theta_over_tau': v, 'theta': v/lam, 'tau': 1/lam,
              'common_shift': lp-mp.mpf('.1')*lam+v}
    if method == 'three':
        values['lambda'] = lam
    return values


def physical_coefficients(physics):
    g0, g1, g2, W, delta = (m(physics[key]) for key in ('g0', 'g1', 'g2', 'W', 'delta'))
    return g0-g2-delta*(W-g2), g1-g2-delta*(W-g2), delta


def validate_prior(raw, physics, where):
    a, b, delta = physical_coefficients(physics)
    check(encloses(raw['a'], a, a), 'prior_a_enclosure', where)
    check(encloses(raw['b'], b, b), 'prior_b_enclosure', where)
    check(abs(m(raw['service_upper'])-delta) <= TOL, 'prior_service_upper', where)
    if raw['decision'] == 'ALLOW':
        check(a >= mp.mpf('.25') and b >= mp.mpf('.125') and
              (a > mp.mpf('.25') or b > mp.mpf('.125')) and
              delta <= m(physics['epsilon']), 'prior_allow_sufficient', where)


def validate_data(raw, observed, physics, method, where):
    required = ('p', 'r') if method == 'two' else OFFERS
    missing = any(observed[d][q][1] == 0 for d in DRIVERS for q in required)
    reason = raw['reason']
    reasons[reason] += 1
    if reason == 'missing_stream':
        check(missing and raw['decision'] == 'ABSTAIN', 'missing_stream', where)
        return
    check(not missing, 'nonmissing_stream', where)
    if missing:
        return
    reference_bands, centers = {}, {}
    for driver in DRIVERS:
        reference_bands[driver], centers[driver] = {}, {}
        for offer in required:
            successes, total = observed[driver][offer]
            low, high, mean = band(successes, total)
            reference_bands[driver][offer] = (low, high)
            centers[driver][offer] = mean
            if 'bands' in raw:
                saved = raw['bands'][driver][offer]
                check(encloses(saved, low, high), 'probability_band_enclosure', where)
    if reason == 'noninterior_probability_band':
        touching = any(low <= TOL or high >= 1-TOL
                       for values in reference_bands.values() for low, high in values.values())
        check(touching and raw['decision'] == 'ABSTAIN', 'noninterior_reason', where)
        return
    if reason == 'empty_or_unresolved_outer':
        check(raw['decision'] == 'ABSTAIN', 'empty_abstention', where)
        return

    # Reconstruct from stored outward probability bounds when available; the
    # center-witness-abstention record has only counts and theta intervals.
    source = ({d: {q: tuple(map(m, raw['bands'][d][q])) for q in required} for d in DRIVERS}
              if 'bands' in raw else reference_bands)
    outer = {}
    for driver in DRIVERS:
        outer[driver] = theta_bounds(source[driver], method)
        if outer[driver] is None:
            check(False, 'reconstructed_outer_empty', where)
            return
        check(encloses(raw['theta_outer'][driver], *outer[driver]), 'theta_outer_enclosure', where)

    if reason == 'central_witness_not_verified':
        check(raw['decision'] == 'ABSTAIN', 'witness_abstention', where)
        return

    for driver in DRIVERS:
        values = witness_values(centers[driver], method)
        if values is None:
            check(False, 'witness_positive_lambda', where)
            return
        check(0 <= values['theta'] <= mp.mpf('.25') and mp.mpf('.05') <= values['tau'] <= mp.mpf('.4'),
              'witness_prior_domain', where)
        for field, value in values.items():
            check(encloses(raw['witness'][driver][field], value, value), 'witness_'+field, where)

    a, b, delta = physical_coefficients(physics)
    check(encloses(raw['a'], a, a), 'a_enclosure', where)
    check(encloses(raw['b'], b, b), 'b_enclosure', where)
    p_l, p_u = source['A']['p']
    r_l, r_u = source['B']['r']
    ta_lo, ta_hi = map(m, raw['theta_outer']['A'])
    tb_lo, tb_hi = map(m, raw['theta_outer']['B'])
    def gain(p, r, ta, tb):
        return p*(a-ta)+(1-p)*r*(b-tb/2)
    minimum = min(gain(p, r, ta_hi, tb_hi) for p in (p_l, p_u) for r in (r_l, r_u))
    maximum = max(gain(p, r, ta_lo, tb_lo) for p in (p_l, p_u) for r in (r_l, r_u))
    check(encloses(raw['benefit_interval'], minimum, maximum), 'benefit_rectangle_enclosure', where)
    service = delta*(p_u+(1-p_u)*r_u)
    check(m(raw['candidate_service_upper'])+TOL >= service, 'candidate_service_enclosure', where)
    check(m(raw['baseline_service_upper']) == 0, 'baseline_service', where)
    lo, upper_service = m(raw['benefit_interval'][0]), m(raw['candidate_service_upper'])
    epsilon = m(physics['epsilon'])
    if reason == 'outward_bounds':
        check(raw['decision'] == 'ALLOW' and lo > 0 and upper_service <= epsilon, 'allow_conditions', where)
    elif reason == 'benefit_not_positive':
        check(raw['decision'] == 'ABSTAIN' and lo <= 0, 'benefit_abstention', where)
    elif reason == 'service_not_certified':
        check(raw['decision'] == 'ABSTAIN' and lo > 0 and upper_service > epsilon, 'service_abstention', where)
    else:
        check(False, 'unexpected_reason', where)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('checkpoints', type=Path)
    args = parser.parse_args()
    latches, last_checkpoint = {}, {}
    with args.checkpoints.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            tested['rows'] += 1
            physics = row['world_evaluator_only']['physics']
            group, pair, checkpoint = row['group'], row['pair'], row['checkpoint']
            pair_id = (group, pair)
            check(checkpoint > last_checkpoint.get(pair_id, 0), 'checkpoint_order', [group, pair, checkpoint])
            last_checkpoint[pair_id] = checkpoint
            validate_prior(row['methods']['prior']['raw'], physics, [group, pair, checkpoint, 'prior'])
            for schedule in SCHEDULES:
                for method in METHODS:
                    name = schedule+'_'+method
                    saved = row['methods'][name]
                    where = [group, pair, checkpoint, name]
                    validate_data(saved['raw'], row['counts'][schedule], physics, method, where)
                    identifier = (group, pair, name)
                    if saved['raw']['decision'] == 'ALLOW' and identifier not in latches:
                        latches[identifier] = checkpoint
                    check(saved['first_crossing'] == latches.get(identifier) and
                          saved['certified'] == (identifier in latches), 'latch_consistency', where)
                    tested['gate_outputs'] += 1
    print(json.dumps({'precision_decimal_digits': mp.mp.dps, 'tolerance': str(TOL),
                      'rows': tested['rows'], 'gate_outputs': tested['gate_outputs'],
                      'tested': dict(tested), 'reasons': dict(reasons),
                      'failures': dict(failures), 'examples': examples}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
