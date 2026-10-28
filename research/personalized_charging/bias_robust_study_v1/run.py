"""Draft aggregate-block bias-robust study. Importing does not run a catalog."""
from __future__ import annotations

import argparse
import hashlib
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

from personalized_charging.sequential_identification_v1.physical import simulate_episode
from personalized_charging.two_contrast_bias_exploratory_v1.gate import evaluate as two_evaluate
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import (
    evaluate as three_evaluate, probability_band,
)

ROOT = Path(__file__).resolve().parents[2]
MASTER_SEED, BOOTSTRAP_SEED = 94613011, 94613012
DRIVERS, DEPLOYMENT, BOOTSTRAPS = 60, 32, 2000
CHECKPOINTS = (16, 64, 256, 1024, 4096, 12288, 100000, 1000000, 3000000)
WALL_SECONDS, ADDRESS_SPACE = 600., 4 * 1024**3
OFFERS, GATES = ('p', 'r', 'third'), ('two', 'three')
GROUPS = (
    ('beneficial', (0., .03), (.08, .18), (-.2, .2), '0.005', False),
    ('harmful', (.15, .25), (.1, .3), (-.2, .2), '0.005', False),
    ('A', (.08, .08), (.2, .2), (.2, .2), '0.005', False),
    ('B', (2/35, 2/35), (1/7, 1/7), (0., 0.), '0.005', False),
    ('tight', (0., .1), (.05, .2), (-.2, .2), '0.0045', False),
    ('A_prime', (.08, .08), (.2, .2), (.2, .2), '0.005', True),
)
REQUIRED = tuple(sorted((
    'personalized_charging/bias_robust_study_v1/PROTOCOL.md',
    'personalized_charging/bias_robust_study_v1/run.py',
    'personalized_charging/bias_robust_study_v1/test_run.py',
    'personalized_charging/bias_robust_study_v1/test_aggregate_independent.py',
    'personalized_charging/__init__.py', 'personalized_charging/core.py',
    'personalized_charging/choices.py', 'personalized_charging/observations.py',
    'personalized_charging/profiles.py', 'personalized_charging/reservations.py',
    'personalized_charging/bridge.py',
    'personalized_charging/sequential_identification_v1/physical.py',
    'personalized_charging/sequential_identification_v1/test_physical.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/gate.py',
    'personalized_charging/three_contrast_confidence_exploratory_v1/test_gate.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/gate.py',
    'personalized_charging/two_contrast_bias_exploratory_v1/test_gate.py',
    'personalized_charging/p3d_diagnostic_v1/interval.py',
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


def model(group_index, driver):
    """Fresh independently keyed parameters; fixed worlds preserve exact logits."""
    name, theta_range, tau_range, c_range, epsilon, shifted = GROUPS[group_index]
    ranges = (theta_range, tau_range, c_range)
    keys = [None if bounds[0] == bounds[1] else [MASTER_SEED, 0, group_index, driver, i]
            for i, bounds in enumerate(ranges)]
    def value(bounds, key):
        return bounds[0] if key is None else float(rng_for(key).uniform(*bounds))
    theta, tau, c = (value(bounds, key) for bounds, key in zip(ranges, keys))
    sigmoid = lambda x: 1. / (1. + math.exp(-x))
    if name in ('A', 'B', 'A_prime'):
        # The mathematical logits are exactly shared despite floating representations.
        p, r = sigmoid(.3), sigmoid(.5)
        third = sigmoid(.8 if name == 'A' else 1.)
    else:
        p = sigmoid((.1 - theta) / tau + c)
        r = sigmoid((.1 - theta / 2) / tau + c)
        third = sigmoid((.2 - theta) / tau + c + (.2 if shifted else 0.))
    benefit = p * (.07 - theta) + (1 - p) * r * (.05 - theta / 2)
    unmet = (p + (1 - p) * r) / 200
    return {'name': name, 'theta': theta, 'tau': tau, 'c': c, 'epsilon': epsilon,
            'shifted': shifted, 'p': p, 'r': r, 'third': third,
            'benefit': benefit, 'unmet': unmet, 'parameter_keys': keys}


def periodic_counts(start, end):
    if type(start) is not int or type(end) is not int or not 0 <= start <= end:
        raise ValueError('invalid episode range')
    return {offer: (end + 2 - j)//3 - (start + 2 - j)//3
            for j, offer in enumerate(OFFERS)}


def ledger(offer, m, accepted, blocked_urgent, served_urgent, theta, probability):
    if (offer not in OFFERS or any(type(x) is not int or x < 0
            for x in (m, accepted, blocked_urgent, served_urgent)) or
            accepted > m or blocked_urgent > accepted or served_urgent > m-accepted or
            not 0 <= probability <= 1):
        raise ValueError('invalid block counts')
    delay_hours = .5 if offer == 'r' else 1.
    procurement_saving = .148 if offer == 'r' else .168
    discount = .2 if offer == 'third' else .1
    return {'m': m, 'accepted': accepted, 'blocked_urgent': blocked_urgent,
            'served_urgent': served_urgent, 'urgent_arrivals': blocked_urgent + served_urgent,
            'realized_unmet': blocked_urgent, 'expected_unmet': .005*m*probability,
            'delay_loss': theta * accepted * delay_hours,
            'focal_retail_savings': discount * accepted,
            'advantage': accepted*(procurement_saving-theta*delay_hours)-19.6*blocked_urgent}


def draw_block(group_index, driver, block_index, offer_index, m, q, theta):
    keys = [[MASTER_SEED, 1, group_index, driver, block_index, offer_index, i] for i in range(3)]
    accepted = int(rng_for(keys[0]).binomial(m, q))
    blocked = int(rng_for(keys[1]).binomial(accepted, .005))
    served = int(rng_for(keys[2]).binomial(m - accepted, .005))
    result = ledger(OFFERS[offer_index], m, accepted, blocked, served, theta, q)
    result['stream_keys'] = keys
    return result


def deploy(group_index, driver, checkpoint_index, world, *, episodes=DEPLOYMENT):
    """Independently keyed 32-episode same-innovation candidate/default pair."""
    keys = [[MASTER_SEED, 2, group_index, driver, checkpoint_index, i] for i in range(3)]
    innovations = [rng_for(key).random(episodes) for key in keys]
    advantage = 0.
    candidate_unmet = 0.
    default_loss = candidate_loss = 0.
    for i in range(episodes):
        args = (float(world['theta']), float(world['tau']), *(float(stream[i]) for stream in innovations))
        default = simulate_episode('baseline', *args, p_response=world['p'], r_response=world['r'])
        candidate = simulate_episode('candidate', *args, p_response=world['p'], r_response=world['r'])
        advantage += default.loss - candidate.loss
        default_loss += default.loss
        candidate_loss += candidate.loss
        candidate_unmet += candidate.unmet_kwh
    return {'stream_keys': keys, 'episodes': episodes, 'candidate_advantage': advantage,
            'candidate_unmet': candidate_unmet, 'default_unmet': 0.,
            'candidate_expected_unmet': episodes*world['unmet'],
            'default_loss_normalized': default_loss, 'candidate_loss_normalized': candidate_loss}


def _validated_gate(result, epsilon, gate, input_bands):
    if not isinstance(result, dict) or result.get('decision') not in ('ALLOW', 'ABSTAIN'):
        raise InvalidRun('malformed gate decision')
    reason = result.get('reason')
    if reason in ('arithmetic_failure', 'invalid_input', 'missing_contrast'):
        raise InvalidRun(f'{gate} gate failed: {reason}')
    if result['decision'] == 'ALLOW':
        try:
            benefit = Decimal(result['benefit_interval'][0])
            benefit_hi = Decimal(result['benefit_interval'][1])
            service = Decimal(result['candidate_service_upper'])
            theta_lo, theta_hi = map(Decimal, result['theta_outer'])
            expected = {key: input_bands[key] for key in (('p', 'r') if gate == 'two' else OFFERS)}
            witness = result['central_witness']
            required_witness = {'theta_over_tau', 'theta', 'tau', 'common_shift'}
            if gate == 'three':
                required_witness.add('lambda')
            if (reason != 'outward_bounds' or not all(x.is_finite() for x in
                    (benefit, benefit_hi, service, theta_lo, theta_hi)) or
                    not 0 < benefit <= benefit_hi or not 0 <= service <= min(Decimal(epsilon), Decimal('.005')) or
                    not 0 <= theta_lo <= theta_hi <= Decimal('.25') or
                    Decimal(result['baseline_service_upper']) != 0 or
                    result.get('bands') != expected or not isinstance(witness, dict) or
                    set(witness) != required_witness):
                raise InvalidRun('invalid ALLOW bounds')
            for interval in witness.values():
                if not isinstance(interval, list) or len(interval) != 2:
                    raise InvalidRun('invalid witness interval')
                lo, hi = map(Decimal, interval)
                if not lo.is_finite() or not hi.is_finite() or lo > hi:
                    raise InvalidRun('invalid witness interval')
            witness_theta = list(map(Decimal, witness['theta']))
            witness_tau = list(map(Decimal, witness['tau']))
            if not (0 <= witness_theta[0] <= witness_theta[1] <= Decimal('.25') and
                    Decimal('.05') <= witness_tau[0] <= witness_tau[1] <= Decimal('.4')):
                raise InvalidRun('witness outside prior')
        except (KeyError, TypeError, ValueError, InvalidOperation, IndexError) as exc:
            raise InvalidRun('malformed ALLOW') from exc
    elif reason not in ('noninterior_probability_band', 'empty_outer',
                        'empty_or_nonpositive_outer', 'central_witness_not_verified',
                        'benefit_not_positive', 'service_not_certified'):
        raise InvalidRun(f'unknown abstention: {reason}')


def driver_records(group_index, driver, *, checkpoints=CHECKPOINTS, deployment_episodes=DEPLOYMENT,
                   two_gate=two_evaluate, three_gate=three_evaluate):
    """One complete fresh unit; only cumulative observed counts enter gates."""
    if (not checkpoints or tuple(sorted(set(checkpoints))) != tuple(checkpoints) or
            any(type(x) is not int or x < 3 for x in checkpoints)):
        raise ValueError('invalid checkpoint schedule')
    world = model(group_index, driver)
    cumulative = {key: [0, 0] for key in OFFERS}
    sums = {'advantage': 0., 'delay_loss': 0., 'focal_retail_savings': 0.,
            'realized_unmet': 0, 'expected_unmet': 0., 'urgent_arrivals': 0}
    latch = {gate: None for gate in GATES}
    stop_snapshot = {gate: None for gate in GATES}
    rows = []
    previous = 0
    for ci, checkpoint in enumerate(checkpoints):
        block = {}
        schedule = periodic_counts(previous, checkpoint)
        for oi, offer in enumerate(OFFERS):
            q = world[offer]
            record = draw_block(group_index, driver, ci, oi, schedule[offer], q, world['theta'])
            block[offer] = record
            cumulative[offer][0] += record['accepted']
            cumulative[offer][1] += record['m']
            for field in sums:
                sums[field] += record[field]
        if sum(value[1] for value in cumulative.values()) != checkpoint:
            raise InvalidRun('periodic collection count mismatch')
        counts3 = {key: tuple(cumulative[key]) for key in OFFERS}
        counts2 = {key: counts3[key] for key in ('p', 'r')}
        try:
            input_bands = {key: probability_band(*counts3[key])[0].json() for key in OFFERS}
        except (ArithmeticError, ValueError) as exc:
            raise InvalidRun('failed input-band calculation') from exc
        results, elapsed = {}, {}
        for gate, function, counts in (('two', two_gate, counts2), ('three', three_gate, counts3)):
            start = time.monotonic()
            result = function(counts, epsilon=world['epsilon'])
            elapsed[gate] = time.monotonic() - start
            _validated_gate(result, world['epsilon'], gate, input_bands)
            results[gate] = result
            if result['decision'] == 'ALLOW' and latch[gate] is None:
                latch[gate] = checkpoint
                stop_snapshot[gate] = dict(sums)
        paired = deploy(group_index, driver, ci, world, episodes=deployment_episodes)
        true_eligible = world['benefit'] > 0 and world['unmet'] <= float(world['epsilon'])
        per_gate = {}
        for gate in GATES:
            certified = latch[gate] is not None
            deployment_gain = paired['candidate_advantage'] if certified else 0.
            deployment_unmet = paired['candidate_unmet'] if certified else 0.
            stop = stop_snapshot[gate] if certified else sums
            per_gate[gate] = {'raw': results[gate], 'elapsed_seconds': elapsed[gate],
                              'first_crossing': latch[gate], 'certified': certified,
                              'false_declaration': certified and not true_eligible,
                              'deployment_advantage': deployment_gain, 'deployment_unmet': deployment_unmet,
                              'expected_deployment_unmet': paired['candidate_expected_unmet'] if certified else 0.,
                              'lifecycle_advantage': sums['advantage'] + deployment_gain,
                              'stop_lifecycle_advantage': stop['advantage'] + deployment_gain,
                              'stop_collection': dict(stop),
                              'stop_collection_unmet': stop['realized_unmet'],
                              'stop_expected_collection_unmet': stop['expected_unmet']}
        rows.append({'group': world['name'], 'group_index': group_index, 'driver': driver,
                     'checkpoint': checkpoint, 'block_start': previous, 'block': block,
                     'world': world, 'counts': counts3, 'input_bands': input_bands,
                     'collection': dict(sums),
                     'deployment_pair': paired, 'gates': per_gate})
        previous = checkpoint
    return rows


def wilson(successes, total):
    if total == 0:
        return None
    z = 1.959963984540054
    p = successes / total
    d = 1 + z*z/total
    c = (p + z*z/(2*total))/d
    r = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return [max(0., c-r), min(1., c+r)]


def summarize(rows, *, n_bootstrap=BOOTSTRAPS, seed=BOOTSTRAP_SEED):
    result = {}
    for gi, (group, *_rest) in enumerate(GROUPS):
        group_rows = [row for row in rows if row['group'] == group]
        if not group_rows:
            continue
        checkpoints = sorted({row['checkpoint'] for row in group_rows})
        drivers = sorted({row['driver'] for row in group_rows})
        lookup = {(r['driver'], r['checkpoint']): r for r in group_rows}
        if len(lookup) != len(group_rows) or any((d, c) not in lookup for d in drivers for c in checkpoints):
            raise InvalidRun('missing or duplicate group/checkpoint driver')
        for ci, checkpoint in enumerate(checkpoints):
            data = [lookup[d, checkpoint] for d in drivers]
            rng = rng_for([seed, gi, ci])
            resamples = rng.integers(0, len(data), size=(n_bootstrap, len(data)))
            entry = {'n': len(data), 'gates': {}, 'paired': {}}
            for gate in GATES:
                certified = sum(row['gates'][gate]['certified'] for row in data)
                nulls = [row for row in data if not (row['world']['benefit'] > 0 and
                         row['world']['unmet'] <= float(row['world']['epsilon']))]
                false = sum(row['gates'][gate]['false_declaration'] for row in nulls)
                strata = {}
                for positive in (True, False):
                    for feasible in (True, False):
                        subset = [row for row in data if (row['world']['benefit'] > 0) == positive and
                                  (row['world']['unmet'] <= float(row['world']['epsilon'])) == feasible]
                        n, yes = len(subset), sum(row['gates'][gate]['certified'] for row in subset)
                        bad = sum(row['gates'][gate]['false_declaration'] for row in subset)
                        strata[f'benefit_{positive}|service_{feasible}'] = {
                            'n': n, 'certified': yes, 'abstained': n-yes, 'false': bad,
                            'certified_fraction': yes/n if n else None,
                            'false_fraction': bad/n if n else None,
                            'certified_wilson_95': wilson(yes, n), 'false_wilson_95': wilson(bad, n)}
                raw_reasons = {}
                for row in data:
                    reason = row['gates'][gate]['raw']['reason']
                    raw_reasons[reason] = raw_reasons.get(reason, 0) + 1
                entry['gates'][gate] = {
                    'certified': certified, 'abstained': len(data)-certified,
                    'certified_fraction': certified/len(data),
                    'abstained_fraction': (len(data)-certified)/len(data),
                    'certified_wilson_95': wilson(certified, len(data)),
                    'false': false, 'null_denominator': len(nulls),
                    'false_fraction_given_null': false/len(nulls) if nulls else None,
                    'false_wilson_95_given_null': wilson(false, len(nulls)),
                    'strata': strata, 'raw_reasons': raw_reasons,
                    'first_crossings': [row['gates'][gate]['first_crossing'] for row in data
                                        if row['gates'][gate]['first_crossing'] is not None],
                    'mean_gate_seconds': float(np.mean([row['gates'][gate]['elapsed_seconds'] for row in data])),
                    'mean_collection_advantage': float(np.mean([row['collection']['advantage'] for row in data])),
                    'mean_accepted_p': float(np.mean([row['counts']['p'][0] for row in data])),
                    'mean_accepted_r': float(np.mean([row['counts']['r'][0] for row in data])),
                    'mean_accepted_third': float(np.mean([row['counts']['third'][0] for row in data])),
                    'mean_collection_delay_loss': float(np.mean([row['collection']['delay_loss'] for row in data])),
                    'mean_focal_retail_savings': float(np.mean([row['collection']['focal_retail_savings'] for row in data])),
                    'mean_collection_urgent_arrivals': float(np.mean([row['collection']['urgent_arrivals'] for row in data])),
                    'mean_collection_unmet': float(np.mean([row['collection']['realized_unmet'] for row in data])),
                    'mean_expected_collection_unmet': float(np.mean([row['collection']['expected_unmet'] for row in data])),
                    'mean_deployment_advantage': float(np.mean([row['gates'][gate]['deployment_advantage'] for row in data])),
                    'mean_deployment_unmet': float(np.mean([row['gates'][gate]['deployment_unmet'] for row in data])),
                    'mean_expected_deployment_unmet': float(np.mean([row['gates'][gate]['expected_deployment_unmet'] for row in data])),
                    'mean_lifecycle_advantage': float(np.mean([row['gates'][gate]['lifecycle_advantage'] for row in data])),
                    'mean_stop_lifecycle_advantage': float(np.mean([row['gates'][gate]['stop_lifecycle_advantage'] for row in data])),
                    'mean_stop_collection_advantage': float(np.mean([row['gates'][gate]['stop_collection']['advantage'] for row in data])),
                    'mean_stop_collection_unmet': float(np.mean([row['gates'][gate]['stop_collection_unmet'] for row in data])),
                    'mean_stop_expected_collection_unmet': float(np.mean([row['gates'][gate]['stop_expected_collection_unmet'] for row in data])),
                }
            for field in ('certified', 'lifecycle_advantage', 'stop_lifecycle_advantage'):
                difference = np.array([float(row['gates']['three'][field])-float(row['gates']['two'][field]) for row in data])
                bootstrap = np.mean(difference[resamples], axis=1)
                entry['paired'][field] = {'mean_three_minus_two': float(np.mean(difference)),
                                          'bootstrap_95': [float(x) for x in np.quantile(bootstrap, [.025, .975])]}
            result[f'{group}|{checkpoint}'] = entry
    return result


def enforce_memory_limit():
    """Fail closed before RNG if a <=4 GiB POSIX address-space cap fails."""
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
        write_json(outdir / 'environment.json', {'python': sys.version, 'numpy': np.__version__,
                   'platform': platform.platform(), **memory})
        all_rows = []
        with (outdir / 'checkpoints.jsonl').open('x', encoding='utf-8') as stream:
            for gi in range(len(GROUPS)):
                for driver in range(DRIVERS):
                    rows = driver_records(gi, driver)
                    for row in rows:
                        stream.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
                    stream.flush()
                    os.fsync(stream.fileno())
                    all_rows.extend(rows)
        write_json(outdir / 'summary.json', summarize(all_rows))
        usage = resource.getrusage(resource.RUSAGE_SELF)
        write_json(outdir / 'worker_finished.json', {'status': 'finished', 'rows': len(all_rows),
                   'peak_rss_platform_units': usage.ru_maxrss, 'cpu_user_seconds': usage.ru_utime,
                   'cpu_system_seconds': usage.ru_stime})
    except BaseException as exc:
        try:
            write_json(outdir / 'worker_failure.json', {'type': type(exc).__name__, 'message': str(exc),
                       'traceback': traceback.format_exc()})
        finally:
            raise


def _worker_entry(target, outdir):
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    target(outdir)


def _artifact_hashes(outdir):
    return {str(path.relative_to(outdir)): digest(path) for path in sorted(outdir.rglob('*'))
            if path.is_file() and path.name not in ('output_hashes.json', 'completed.json', 'incomplete.json')}


def supervise(outdir, manifest_path, manifest_digest, expected_sources, *, target=_worker,
              seconds=WALL_SECONDS, started_at=None):
    start = time.monotonic() if started_at is None else started_at
    outdir = Path(outdir)
    outdir.mkdir(exist_ok=False)
    write_json(outdir / 'started.json', {'status': 'incomplete', 'manifest_sha256': manifest_digest,
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
        remaining = seconds - (time.monotonic()-start)
        if remaining <= 0:
            raise GlobalTimeout('whole-run wall limit before worker start')
        signal.setitimer(signal.ITIMER_REAL, remaining)
        child.start()
        child.join()
        if child.exitcode != 0 or not (outdir / 'worker_finished.json').is_file():
            raise InvalidRun('worker did not complete successfully')
        if source_hashes() != expected_sources or digest(manifest_path) != manifest_digest:
            raise InvalidRun('source or manifest postcheck failed')
        write_json(outdir / 'output_hashes.json', {'sha256': _artifact_hashes(outdir)})
        write_json(outdir / 'completed.json', {'status': 'complete',
                   'output_hashes_sha256': digest(outdir / 'output_hashes.json'),
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
        (outdir / 'completed.json').unlink(missing_ok=True)
        write_json(outdir / 'incomplete.json', {'status': 'incomplete', 'reason': str(exc),
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
    manifest_digest, expected_sources = verify_manifest(args.manifest)
    return 0 if supervise(args.outdir, args.manifest, manifest_digest, expected_sources,
                          started_at=started) == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
