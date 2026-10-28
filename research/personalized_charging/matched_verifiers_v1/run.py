"""Draft prospective matched-verifier experiment; no execution on import."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import multiprocessing
import os
import platform
import signal
import sys
import time
import traceback
from fractions import Fraction
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from personalized_charging.sequential_identification_v1.certificate import PProbeCertificate
from personalized_charging.sequential_identification_v1.physical import simulate_episode
from personalized_charging.continuous_certificate_exploratory_v1.comparator import (
    evaluate as continuous_evaluate, prospective_mixture,
)
from personalized_charging.continuous_certificate_exploratory_v1.proof_replay import replay

ROOT = Path(__file__).resolve().parents[2]
MASTER_SEED, BOOTSTRAP_SEED = 80327941, 80327942
DRIVERS, COLLECTION, DEPLOYMENT = 60, 64, 32
CHECKPOINTS = (16, 32, 48, 64)
NODE_CAP, CALL_SECONDS, WALL_SECONDS, BOOTSTRAPS = 100, 3.0, 900.0, 2000
MARGIN = float(Fraction(161, 41100))
COLLECTORS, GATES = ('p_only', 'alternating'), ('p_only', 'continuous')
GROUPS = (
    ('easy', (0., .02), (.05, .08), '0.005', False),
    ('low_information', (0., .035), (.2, .4), '0.005', False),
    ('mixed', (.055, .25), (.05, .4), '0.005', False),
    ('tight', (0., .1), (.05, .2), '0.0045', False),
    ('misspecified', (.11, .2), (.05, .2), '0.005', True),
)
REQUIRED = tuple(sorted((
    'personalized_charging/matched_verifiers_v1/PROTOCOL.md',
    'personalized_charging/matched_verifiers_v1/run.py',
    'personalized_charging/matched_verifiers_v1/test_run.py',
    'personalized_charging/__init__.py', 'personalized_charging/core.py',
    'personalized_charging/choices.py', 'personalized_charging/observations.py',
    'personalized_charging/profiles.py', 'personalized_charging/reservations.py',
    'personalized_charging/bridge.py',
    'personalized_charging/sequential_identification_v1/physical.py',
    'personalized_charging/sequential_identification_v1/certificate.py',
    'personalized_charging/sequential_identification_v1/test_physical.py',
    'personalized_charging/sequential_identification_v1/test_certificate.py',
    'personalized_charging/continuous_certificate_exploratory_v1/comparator.py',
    'personalized_charging/continuous_certificate_exploratory_v1/proof_replay.py',
    'personalized_charging/continuous_certificate_exploratory_v1/test_comparator.py',
    'personalized_charging/continuous_certificate_exploratory_v1/test_proof_replay.py',
    'personalized_charging/p3d_diagnostic_v1/interval.py',
)))


class InvalidRun(RuntimeError):
    pass


class CallTimeout(Exception):
    pass


class GlobalTimeout(Exception):
    pass


class ExternalStop(Exception):
    pass


def _signal_timeout(_signum, _frame):
    raise CallTimeout('continuous call elapsed limit')


def _global_timeout(_signum, _frame):
    raise GlobalTimeout('whole-run wall limit')


def _external_stop(signum, _frame):
    raise ExternalStop(f'external signal {signum}')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    return {name: digest(ROOT / name) for name in REQUIRED}


def verify_manifest(path):
    """Verify exactly the required prospective sources before generation."""
    raw = Path(path).read_bytes()
    document = json.loads(raw)
    if not isinstance(document, dict) or not isinstance(document.get('sha256'), dict):
        raise ValueError('manifest must contain a sha256 mapping')
    expected = document['sha256']
    if sorted(expected) != list(REQUIRED):
        raise ValueError('manifest must list exactly the required source paths')
    if any(not isinstance(v, str) or len(v) != 64 or
           any(c not in '0123456789abcdef' for c in v) for v in expected.values()):
        raise ValueError('invalid sha256 value')
    current = source_hashes()
    if current != expected:
        raise ValueError('source manifest mismatch')
    return hashlib.sha256(raw).hexdigest(), current


def write_json(path, obj):
    path = Path(path)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def streams(group_index, driver_index, count=COLLECTION + DEPLOYMENT):
    """Separate per-driver/group/event PCG64 namespaces; no prior data read."""
    def rng(code):
        sequence = np.random.SeedSequence([MASTER_SEED, group_index, driver_index, code])
        return np.random.Generator(np.random.PCG64(sequence))
    theta_draw, tau_draw = float(rng(1).random()), float(rng(2).random())
    innovations = np.column_stack([rng(code).random(count) for code in (10, 11, 12)])
    return theta_draw, tau_draw, innovations


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def true_values(theta, tau, shift):
    p = sigmoid((.1 - theta) / tau + shift)
    r = sigmoid((.1 - theta / 2) / tau + shift)
    benefit = p * (.07 - theta) + (1 - p) * r * (.05 - theta / 2)
    unmet = (p + (1 - p) * r) / 200
    return p, r, benefit, unmet


def benefit_band(value):
    if value <= 0:
        return 'nonpositive'
    return 'positive_at_or_below_margin' if value <= MARGIN else 'above_margin'


def _validate_solver_result(result, max_nodes):
    if not isinstance(result, dict) or result.get('decision') not in ('ALLOW', 'ABSTAIN'):
        raise InvalidRun('invalid continuous result')
    nodes = result.get('nodes')
    if type(nodes) is not int or not 0 <= nodes <= max_nodes:
        raise InvalidRun('invalid continuous node count')
    if result['decision'] == 'ALLOW':
        if result.get('reason') != 'outward_bounds' or not isinstance(result.get('proof'), dict):
            raise InvalidRun('invalid ALLOW schema')
        return
    reason = result.get('reason')
    known = ('node_limit', 'precision_limit', 'no_strict_witness',
             'nonpositive_benefit_witness', 'service_violation_witness',
             'arithmetic_failure', 'no_retained_boxes')
    if reason not in known:
        raise InvalidRun('unknown continuous abstention')
    if reason in ('node_limit', 'precision_limit', 'no_retained_boxes') and nodes < 1:
        raise InvalidRun('invalid node count for search outcome')
    if reason == 'no_strict_witness' and nodes != 0:
        raise InvalidRun('invalid no-witness node count')
    if reason in ('nonpositive_benefit_witness', 'service_violation_witness'):
        witness = result.get('witness')
        if not isinstance(witness, (tuple, list)) or len(witness) != 2 or any(
                not isinstance(x, str) for x in witness):
            raise InvalidRun('malformed alleged witness')
        try:
            theta, tau = map(Decimal, witness)
            valid = (theta.is_finite() and tau.is_finite() and
                     Decimal('0') <= theta <= Decimal('.25') and Decimal('.05') <= tau <= Decimal('.4'))
        except (InvalidOperation, ValueError):
            valid = False
        if not valid:
            raise InvalidRun('alleged witness outside prior')


def continuous_call(history, epsilon, *, max_nodes=NODE_CAP, seconds=CALL_SECONDS,
                    solver=continuous_evaluate, checker=replay):
    """Apply a wall cap to solver and replay; preserve any produced ALLOW tree."""
    mixture = prospective_mixture()
    started = time.monotonic()
    previous = signal.getsignal(signal.SIGALRM)
    if signal.getitimer(signal.ITIMER_REAL)[0] != 0:
        raise InvalidRun('continuous call must have its own timer')
    result, replay_status = None, None
    signal.signal(signal.SIGALRM, _signal_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        result = solver(history, mixture=mixture, epsilon=epsilon, max_nodes=max_nodes)
        try:
            _validate_solver_result(result, max_nodes)
        except InvalidRun as exc:
            return {'outcome': 'invalid_solver', 'result': result,
                    'replay': {'valid': False, 'detail': str(exc)},
                    'elapsed': time.monotonic() - started}
        if result.get('decision') == 'ALLOW':
            try:
                valid, detail = checker(result, history=history, mixture=mixture,
                                        epsilon=epsilon, max_nodes=max_nodes)
            except CallTimeout:
                raise
            except Exception as exc:
                return {'outcome': 'invalid_replay', 'result': result,
                        'replay': {'valid': False, 'detail': f'{type(exc).__name__}: {exc}'},
                        'elapsed': time.monotonic() - started}
            replay_status = {'valid': bool(valid), 'detail': str(detail)}
            if not valid:
                return {'outcome': 'invalid_replay', 'result': result, 'replay': replay_status,
                        'elapsed': time.monotonic() - started}
        elif result.get('reason') in ('arithmetic_failure', 'no_retained_boxes'):
            return {'outcome': 'invalid_solver', 'result': result, 'replay': None,
                    'elapsed': time.monotonic() - started}
    except CallTimeout:
        return {'outcome': 'elapsed_limit', 'result': result,
                'replay': replay_status or {'valid': None, 'detail': 'timeout'},
                'elapsed': time.monotonic() - started}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    elapsed = time.monotonic() - started
    if elapsed >= seconds:
        return {'outcome': 'elapsed_limit', 'result': result, 'replay': replay_status,
                'elapsed': elapsed}
    reason = result['reason']
    if reason in ('nonpositive_benefit_witness', 'service_violation_witness'):
        reason = 'unverified_' + reason
    return {'outcome': 'allow' if result['decision'] == 'ALLOW' else reason,
            'result': result, 'replay': replay_status, 'elapsed': elapsed}


def _proof_artifact(outdir, group, driver, collector, checkpoint, call):
    result = call.get('result')
    if not result or result.get('decision') != 'ALLOW':
        return None
    name = f'{group}_{driver:03d}_{collector}_{checkpoint:03d}.json'
    path = outdir / 'proofs' / name
    write_json(path, {'result': result, 'replay': call['replay'], 'outcome': call['outcome']})
    return str(path.relative_to(outdir))


def simulate_unit(group_name, driver, theta, tau, epsilon, shifted, innovations, *,
                  collection=COLLECTION, deployment=DEPLOYMENT, checkpoints=CHECKPOINTS,
                  call=continuous_call, proof_writer=None, event_writer=None):
    """Generate matched histories and paired ledgers for one driver/world."""
    if innovations.shape != (collection + deployment, 3):
        raise ValueError('wrong innovation shape')
    if not checkpoints or tuple(sorted(set(checkpoints))) != tuple(checkpoints) or checkpoints[-1] != collection:
        raise ValueError('checkpoints must be unique, increasing and end at collection')
    shift = 2.0 if shifted else 0.0
    p, r, benefit, service = true_values(theta, tau, shift)
    eligible = benefit > 0 and service <= float(epsilon)

    def episode(policy, index):
        up, ur, urgent = map(float, innovations[index])
        return simulate_episode(policy, float(theta), float(tau), up, ur, urgent,
                                p_response=p, r_response=r)

    def emit_episode(phase, collector, gate, policy, index, value):
        if event_writer is None:
            return
        event_writer({'kind': 'episode', 'group': group_name, 'driver': driver,
                      'phase': phase, 'collector': collector, 'gate': gate,
                      'policy': policy, 'episode_index': index,
                      'procurement_cost': value.procurement_cost,
                      'delay_loss_normalized': value.delay_loss,
                      'unmet_penalty': value.unmet_penalty, 'loss_normalized': value.loss,
                      'unmet_kwh': value.unmet_kwh,
                      'events': [{'request': e.request, 'offer': e.offer,
                                  'accepted': e.accepted, 'assigned_slot': e.assigned_slot,
                                  'occupied_after': e.occupied_after} for e in value.events]})

    if event_writer is not None:
        for i, (up, ur, urgent) in enumerate(innovations):
            event_writer({'kind': 'innovation', 'group': group_name, 'driver': driver,
                          'episode_index': i, 'phase': 'collection' if i < collection else 'deployment',
                          'p_uniform': float(up), 'r_uniform': float(ur), 'urgent_uniform': float(urgent)})

    defaults = [episode('baseline', i) for i in range(collection + deployment)]
    candidates = [episode('candidate', i) for i in range(collection, collection + deployment)]
    for i, value in enumerate(defaults):
        emit_episode('paired_default', None, None, 'baseline', i, value)
    for i, value in enumerate(candidates, start=collection):
        emit_episode('paired_candidate', None, None, 'candidate', i, value)
    records = []
    for collector in COLLECTORS:
        history, actual_collection, traces = [], [], []
        exact = PProbeCertificate()
        crossed = {gate: None for gate in GATES}
        for i in range(collection):
            offer = 'p' if collector == 'p_only' or i % 2 == 0 else 'r'
            observed = episode('collect_' + offer, i)
            emit_episode('collection', collector, None, 'collect_' + offer, i, observed)
            feedback = [(event.offer, event.accepted) for event in observed.events if event.offer is not None]
            if len(feedback) != 1 or feedback[0][0] != offer or type(feedback[0][1]) is not bool:
                raise InvalidRun('invalid physical feedback')
            event = feedback[0]
            history.append(event)
            exact.observe(*event)
            actual_collection.append(observed)
            if i + 1 not in checkpoints:
                continue
            exact_start = time.monotonic()
            exact_decision = exact.evaluate(Fraction(epsilon)) if crossed['p_only'] is None else None
            exact_time = time.monotonic() - exact_start
            if exact_decision is not None and exact_decision.certified:
                crossed['p_only'] = i + 1
            exact_status = ('latched' if exact_decision is None else
                            'allow' if exact_decision.certified else
                            'service_bound' if not exact_decision.service_sufficient else 'below_threshold')
            if crossed['continuous'] is None:
                value = call(tuple(history), epsilon)
                if not isinstance(value, dict) or 'outcome' not in value or 'elapsed' not in value:
                    raise InvalidRun('malformed continuous call')
                outcomes = ('allow', 'elapsed_limit', 'node_limit', 'precision_limit',
                            'no_strict_witness', 'unverified_nonpositive_benefit_witness',
                            'unverified_service_violation_witness', 'invalid_replay', 'invalid_solver')
                if (value['outcome'] not in outcomes or isinstance(value['elapsed'], bool) or
                        not isinstance(value['elapsed'], (int, float)) or
                        not math.isfinite(value['elapsed']) or value['elapsed'] < 0):
                    raise InvalidRun('invalid continuous outcome or elapsed time')
                artifact = proof_writer(group_name, driver, collector, i + 1, value) if proof_writer else None
                if value['outcome'] in ('invalid_replay', 'invalid_solver'):
                    raise InvalidRun('continuous proof or arithmetic failed')
                if value['outcome'] == 'allow':
                    if not value.get('result') or not value.get('replay', {}).get('valid'):
                        raise InvalidRun('ALLOW without replay')
                    crossed['continuous'] = i + 1
                result = value.get('result')
                nodes = result.get('nodes') if result else None
                cont = {'status': value['outcome'], 'elapsed_seconds': value['elapsed'],
                        'created_nodes': nodes, 'proof': artifact}
            else:
                cont = {'status': 'latched', 'elapsed_seconds': 0., 'created_nodes': None, 'proof': None}
            traces.append({'checkpoint': i + 1, 'p_only_status': exact_status,
                           'p_only_elapsed_seconds': exact_time, 'continuous': cont})

        collection_gain = sum(defaults[i].loss - actual_collection[i].loss for i in range(collection))
        collection_unmet = sum(x.unmet_kwh for x in actual_collection)
        expected_collection_unmet = sum((p if offer == 'p' else r) / 200 for offer, _ in history)
        for gate in GATES:
            crossing = crossed[gate]
            selected = candidates if crossing is not None else defaults[collection:]
            for i, value in enumerate(selected, start=collection):
                emit_episode('deployment', collector, gate,
                             'candidate' if crossing is not None else 'baseline', i, value)
            deploy_gain = sum(defaults[collection + i].loss - selected[i].loss for i in range(deployment))
            deploy_unmet = sum(x.unmet_kwh for x in selected)
            stop_index = crossing if crossing is not None else collection
            stop_gain = sum(defaults[i].loss - actual_collection[i].loss for i in range(stop_index))
            records.append({
                'group': group_name, 'driver': driver, 'collector': collector, 'gate': gate,
                'theta': theta, 'tau': tau, 'actual_p': p, 'actual_r': r,
                'actual_B': benefit, 'actual_U': service, 'epsilon': epsilon, 'shifted': shifted,
                'benefit_band': benefit_band(benefit), 'service_feasible': service <= float(epsilon),
                'truth_eligible': eligible, 'history': history, 'checkpoints': traces,
                'first_crossing': crossing, 'certified': crossing is not None,
                'false_declaration': crossing is not None and not eligible,
                'p_margin_false': gate == 'p_only' and crossing is not None and benefit <= MARGIN,
                'collection_unmet': collection_unmet, 'expected_collection_unmet': expected_collection_unmet,
                'deployment_unmet': deploy_unmet,
                'expected_deployment_unmet': deployment * service if crossing is not None else 0.,
                'collection_advantage': collection_gain, 'deployment_advantage': deploy_gain,
                'lifecycle_advantage': collection_gain + deploy_gain,
                'stop_counterfactual_advantage': stop_gain + deploy_gain,
            })
    return records


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    d = 1 + z*z / total
    c = (p + z*z / (2*total)) / d
    r = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / d
    return [max(0., c-r), min(1., c+r)]


def summarize(records, *, bootstrap_seed=BOOTSTRAP_SEED, n_bootstrap=BOOTSTRAPS):
    """Truth-stratified outcomes and paired driver bootstrap, not a joint test."""
    out = {}
    for gi, (group, *_other) in enumerate(GROUPS):
        group_rows = [row for row in records if row['group'] == group]
        if not group_rows:
            continue
        ids = sorted({row['driver'] for row in group_rows})
        methods = [(collector, gate) for collector in COLLECTORS for gate in GATES]
        lookup = {(row['driver'], row['collector'], row['gate']): row for row in group_rows}
        if len(lookup) != len(group_rows) or any((i, *method) not in lookup for i in ids for method in methods):
            raise InvalidRun('missing or duplicate driver method')
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([bootstrap_seed, gi])))
        samples = rng.integers(0, len(ids), size=(n_bootstrap, len(ids)))
        result = {'n': len(ids), 'methods': {}, 'paired': {}}
        for collector, gate in methods:
            rows = [lookup[(i, collector, gate)] for i in ids]
            strata = {}
            for band in ('nonpositive', 'positive_at_or_below_margin', 'above_margin'):
                for feasible in (True, False):
                    subset = [r for r in rows if r['benefit_band'] == band and r['service_feasible'] == feasible]
                    n, yes = len(subset), sum(r['certified'] for r in subset)
                    bad = sum(r['false_declaration'] for r in subset)
                    strata[f'{band}|service_{feasible}'] = {
                        'n': n, 'certified': yes, 'abstained': n-yes,
                        'false': bad, 'certified_wilson_95': wilson(yes, n),
                        'false_wilson_95': wilson(bad, n),
                    }
            n = len(rows)
            yes = sum(r['certified'] for r in rows)
            invalid = [r for r in rows if not r['truth_eligible']]
            false = sum(r['false_declaration'] for r in invalid)
            means = {field: float(np.mean([r[field] for r in rows])) for field in (
                'collection_unmet', 'expected_collection_unmet', 'deployment_unmet',
                'expected_deployment_unmet', 'collection_advantage', 'deployment_advantage',
                'lifecycle_advantage', 'stop_counterfactual_advantage')}
            statuses = {}
            elapsed, known_nodes = [], []
            for row in rows:
                for entry in row['checkpoints']:
                    value = entry['continuous'] if gate == 'continuous' else None
                    status = value['status'] if value else entry['p_only_status']
                    statuses[status] = statuses.get(status, 0) + 1
                    elapsed.append(value['elapsed_seconds'] if value else entry['p_only_elapsed_seconds'])
                    if value and value['created_nodes'] is not None:
                        known_nodes.append(value['created_nodes'])
            result['methods'][f'{collector}:{gate}'] = {
                'n': n, 'certified': yes, 'abstained': n-yes, 'certified_wilson_95': wilson(yes, n),
                'false_n': false, 'false_null_denominator': len(invalid),
                'false_wilson_95_given_null': wilson(false, len(invalid)),
                'p_margin_false': sum(r['p_margin_false'] for r in rows) if gate == 'p_only' else None,
                'p_margin_null_denominator': sum(r['actual_B'] <= MARGIN for r in rows) if gate == 'p_only' else None,
                'first_crossings': [r['first_crossing'] for r in rows if r['first_crossing'] is not None],
                'strata': strata, 'means': means, 'checkpoint_statuses': statuses,
                'gate_elapsed_seconds_total': sum(elapsed),
                'known_node_counts': known_nodes,
            }
        for first, second in itertools.combinations(methods, 2):
            a = [lookup[(i, *first)] for i in ids]
            b = [lookup[(i, *second)] for i in ids]
            comparisons = {}
            for field in ('certified', 'lifecycle_advantage'):
                diff = np.array([float(x[field]) - float(y[field]) for x, y in zip(a, b)])
                boot = np.mean(diff[samples], axis=1)
                comparisons[field] = {'mean_difference': float(np.mean(diff)),
                                      'bootstrap_95': [float(x) for x in np.quantile(boot, [.025, .975])]}
            result['paired'][f'{first[0]}:{first[1]} minus {second[0]}:{second[1]}'] = comparisons
        out[group] = result
    return out


def _worker(outdir):
    """One catalog attempt, writes partial records; never reads old results."""
    outdir = Path(outdir)
    try:
        all_rows = []
        with (outdir / 'drivers.jsonl').open('x', encoding='utf-8') as stream, \
             (outdir / 'events.jsonl').open('x', encoding='utf-8') as event_stream:
            for gi, (group, theta_range, tau_range, epsilon, shifted) in enumerate(GROUPS):
                for driver in range(DRIVERS):
                    dt, ds, innovations = streams(gi, driver)
                    theta = theta_range[0] + (theta_range[1] - theta_range[0]) * dt
                    tau = tau_range[0] + (tau_range[1] - tau_range[0]) * ds
                    writer = lambda g, d, c, cp, value: _proof_artifact(outdir, g, d, c, cp, value)
                    event_writer = lambda event: event_stream.write(json.dumps(event, sort_keys=True,
                                                                              allow_nan=False) + '\n')
                    rows = simulate_unit(group, driver, theta, tau, epsilon, shifted, innovations,
                                         proof_writer=writer, event_writer=event_writer)
                    for row in rows:
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                    event_stream.flush()
                    os.fsync(event_stream.fileno())
                    all_rows.extend(rows)
        write_json(outdir / 'summary.json', summarize(all_rows))
        write_json(outdir / 'worker_finished.json', {'status': 'finished', 'driver_method_rows': len(all_rows)})
    except BaseException as exc:
        try:
            write_json(outdir / 'worker_failure.json', {'type': type(exc).__name__,
                       'message': str(exc), 'traceback': traceback.format_exc()})
        finally:
            raise


def _artifact_hashes(outdir):
    return {str(path.relative_to(outdir)): digest(path) for path in sorted(outdir.rglob('*'))
            if path.is_file() and path.name not in ('output_hashes.json', 'completed.json', 'incomplete.json')}


def _worker_entry(target, outdir):
    # A supervisor termination must terminate the worker, not run parent cleanup.
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    target(outdir)


def supervise(outdir, manifest_digest, expected_sources, *, target=_worker, seconds=WALL_SECONDS,
              started_at=None):
    """Supervise one worker attempt; partial results never become complete."""
    started = time.monotonic() if started_at is None else started_at
    outdir = Path(outdir)
    outdir.mkdir(exist_ok=False)
    (outdir / 'proofs').mkdir()
    write_json(outdir / 'started.json', {'status': 'incomplete', 'manifest_sha256': manifest_digest,
               'master_seed': MASTER_SEED, 'bootstrap_seed': BOOTSTRAP_SEED,
               'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform(),
               'wall_limit_seconds': seconds})
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    if signal.getitimer(signal.ITIMER_REAL)[0] != 0:
        raise InvalidRun('supervisor timer already active')
    child = multiprocessing.get_context('fork').Process(target=_worker_entry, args=(target, str(outdir)))
    status = 'incomplete'
    try:
        signal.signal(signal.SIGALRM, _global_timeout)
        signal.signal(signal.SIGTERM, _external_stop)
        signal.signal(signal.SIGINT, _external_stop)
        remaining = seconds - (time.monotonic() - started)
        if remaining <= 0:
            raise GlobalTimeout('whole-run wall limit before worker start')
        signal.setitimer(signal.ITIMER_REAL, remaining)
        child.start()
        child.join()
        if child.exitcode != 0 or not (outdir / 'worker_finished.json').is_file():
            raise InvalidRun('worker did not complete successfully')
        if source_hashes() != expected_sources:
            raise InvalidRun('source postcheck failed')
        write_json(outdir / 'output_hashes.json', {'sha256': _artifact_hashes(outdir)})
        write_json(outdir / 'completed.json', {'status': 'complete',
                   'output_hashes_sha256': digest(outdir / 'output_hashes.json'),
                   'manifest_sha256': manifest_digest, 'elapsed_seconds': time.monotonic() - started})
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
        # A signal during receipt creation must not leave a false completion.
        (outdir / 'completed.json').unlink(missing_ok=True)
        write_json(outdir / 'incomplete.json', {'status': 'incomplete', 'reason': str(exc),
                   'elapsed_seconds': time.monotonic() - started})
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
    manifest_digest, expected_sources = verify_manifest(args.manifest)
    return 0 if supervise(args.outdir, manifest_digest, expected_sources,
                          started_at=started) == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
