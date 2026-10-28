"""Draft variable-physics paired study; importing never runs a catalog."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import multiprocessing
import os
import platform
import resource
import signal
import sys
import time
import traceback
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from personalized_charging.three_contrast_confidence_exploratory_v1.gate import probability_band
from personalized_charging.variable_physics_exploratory_v1.gate import (
    coefficients, evaluate as data_evaluate,
)
from personalized_charging.variable_physics_exploratory_v1.prior_gate import evaluate as prior_evaluate

ROOT = Path(__file__).resolve().parents[2]
MASTER_SEED, BOOTSTRAP_SEED = 83269021, 83269022
DRIVERS, DEPLOYMENT, BOOTSTRAPS = 60, 32, 2000
CHECKPOINTS = (16, 64, 256, 1024, 4096, 12288, 100000, 1000000, 3000000)
WALL_SECONDS, ADDRESS_SPACE, MAX_ATTEMPTS = 600., 4 * 1024**3, 10000
OFFERS, METHODS = ('p', 'r', 'third'), ('two', 'three', 'prior', 'default')
CATEGORIES = tuple(itertools.product(range(3), range(2), range(2)))


def physics(g0, g1, g2, delta, W, epsilon):
    return {'g0': g0, 'g1': g1, 'g2': g2, 'delta': delta, 'W': W, 'epsilon': epsilon}


GROUPS = (
    ('prior_positive_1', physics('.8', '.65', '.4', '.005', '20', '.005'), (0., .25), 'standard'),
    ('prior_positive_2', physics('.82', '.70', '.45', '.02', '5', '.02'), (0., .25), 'standard'),
    ('harmful', physics('.568', '.548', '.4', '.005', '20', '.005'), (.15, .25), 'standard'),
    ('near_zero', physics('.61', '.571', '.45', '.02', '5', '.02'), (0., .25), 'near_zero'),
    ('tight', physics('.75', '.65', '.45', '.01', '10', '.0085'), (0., .25), 'standard'),
    ('low_penalty', physics('.51', '.46', '.5', '.02', '.2', '.02'), (0., .12), 'standard'),
    ('A', physics('.61', '.571', '.45', '.02', '5', '.02'), None, 'A'),
    ('B', physics('.61', '.571', '.45', '.02', '5', '.02'), None, 'B'),
    ('A_prime', physics('.61', '.571', '.45', '.02', '5', '.02'), None, 'A_prime'),
)
REQUIRED = tuple(sorted((
    'personalized_charging/variable_sensitivity_study_v1/PROTOCOL.md',
    'personalized_charging/variable_sensitivity_study_v1/run.py',
    'personalized_charging/variable_sensitivity_study_v1/test_run.py',
    'personalized_charging/variable_sensitivity_study_v1/test_joint_independent.py',
    'personalized_charging/__init__.py', 'personalized_charging/core.py',
    'personalized_charging/choices.py', 'personalized_charging/observations.py',
    'personalized_charging/profiles.py', 'personalized_charging/reservations.py',
    'personalized_charging/bridge.py',
    'personalized_charging/variable_physics_exploratory_v1/gate.py',
    'personalized_charging/variable_physics_exploratory_v1/prior_gate.py',
    'personalized_charging/variable_physics_exploratory_v1/physical.py',
    'personalized_charging/variable_physics_exploratory_v1/test_extension.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/gate.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/test_gate.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/gate.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/test_gate.py',
    'personalized_charging/p3d_diagnostic_v1/interval.py',
    'personalized_charging/sequential_identification_v1/physical.py',
    'personalized_charging/sequential_identification_v1/test_physical.py',
)))


class InvalidRun(RuntimeError):
    pass


class GlobalTimeout(Exception):
    pass


class ExternalStop(Exception):
    pass


def _global_timeout(_signum, _frame):
    raise GlobalTimeout('whole-run wall limit')


def _external_stop(signum, _frame):
    raise ExternalStop(f'external signal {signum}')


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(data)
    return sha.hexdigest()


def source_hashes():
    return {name: digest(ROOT / name) for name in REQUIRED}


def verify_manifest(path):
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict) or not isinstance(document.get('sha256'), dict):
        raise ValueError('manifest must contain a sha256 mapping')
    expected = document['sha256']
    if sorted(expected) != list(REQUIRED):
        raise ValueError('manifest must list exactly the required sources')
    if any(not isinstance(v, str) or len(v) != 64 or
           any(c not in '0123456789abcdef' for c in v) for v in expected.values()):
        raise ValueError('invalid sha256 value')
    actual = source_hashes()
    if actual != expected:
        raise ValueError('source manifest mismatch')
    return hashlib.sha256(raw).hexdigest(), actual


def write_json(path, obj):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def rng_for(key):
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(key)))


def _sigmoid(x):
    if x >= 0:
        return 1. / (1. + math.exp(-x))
    e = math.exp(x)
    return e / (1. + e)


def truth(theta, tau, c, physical, extra=0.):
    p, r, q3 = (_sigmoid((.1-theta)/tau+c), _sigmoid((.1-theta/2)/tau+c),
                 _sigmoid((.2-theta)/tau+c+extra))
    g0, g1, g2, d, W = (float(physical[key]) for key in ('g0', 'g1', 'g2', 'delta', 'W'))
    a, b = g0-g2-d*(W-g2), g1-g2-d*(W-g2)
    benefit = p*(a-theta)+(1-p)*r*(b-theta/2)
    unmet = d*(p+(1-p)*r)
    return {'p': p, 'r': r, 'third': q3, 'a': a, 'b': b, 'benefit': benefit, 'unmet': unmet}


def sample_world(group_index, driver, *, max_attempts=MAX_ATTEMPTS):
    """Only near_zero uses bounded truth-dependent rejection sampling."""
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError('invalid rejection limit')
    name, physical, theta_range, mode = GROUPS[group_index]
    if mode in ('A', 'B', 'A_prime'):
        theta, tau, c = ((2/35, 1/7, 0.) if mode == 'B' else (.08, .2, .2))
        values = truth(theta, tau, c, physical, .2 if mode == 'A_prime' else 0.)
        # Preserve mathematically identical logits across fixed A/B/A-prime.
        values.update(p=_sigmoid(.3), r=_sigmoid(.5), third=_sigmoid(.8 if mode == 'A' else 1.))
        p, r, a, b = values['p'], values['r'], values['a'], values['b']
        values['benefit'] = p*(a-theta)+(1-p)*r*(b-theta/2)
        values['unmet'] = float(physical['delta'])*(p+(1-p)*r)
        return {'name': name, 'theta': theta, 'tau': tau, 'c': c, 'physics': physical,
                'mode': mode, 'selection_attempt': None, 'parameter_keys': None, **values}
    for attempt in range(max_attempts if mode == 'near_zero' else 1):
        keys = [[MASTER_SEED, 0, group_index, driver, attempt, j] for j in range(3)]
        theta = float(rng_for(keys[0]).uniform(*theta_range))
        tau = float(rng_for(keys[1]).uniform(.08, .3))
        c = float(rng_for(keys[2]).uniform(-.2, .2))
        values = truth(theta, tau, c, physical)
        if mode != 'near_zero' or abs(values['benefit']) <= .002:
            return {'name': name, 'theta': theta, 'tau': tau, 'c': c, 'physics': physical,
                    'mode': mode, 'selection_attempt': attempt+1, 'parameter_keys': keys, **values}
    raise InvalidRun('near-zero rejection selection exceeded its registered limit')


def periodic_counts(start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start <= end:
        raise ValueError('invalid episode range')
    return {offer: (end+2-j)//3-(start+2-j)//3 for j, offer in enumerate(OFFERS)}


def joint_probabilities(p, r, q3, delta):
    """Three shared-first-uniform states crossed with r and urgent bits."""
    if not all(math.isfinite(x) for x in (p, r, q3, delta)) or not (
            0 <= p < q3 <= 1 and 0 <= r <= 1 and 0 <= delta <= 1):
        raise InvalidRun('invalid joint probabilities or p>=q3')
    first = (p, q3-p, 1-q3)
    probabilities = [first[f] * (r if rb else 1-r) * (delta if urgent else 1-delta)
                     for f, rb, urgent in CATEGORIES]
    total = math.fsum(probabilities)
    if any(x < 0 or not math.isfinite(x) for x in probabilities) or abs(total-1.) > 1e-12:
        raise InvalidRun('invalid 12-category distribution')
    return [x/total for x in probabilities]


def joint_block(group_index, driver, block_index, offer_index, m, world, *, deployment=False):
    """One independently keyed aggregate preserving common potential outcomes."""
    if type(m) is not int or m < 0:
        raise ValueError('invalid block size')
    key = [MASTER_SEED, 2 if deployment else 1, group_index, driver, block_index, offer_index]
    probabilities = joint_probabilities(world['p'], world['r'], world['third'], float(world['physics']['delta']))
    cells = [int(x) for x in rng_for(key).multinomial(m, probabilities)]
    if len(cells) != 12 or any(x < 0 for x in cells) or sum(cells) != m:
        raise InvalidRun('invalid joint block')
    return {'m': m, 'stream_key': key, 'joint_counts_evaluator_only': cells}


def block_ledger(cells, offer, world):
    """Compute observable offer stats and paired candidate potential ledger."""
    if offer not in OFFERS or len(cells) != 12 or any(type(x) is not int or x < 0 for x in cells):
        raise ValueError('invalid category cells')
    physical = world['physics']
    g0, g1, g2, delta, W = (float(physical[key]) for key in ('g0', 'g1', 'g2', 'delta', 'W'))
    theta = world['theta']
    m = sum(cells)
    ledger = {'m': m, 'accepted': 0, 'blocked_urgent': 0, 'served_urgent': 0,
              'urgent_arrivals': 0, 'collection_advantage': 0., 'collection_delay': 0.,
              'candidate_advantage': 0., 'candidate_unmet': 0, 'candidate_delay': 0.}
    for count, (first, rb, urgent) in zip(cells, CATEGORIES):
        accept_p, accept_third = first == 0, first != 2
        selected = {'p': accept_p, 'r': bool(rb), 'third': accept_third}[offer]
        cand_first = accept_p
        cand_second = not cand_first and bool(rb)
        candidate_occupied = cand_first or cand_second
        q_delay = .5 if offer == 'r' else 1.
        q_saving = g1-g2 if offer == 'r' else g0-g2
        candidate_saving = ((g0-g2-theta) if cand_first else
                            (g1-g2-theta/2) if cand_second else 0.)
        ledger['accepted'] += count*selected
        ledger['blocked_urgent'] += count*selected*urgent
        ledger['served_urgent'] += count*(not selected)*urgent
        ledger['urgent_arrivals'] += count*urgent
        ledger['collection_advantage'] += count*(int(selected)*(q_saving-theta*q_delay)-
                                                  (W-g2)*int(selected)*urgent)
        ledger['collection_delay'] += count*int(selected)*theta*q_delay
        ledger['candidate_advantage'] += count*(candidate_saving-(W-g2)*int(candidate_occupied)*urgent)
        ledger['candidate_unmet'] += count*int(candidate_occupied)*urgent
        ledger['candidate_delay'] += count*theta*(int(cand_first)+int(cand_second)/2)
    ledger['baseline_cost_normalized'] = m*(g0+g1)+g2*ledger['urgent_arrivals']
    ledger['collection_cost_normalized'] = ledger['baseline_cost_normalized']-ledger['collection_advantage']
    ledger['candidate_cost_normalized'] = ledger['baseline_cost_normalized']-ledger['candidate_advantage']
    ledger['collection_expected_unmet'] = m*delta*world[offer]
    ledger['candidate_expected_unmet'] = m*world['unmet']
    if not all(math.isfinite(v) for v in ledger.values()):
        raise InvalidRun('nonfinite ledger')
    return ledger


def _physical_coefficients(physical):
    return coefficients(*(Decimal(physical[key]) for key in ('g0', 'g1', 'g2', 'delta', 'W')))


def _valid_data_gate(result, method, physical, expected_bands):
    if not isinstance(result, dict) or result.get('decision') not in ('ALLOW', 'ABSTAIN'):
        raise InvalidRun('malformed data-gate output')
    reason = result.get('reason')
    if reason in ('invalid_physics', 'arithmetic_or_inference_failure'):
        raise InvalidRun('failed data-gate arithmetic')
    if reason == 'inference_unresolved':
        if result['decision'] != 'ABSTAIN' or result.get('inference_reason') not in ('noninterior_probability_band', 'empty_outer',
                'empty_or_nonpositive_outer', 'central_witness_not_verified'):
            raise InvalidRun('invalid underlying inference')
        return
    if reason not in ('outward_bounds', 'benefit_not_positive', 'service_not_certified'):
        raise InvalidRun('invalid data-gate reason')
    try:
        expected = {k: expected_bands[k] for k in (('p', 'r') if method == 'two' else OFFERS)}
        witness = result['central_witness']
        required_witness = {'theta_over_tau', 'theta', 'tau', 'common_shift'}
        if method == 'three':
            required_witness.add('lambda')
        if result['bands'] != expected or not isinstance(witness, dict) or set(witness) != required_witness:
            raise InvalidRun('data-gate witness or common bands mismatch')
        for interval in witness.values():
            if not isinstance(interval, list) or len(interval) != 2:
                raise InvalidRun('malformed witness interval')
            left, right = map(Decimal, interval)
            if not left.is_finite() or not right.is_finite() or left > right:
                raise InvalidRun('malformed witness interval')
        witness_theta = list(map(Decimal, witness['theta']))
        witness_tau = list(map(Decimal, witness['tau']))
        if not (0 <= witness_theta[0] <= witness_theta[1] <= Decimal('.25') and
                Decimal('.05') <= witness_tau[0] <= witness_tau[1] <= Decimal('.4')):
            raise InvalidRun('witness outside prior')
        expected_a, expected_b = _physical_coefficients(physical)
        if result['a'] != expected_a.json() or result['b'] != expected_b.json():
            raise InvalidRun('data-gate physical coefficient mismatch')
        lo, hi = map(Decimal, result['benefit_interval'])
        ulo = Decimal(result['candidate_service_upper'])
        th_lo, th_hi = map(Decimal, result['theta_outer'])
        if (not all(x.is_finite() for x in (lo, hi, ulo, th_lo, th_hi)) or lo > hi or
                not 0 <= th_lo <= th_hi <= Decimal('.25') or not 0 <= ulo <= Decimal(physical['delta']) or
                Decimal(result['baseline_service_upper']) != 0):
            raise InvalidRun('invalid numerical gate enclosure')
        epsilon = Decimal(physical['epsilon'])
        if result['decision'] == 'ALLOW' and not (reason == 'outward_bounds' and lo > 0 and ulo <= epsilon):
            raise InvalidRun('invalid favorable gate decision')
        if result['decision'] == 'ABSTAIN' and reason == 'outward_bounds':
            raise InvalidRun('inconsistent data-gate reason')
        if result['decision'] == 'ABSTAIN' and ((reason == 'benefit_not_positive' and lo > 0) or
                (reason == 'service_not_certified' and not (lo > 0 and ulo > epsilon))):
            raise InvalidRun('inconsistent data-gate abstention')
    except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
        raise InvalidRun('malformed data-gate bounds') from exc


def _valid_prior(result, physical):
    if not isinstance(result, dict) or result.get('decision') not in ('ALLOW', 'ABSTAIN'):
        raise InvalidRun('malformed prior rule')
    reason = result.get('reason')
    if reason == 'invalid_or_arithmetic_failure':
        raise InvalidRun('failed prior arithmetic')
    if reason not in ('prior_pointwise_positive', 'prior_not_certified', 'service_not_certified'):
        raise InvalidRun('unknown prior reason')
    try:
        a, b = Decimal(result['a'][0]), Decimal(result['b'][0])
        service = Decimal(result['service_upper'])
        expected_a, expected_b = _physical_coefficients(physical)
        if result['a'] != expected_a.json() or result['b'] != expected_b.json():
            raise InvalidRun('prior physical coefficient mismatch')
        if not all(x.is_finite() for x in (a, b, service)) or service != Decimal(physical['delta']):
            raise InvalidRun('invalid prior bounds')
        if result['decision'] == 'ALLOW' and not (
                reason == 'prior_pointwise_positive' and a >= Decimal('.25') and b >= Decimal('.125') and
                (a > Decimal('.25') or b > Decimal('.125')) and service <= Decimal(physical['epsilon'])):
            raise InvalidRun('invalid prior favorable decision')
        if result['decision'] == 'ABSTAIN' and reason == 'prior_pointwise_positive':
            raise InvalidRun('inconsistent prior reason')
        enough = a >= Decimal('.25') and b >= Decimal('.125') and (a > Decimal('.25') or b > Decimal('.125'))
        if result['decision'] == 'ABSTAIN' and (
                (reason == 'service_not_certified' and service <= Decimal(physical['epsilon'])) or
                (reason == 'prior_not_certified' and
                 (service > Decimal(physical['epsilon']) or enough))):
            raise InvalidRun('inconsistent prior abstention')
    except (KeyError, TypeError, ValueError, InvalidOperation, IndexError) as exc:
        raise InvalidRun('malformed prior bounds') from exc


def _empty_sums():
    return {'m': 0, 'baseline_cost_normalized': 0., 'collection_advantage': 0., 'collection_delay': 0.,
            'collection_unmet': 0, 'collection_expected_unmet': 0., 'candidate_advantage': 0.,
            'candidate_delay': 0., 'candidate_unmet': 0, 'candidate_expected_unmet': 0., 'urgent_arrivals': 0}


def _accumulate(sums, ledger):
    sums['m'] += ledger['m']
    for key in ('baseline_cost_normalized', 'collection_advantage', 'collection_delay',
                'collection_expected_unmet', 'candidate_advantage', 'candidate_delay',
                'candidate_unmet', 'candidate_expected_unmet', 'urgent_arrivals'):
        sums[key] += ledger[key]
    sums['collection_unmet'] += ledger['blocked_urgent']


def driver_records(group_index, driver, *, checkpoints=CHECKPOINTS, deployment_episodes=DEPLOYMENT,
                   data_gate=data_evaluate, prior_gate=prior_evaluate, world_factory=sample_world):
    """Whole-driver unit; only observed counts and known physics enter gates."""
    if (not checkpoints or tuple(sorted(set(checkpoints))) != tuple(checkpoints) or
            any(type(x) is not int or x < 3 for x in checkpoints) or
            type(deployment_episodes) is not int or deployment_episodes < 1):
        raise ValueError('invalid schedule')
    world = world_factory(group_index, driver)
    physical = world['physics']
    prior_start = time.monotonic()
    prior = prior_gate(**physical)
    prior_elapsed = time.monotonic()-prior_start
    _valid_prior(prior, physical)
    prior_allowed = prior['decision'] == 'ALLOW'
    cumulative = {key: [0, 0] for key in OFFERS}
    totals = _empty_sums()
    latch = {'two': None, 'three': None}
    snapshots = {'two': None, 'three': None}
    rows = []
    previous = 0
    for ci, checkpoint in enumerate(checkpoints):
        schedule, block = periodic_counts(previous, checkpoint), {}
        for oi, offer in enumerate(OFFERS):
            drawn = joint_block(group_index, driver, ci, oi, schedule[offer], world)
            ledger = block_ledger(drawn['joint_counts_evaluator_only'], offer, world)
            block[offer] = {**drawn, 'ledger': ledger}
            cumulative[offer][0] += ledger['accepted']
            cumulative[offer][1] += ledger['m']
            _accumulate(totals, ledger)
        if totals['m'] != checkpoint or sum(x[1] for x in cumulative.values()) != checkpoint:
            raise InvalidRun('periodic collection count mismatch')
        counts3 = {key: tuple(cumulative[key]) for key in OFFERS}
        try:
            bands = {key: probability_band(*counts3[key])[0].json() for key in OFFERS}
        except (ArithmeticError, ValueError) as exc:
            raise InvalidRun('failed shared input-band calculation') from exc
        raw, elapsed = {}, {}
        for method in ('two', 'three'):
            counts = {key: counts3[key] for key in (('p', 'r') if method == 'two' else OFFERS)}
            start = time.monotonic()
            result = data_gate(counts, method=method, **physical)
            elapsed[method] = time.monotonic()-start
            _valid_data_gate(result, method, physical, bands)
            raw[method] = result
            if result['decision'] == 'ALLOW' and latch[method] is None:
                latch[method], snapshots[method] = checkpoint, dict(totals)
        deploy = joint_block(group_index, driver, ci, 0, deployment_episodes, world, deployment=True)
        deployment = block_ledger(deploy['joint_counts_evaluator_only'], 'p', world)
        truth_eligible = world['benefit'] > 0 and world['unmet'] <= float(physical['epsilon'])
        methods = {}
        for method in ('two', 'three'):
            certified = latch[method] is not None
            dep_gain = deployment['candidate_advantage'] if certified else 0.
            dep_unmet = deployment['candidate_unmet'] if certified else 0
            dep_expected = deployment['candidate_expected_unmet'] if certified else 0.
            dep_delay = deployment['candidate_delay'] if certified else 0.
            snap = snapshots[method]
            stop_gain = (totals['collection_advantage'] if snap is None else
                         snap['collection_advantage'] + totals['candidate_advantage']-snap['candidate_advantage'])
            stop_unmet = (totals['collection_unmet'] if snap is None else
                          snap['collection_unmet'] + totals['candidate_unmet']-snap['candidate_unmet'])
            stop_expected = (totals['collection_expected_unmet'] if snap is None else
                             snap['collection_expected_unmet'] + totals['candidate_expected_unmet']-snap['candidate_expected_unmet'])
            stop_delay = (totals['collection_delay'] if snap is None else
                          snap['collection_delay'] + totals['candidate_delay']-snap['candidate_delay'])
            methods[method] = {'raw': raw[method], 'elapsed_seconds': elapsed[method],
                'first_crossing': latch[method], 'certified': certified,
                'false_declaration': certified and not truth_eligible,
                'collection_advantage': totals['collection_advantage'],
                'collection_cost_normalized': totals['baseline_cost_normalized']-totals['collection_advantage'],
                'collection_delay': totals['collection_delay'],
                'collection_unmet': totals['collection_unmet'],
                'collection_expected_unmet': totals['collection_expected_unmet'],
                'deployment_advantage': dep_gain, 'deployment_unmet': dep_unmet,
                'deployment_cost_normalized': deployment['baseline_cost_normalized']-dep_gain,
                'deployment_delay': dep_delay,
                'deployment_expected_unmet': dep_expected,
                'lifecycle_advantage': totals['collection_advantage']+dep_gain,
                'lifecycle_cost_normalized': totals['baseline_cost_normalized']+
                    deployment['baseline_cost_normalized']-totals['collection_advantage']-dep_gain,
                'lifecycle_unmet': totals['collection_unmet']+dep_unmet,
                'lifecycle_expected_unmet': totals['collection_expected_unmet']+dep_expected,
                'lifecycle_delay': totals['collection_delay']+dep_delay,
                'stop_lifecycle_advantage': stop_gain+dep_gain,
                'stop_collection_advantage': stop_gain,
                'stop_collection_cost_normalized': totals['baseline_cost_normalized']-stop_gain,
                'stop_collection_unmet': stop_unmet,
                'stop_collection_expected_unmet': stop_expected,
                'stop_collection_delay': stop_delay,
                'stop_lifecycle_cost_normalized': totals['baseline_cost_normalized']+
                    deployment['baseline_cost_normalized']-stop_gain-dep_gain,
                'stop_lifecycle_unmet': stop_unmet+dep_unmet,
                'stop_lifecycle_expected_unmet': stop_expected+dep_expected,
                'stop_lifecycle_delay': stop_delay+dep_delay}
        prior_col_gain = totals['candidate_advantage'] if prior_allowed else 0.
        prior_dep_gain = deployment['candidate_advantage'] if prior_allowed else 0.
        prior_col_unmet = totals['candidate_unmet'] if prior_allowed else 0
        prior_dep_unmet = deployment['candidate_unmet'] if prior_allowed else 0
        prior_col_exp = totals['candidate_expected_unmet'] if prior_allowed else 0.
        prior_dep_exp = deployment['candidate_expected_unmet'] if prior_allowed else 0.
        prior_delay = (totals['candidate_delay']+deployment['candidate_delay']) if prior_allowed else 0.
        methods['prior'] = {'raw': prior, 'elapsed_seconds': prior_elapsed, 'first_crossing': 0 if prior_allowed else None,
            'certified': prior_allowed, 'false_declaration': prior_allowed and not truth_eligible,
            'collection_advantage': prior_col_gain, 'collection_unmet': prior_col_unmet,
            'collection_cost_normalized': totals['baseline_cost_normalized']-prior_col_gain,
            'collection_delay': totals['candidate_delay'] if prior_allowed else 0.,
            'collection_expected_unmet': prior_col_exp, 'deployment_advantage': prior_dep_gain,
            'deployment_cost_normalized': deployment['baseline_cost_normalized']-prior_dep_gain,
            'deployment_delay': deployment['candidate_delay'] if prior_allowed else 0.,
            'deployment_unmet': prior_dep_unmet, 'deployment_expected_unmet': prior_dep_exp,
            'lifecycle_advantage': prior_col_gain+prior_dep_gain,
            'lifecycle_cost_normalized': totals['baseline_cost_normalized']+deployment['baseline_cost_normalized']-
                prior_col_gain-prior_dep_gain,
            'lifecycle_unmet': prior_col_unmet+prior_dep_unmet,
            'lifecycle_expected_unmet': prior_col_exp+prior_dep_exp, 'lifecycle_delay': prior_delay,
            'stop_lifecycle_advantage': prior_col_gain+prior_dep_gain,
            'stop_collection_advantage': prior_col_gain,
            'stop_collection_cost_normalized': totals['baseline_cost_normalized']-prior_col_gain,
            'stop_collection_unmet': prior_col_unmet, 'stop_collection_expected_unmet': prior_col_exp,
            'stop_collection_delay': totals['candidate_delay'] if prior_allowed else 0.,
            'stop_lifecycle_cost_normalized': totals['baseline_cost_normalized']+deployment['baseline_cost_normalized']-
                prior_col_gain-prior_dep_gain,
            'stop_lifecycle_unmet': prior_col_unmet+prior_dep_unmet,
            'stop_lifecycle_expected_unmet': prior_col_exp+prior_dep_exp, 'stop_lifecycle_delay': prior_delay}
        default_cost = totals['baseline_cost_normalized']+deployment['baseline_cost_normalized']
        methods['default'] = {'raw': {'decision': 'ABSTAIN', 'reason': 'default_reference'},
            'elapsed_seconds': 0., 'first_crossing': None, 'certified': False, 'false_declaration': False,
            'collection_advantage': 0., 'collection_unmet': 0, 'collection_expected_unmet': 0.,
            'collection_cost_normalized': totals['baseline_cost_normalized'], 'collection_delay': 0.,
            'deployment_advantage': 0., 'deployment_unmet': 0, 'deployment_expected_unmet': 0.,
            'deployment_cost_normalized': deployment['baseline_cost_normalized'], 'deployment_delay': 0.,
            'lifecycle_advantage': 0., 'lifecycle_cost_normalized': default_cost,
            'lifecycle_unmet': 0, 'lifecycle_expected_unmet': 0., 'lifecycle_delay': 0.,
            'stop_lifecycle_advantage': 0., 'stop_lifecycle_cost_normalized': default_cost,
            'stop_collection_advantage': 0., 'stop_collection_cost_normalized': totals['baseline_cost_normalized'],
            'stop_collection_unmet': 0, 'stop_collection_expected_unmet': 0., 'stop_collection_delay': 0.,
            'stop_lifecycle_unmet': 0, 'stop_lifecycle_expected_unmet': 0., 'stop_lifecycle_delay': 0.}
        rows.append({'group': world['name'], 'group_index': group_index, 'driver': driver,
                     'checkpoint': checkpoint, 'block_start': previous, 'world': world,
                     'block_evaluator_only': block, 'counts': counts3, 'input_bands': bands,
                     'collection_evaluator': dict(totals), 'deployment_evaluator_only': {**deploy, 'ledger': deployment},
                     'methods': methods})
        previous = checkpoint
    return rows


def wilson(successes, total):
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes/total
    den = 1+z*z/total
    center = (p+z*z/(2*total))/den
    radius = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/den
    return [max(0., center-radius), min(1., center+radius)]


def summarize(rows, *, n_bootstrap=BOOTSTRAPS, seed=BOOTSTRAP_SEED):
    result = {}
    for gi, (group, *_rest) in enumerate(GROUPS):
        selected = [r for r in rows if r['group'] == group]
        if not selected:
            continue
        cps = sorted({r['checkpoint'] for r in selected})
        drivers = sorted({r['driver'] for r in selected})
        lookup = {(r['driver'], r['checkpoint']): r for r in selected}
        if len(lookup) != len(selected) or any((d, cp) not in lookup for d in drivers for cp in cps):
            raise InvalidRun('missing or duplicate group/checkpoint driver')
        for ci, checkpoint in enumerate(cps):
            data = [lookup[d, checkpoint] for d in drivers]
            rng = rng_for([seed, gi, ci])
            samples = rng.integers(0, len(data), size=(n_bootstrap, len(data)))
            entry = {'n': len(data), 'methods': {}, 'paired': {},
                     'mean_true_benefit': float(np.mean([r['world']['benefit'] for r in data])),
                     'mean_true_unmet': float(np.mean([r['world']['unmet'] for r in data])),
                     'deployment_epsilon': data[0]['world']['physics']['epsilon'],
                     'collection_expected_unmet_upper': checkpoint*float(data[0]['world']['physics']['delta']),
                     'common_shift_model_violated': group == 'A_prime',
                     'two_band_bound_under_model': '2/60',
                     'shared_data_gate_bound_under_model': None if group == 'A_prime' else '3/60'}
            for method in METHODS:
                yes = sum(r['methods'][method]['certified'] for r in data)
                nulls = [r for r in data if not (r['world']['benefit'] > 0 and
                         r['world']['unmet'] <= float(r['world']['physics']['epsilon']))]
                false = sum(r['methods'][method]['false_declaration'] for r in nulls)
                strata = {}
                for positive in (True, False):
                    for feasible in (True, False):
                        sub = [r for r in data if (r['world']['benefit'] > 0) == positive and
                               (r['world']['unmet'] <= float(r['world']['physics']['epsilon'])) == feasible]
                        n, s = len(sub), sum(r['methods'][method]['certified'] for r in sub)
                        f = sum(r['methods'][method]['false_declaration'] for r in sub)
                        strata[f'benefit_{positive}|service_{feasible}'] = {
                            'n': n, 'certified': s, 'abstained': n-s, 'false': f,
                            'certified_fraction': s/n if n else None,
                            'false_fraction': f/n if n else None,
                            'certified_wilson_95': wilson(s, n), 'false_wilson_95': wilson(f, n)}
                fields = ('collection_advantage', 'collection_cost_normalized', 'collection_delay',
                          'collection_unmet', 'collection_expected_unmet',
                          'deployment_advantage', 'deployment_cost_normalized', 'deployment_delay',
                          'deployment_unmet', 'deployment_expected_unmet',
                          'lifecycle_advantage', 'lifecycle_cost_normalized', 'lifecycle_unmet',
                          'lifecycle_expected_unmet', 'lifecycle_delay', 'stop_lifecycle_advantage',
                          'stop_collection_advantage', 'stop_collection_cost_normalized',
                          'stop_collection_unmet', 'stop_collection_expected_unmet', 'stop_collection_delay',
                          'stop_lifecycle_cost_normalized', 'stop_lifecycle_unmet',
                          'stop_lifecycle_expected_unmet', 'stop_lifecycle_delay')
                reasons = {}
                for row in data:
                    reason = row['methods'][method]['raw']['reason']
                    reasons[reason] = reasons.get(reason, 0)+1
                entry['methods'][method] = {'certified': yes, 'abstained': len(data)-yes,
                    'certified_fraction': yes/len(data), 'certified_wilson_95': wilson(yes, len(data)),
                    'false': false, 'null_denominator': len(nulls),
                    'false_fraction_given_null': false/len(nulls) if nulls else None,
                    'false_wilson_95_given_null': wilson(false, len(nulls)), 'strata': strata,
                    'raw_reasons': reasons,
                    'first_crossings': [r['methods'][method]['first_crossing'] for r in data
                                        if r['methods'][method]['first_crossing'] is not None],
                    'mean_gate_seconds': float(np.mean([r['methods'][method]['elapsed_seconds'] for r in data])),
                    'means': {key: float(np.mean([r['methods'][method][key] for r in data])) for key in fields}}
            for first, second in itertools.combinations(METHODS, 2):
                metrics = {}
                for field in ('certified', 'lifecycle_advantage', 'stop_lifecycle_advantage'):
                    diff = np.array([float(r['methods'][first][field])-float(r['methods'][second][field]) for r in data])
                    means = np.mean(diff[samples], axis=1)
                    metrics[field] = {'mean_difference': float(np.mean(diff)),
                                      'bootstrap_95': [float(x) for x in np.quantile(means, [.025, .975])]}
                entry['paired'][f'{first} minus {second}'] = metrics
            result[f'{group}|{checkpoint}'] = entry
    return result


def enforce_memory_limit():
    soft, hard = resource.getrlimit(resource.RLIMIT_AS)
    cap = min(ADDRESS_SPACE, hard) if hard != resource.RLIM_INFINITY else ADDRESS_SPACE
    if soft != resource.RLIM_INFINITY:
        cap = min(cap, soft)
    if cap <= 0:
        raise InvalidRun('invalid address-space cap')
    try:
        resource.setrlimit(resource.RLIMIT_AS, (cap, hard))
        actual_soft, actual_hard = resource.getrlimit(resource.RLIMIT_AS)
    except (OSError, ValueError) as exc:
        raise InvalidRun('cannot enforce address-space cap') from exc
    if actual_soft == resource.RLIM_INFINITY or not 0 < actual_soft <= ADDRESS_SPACE:
        raise InvalidRun('address-space cap was not enforced')
    return {'address_space_soft_bytes': actual_soft, 'address_space_hard_bytes': actual_hard}


def _worker(outdir):
    outdir = Path(outdir)
    try:
        memory = enforce_memory_limit()
        write_json(outdir/'environment.json', {'python': sys.version, 'numpy': np.__version__,
                   'platform': platform.platform(), **memory})
        all_rows = []
        with (outdir/'checkpoints.jsonl').open('x', encoding='utf-8') as stream:
            for group_index in range(len(GROUPS)):
                for driver in range(DRIVERS):
                    rows = driver_records(group_index, driver)
                    for row in rows:
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                    all_rows.extend(rows)
        write_json(outdir/'summary.json', summarize(all_rows))
        usage = resource.getrusage(resource.RUSAGE_SELF)
        write_json(outdir/'worker_finished.json', {'status': 'finished', 'rows': len(all_rows),
                   'peak_rss_platform_units': usage.ru_maxrss, 'cpu_user_seconds': usage.ru_utime,
                   'cpu_system_seconds': usage.ru_stime})
    except BaseException as exc:
        try:
            write_json(outdir/'worker_failure.json', {'type': type(exc).__name__, 'message': str(exc),
                       'traceback': traceback.format_exc()})
        finally:
            raise


def _worker_entry(target, outdir):
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
    target(outdir)


def _artifact_hashes(outdir):
    return {str(path.relative_to(outdir)): digest(path) for path in sorted(outdir.rglob('*'))
            if path.is_file() and path.name not in ('output_hashes.json', 'completed.json', 'incomplete.json')}


def supervise(outdir, manifest_path, manifest_digest, expected_sources, *, target=_worker,
              seconds=WALL_SECONDS, started_at=None):
    start = time.monotonic() if started_at is None else started_at
    outdir = Path(outdir)
    outdir.mkdir(exist_ok=False)
    write_json(outdir/'started.json', {'status': 'incomplete', 'manifest_sha256': manifest_digest,
               'master_seed': MASTER_SEED, 'bootstrap_seed': BOOTSTRAP_SEED,
               'wall_limit_seconds': seconds, 'address_space_limit_bytes': ADDRESS_SPACE})
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    if signal.getitimer(signal.ITIMER_REAL)[0] != 0:
        raise InvalidRun('supervisor timer already active')
    child = multiprocessing.get_context('fork').Process(target=_worker_entry, args=(target, str(outdir)))
    status = 'incomplete'
    try:
        signal.signal(signal.SIGALRM, _global_timeout)
        signal.signal(signal.SIGTERM, _external_stop)
        signal.signal(signal.SIGINT, _external_stop)
        remaining = seconds-(time.monotonic()-start)
        if remaining <= 0:
            raise GlobalTimeout('whole-run wall limit before worker start')
        signal.setitimer(signal.ITIMER_REAL, remaining)
        # Do not let a signal interrupt fork before the supervisor has a
        # usable child handle; the child unblocks signals on entry.
        old_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM, signal.SIGINT})
        try:
            child.start()
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, old_mask)
        child.join()
        if child.exitcode != 0 or not (outdir/'worker_finished.json').is_file():
            raise InvalidRun('worker did not complete successfully')
        if source_hashes() != expected_sources or digest(manifest_path) != manifest_digest:
            raise InvalidRun('source or manifest postcheck failed')
        write_json(outdir/'output_hashes.json', {'sha256': _artifact_hashes(outdir)})
        write_json(outdir/'completed.json', {'status': 'complete',
                   'output_hashes_sha256': digest(outdir/'output_hashes.json'),
                   'manifest_sha256': manifest_digest, 'elapsed_seconds': time.monotonic()-start})
        status = 'complete'
    except Exception as exc:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if child.is_alive():
            child.terminate()
            child.join(1)
            if child.is_alive():
                child.kill()
                child.join()
        (outdir/'completed.json').unlink(missing_ok=True)
        write_json(outdir/'incomplete.json', {'status': 'incomplete', 'reason': str(exc),
                   'elapsed_seconds': time.monotonic()-start})
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return status


def main():
    started = time.monotonic()
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--outdir', required=True)
    args = parser.parse_args()
    manifest_digest, sources = verify_manifest(args.manifest)
    return 0 if supervise(args.outdir, args.manifest, manifest_digest, sources, started_at=started) == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
