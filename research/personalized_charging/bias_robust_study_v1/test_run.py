import itertools
import copy
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from personalized_charging.bias_robust_study_v1 import run
from personalized_charging.sequential_identification_v1.physical import simulate_episode
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import evaluate as three_gate
from personalized_charging.two_contrast_bias_exploratory_v1.gate import evaluate as two_gate


def _hang_worker(_outdir):
    time.sleep(1)


def _success_worker(outdir):
    run.write_json(Path(outdir) / 'sample.json', {'sample': True})
    run.write_json(Path(outdir) / 'worker_finished.json', {'status': 'finished'})


def _abstain(data, *, epsilon):
    return {'decision': 'ABSTAIN', 'reason': 'benefit_not_positive'}


def _allow(data, *, epsilon):
    return {'decision': 'ALLOW', 'reason': 'outward_bounds', 'central_witness': {'valid': True},
            'benefit_interval': ['0.01', '0.02'], 'candidate_service_upper': '0.004', 'bands': {}}


class BiasRobustStudyTests(unittest.TestCase):
    def test_periodic_block_schedule(self):
        self.assertEqual(run.periodic_counts(0, 16), {'p': 6, 'r': 5, 'third': 5})
        for start in range(10):
            for end in range(start, start+12):
                direct = {key: sum(i % 3 == j for i in range(start, end))
                          for j, key in enumerate(run.OFFERS)}
                self.assertEqual(run.periodic_counts(start, end), direct)

    def test_small_n_aggregate_joint_law_exactly(self):
        q, delta, m = Fraction(1, 4), Fraction(1, 200), 2
        categories = ((0, 0, (1-q)*(1-delta)), (0, 1, (1-q)*delta),
                      (1, 0, q*(1-delta)), (1, 1, q*delta))
        direct = defaultdict(Fraction)
        for path in itertools.product(categories, repeat=m):
            k = sum(x[0] for x in path)
            u = sum(x[0] and x[1] for x in path)
            v = sum(not x[0] and x[1] for x in path)
            weight = Fraction(1)
            for _, _, probability in path:
                weight *= probability
            direct[k, u, v] += weight
        def binomial(n, x, probability):
            return Fraction(math.comb(n, x)) * probability**x * (1-probability)**(n-x)
        for (k, u, v), value in direct.items():
            aggregate = binomial(m, k, q)*binomial(k, u, delta)*binomial(m-k, v, delta)
            self.assertEqual(value, aggregate)
        self.assertEqual(sum(direct.values()), 1)

    def test_physics_ledger_against_all_small_paths(self):
        theta, tau = .12, .2
        for offer in run.OFFERS:
            policy = 'collect_r' if offer == 'r' else 'collect_p'
            for events in itertools.product(((False, False), (False, True),
                                              (True, False), (True, True)), repeat=2):
                k = sum(accepted for accepted, _ in events)
                u = sum(accepted and urgent for accepted, urgent in events)
                v = sum(not accepted and urgent for accepted, urgent in events)
                expected = run.ledger(offer, 2, k, u, v, theta, .5)
                benefit, unmet = 0., 0.
                for accepted, urgent in events:
                    accept_draw, urgent_draw = (0. if accepted else .99), (0. if urgent else .5)
                    args = (theta, tau, accept_draw, accept_draw, urgent_draw)
                    default = simulate_episode('baseline', *args, p_response=.5, r_response=.5)
                    chosen = simulate_episode(policy, *args, p_response=.5, r_response=.5)
                    benefit += default.loss - chosen.loss
                    unmet += chosen.unmet_kwh
                self.assertAlmostEqual(expected['advantage'], benefit)
                self.assertEqual(expected['realized_unmet'], unmet)
                self.assertEqual(expected['urgent_arrivals'], sum(urgent for _, urgent in events))

    def test_keyed_binomial_zero_one_and_repeatability(self):
        for q in (0., 1.):
            block = run.draw_block(0, 2, 1, 0, 20, q, .1)
            self.assertEqual(block['accepted'], 20 if q else 0)
            self.assertEqual(block['served_urgent'] if q else block['blocked_urgent'], 0)
            self.assertEqual(block, run.draw_block(0, 2, 1, 0, 20, q, .1))
            self.assertEqual(len({tuple(key) for key in block['stream_keys']}), 3)
        self.assertNotEqual(run.draw_block(0, 2, 1, 0, 20, .5, .1)['stream_keys'],
                            run.draw_block(0, 3, 1, 0, 20, .5, .1)['stream_keys'])

    def test_fixed_bias_worlds_and_actual_deployment_truth(self):
        a, b, ap = run.model(2, 0), run.model(3, 0), run.model(5, 0)
        self.assertEqual((a['p'], a['r']), (b['p'], b['r']))
        self.assertEqual((ap['p'], ap['r'], ap['third']), (b['p'], b['r'], b['third']))
        self.assertEqual(a['parameter_keys'], [None, None, None])
        self.assertTrue(all(key is not None for key in run.model(0, 0)['parameter_keys']))
        self.assertLess(a['benefit'], 0)
        self.assertLess(ap['benefit'], 0)
        self.assertGreater(b['benefit'], 0)
        self.assertAlmostEqual(a['unmet'], b['unmet'])
        one = run.deploy(5, 0, 0, ap, episodes=4)
        two = run.deploy(5, 0, 0, ap, episodes=4)
        self.assertEqual(one, two)
        self.assertAlmostEqual(one['candidate_expected_unmet'], 4*ap['unmet'])

    def test_shared_alpha_and_probability_boundaries(self):
        n = 10**6
        world = run.model(3, 0)
        counts = {key: (round(world[key]*n), n) for key in run.OFFERS}
        first = two_gate({key: counts[key] for key in ('p', 'r')})
        third = three_gate(counts)
        self.assertEqual(first['bands']['p'], third['bands']['p'])
        self.assertEqual(first['bands']['r'], third['bands']['r'])
        self.assertEqual(3*Fraction(1, 60), Fraction(1, 20))
        self.assertEqual(two_gate({'p': (1, 1), 'r': (0, 1)})['reason'], 'noninterior_probability_band')
        self.assertEqual(three_gate({'p': (1, 1), 'r': (0, 1), 'third': (1, 1)})['reason'], 'noninterior_probability_band')

    def test_matched_counts_no_hidden_access_and_stop_lifecycle(self):
        calls = []
        def gate2(data, *, epsilon):
            calls.append(('two', dict(data), epsilon))
            return _allow(data, epsilon=epsilon)
        def gate3(data, *, epsilon):
            calls.append(('three', dict(data), epsilon))
            return _abstain(data, epsilon=epsilon)
        # A stubbed ALLOW isolates the latching/paired-ledger mechanics;
        # real favorable schemas are tested independently below.
        with patch.object(run, '_validated_gate', return_value=None):
            rows = run.driver_records(3, 0, checkpoints=(6, 12), deployment_episodes=2,
                                      two_gate=gate2, three_gate=gate3)
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(calls[0][1]), {'p', 'r'})
        self.assertEqual(set(calls[1][1]), {'p', 'r', 'third'})
        self.assertEqual(calls[0][1]['p'], calls[1][1]['p'])
        self.assertEqual(calls[0][1]['r'], calls[1][1]['r'])
        self.assertEqual(rows[0]['gates']['two']['first_crossing'], 6)
        self.assertEqual(rows[1]['gates']['two']['first_crossing'], 6)
        self.assertEqual(set(rows[0]['input_bands']), set(run.OFFERS))
        self.assertEqual(rows[1]['gates']['two']['stop_collection'], rows[0]['collection'])
        self.assertFalse(rows[1]['gates']['three']['certified'])
        self.assertAlmostEqual(rows[1]['gates']['two']['lifecycle_advantage'],
                               rows[1]['collection']['advantage']+rows[1]['gates']['two']['deployment_advantage'])
        self.assertAlmostEqual(rows[1]['gates']['two']['stop_lifecycle_advantage'],
                               rows[0]['collection']['advantage']+rows[1]['gates']['two']['deployment_advantage'])
        self.assertEqual(rows[1]['gates']['three']['deployment_advantage'], 0.)
        self.assertEqual(rows[0]['deployment_pair']['stream_keys'], run.deploy(3, 0, 0, rows[0]['world'], episodes=2)['stream_keys'])

    def test_failed_math_and_invalid_allow_are_not_abstentions(self):
        def broken(data, *, epsilon):
            return {'decision': 'ABSTAIN', 'reason': 'arithmetic_failure'}
        with self.assertRaises(run.InvalidRun):
            run.driver_records(0, 0, checkpoints=(3,), deployment_episodes=1,
                               two_gate=broken, three_gate=_abstain)
        def false_allow(data, *, epsilon):
            return {'decision': 'ALLOW', 'reason': 'outward_bounds', 'central_witness': {},
                    'benefit_interval': ['-1', '1'], 'candidate_service_upper': '.005', 'bands': {}}
        with self.assertRaises(run.InvalidRun):
            run.driver_records(0, 0, checkpoints=(3,), deployment_episodes=1,
                               two_gate=false_allow, three_gate=_abstain)

    def test_favorable_schema_uses_exact_shared_bands(self):
        n = 10**6
        world = run.model(3, 0)
        counts = {key: (round(world[key]*n), n) for key in run.OFFERS}
        expected = {key: run.probability_band(*counts[key])[0].json() for key in run.OFFERS}
        result = three_gate(counts)
        self.assertEqual(result['decision'], 'ALLOW', result)
        run._validated_gate(result, '0.005', 'three', expected)
        changed = copy.deepcopy(result)
        changed['candidate_service_upper'] = '-1'
        with self.assertRaises(run.InvalidRun):
            run._validated_gate(changed, '0.005', 'three', expected)
        changed = copy.deepcopy(result)
        changed['bands']['p'][0] = '0.2'
        with self.assertRaises(run.InvalidRun):
            run._validated_gate(changed, '0.005', 'three', expected)

    def test_summary_denominators_and_paired_bootstrap(self):
        rows = []
        for driver in (0, 1):
            row = run.driver_records(0, driver, checkpoints=(3,), deployment_episodes=1,
                                     two_gate=_abstain, three_gate=_abstain)[0]
            if driver == 0:
                row['world']['benefit'] = -.1
                row['gates']['two']['certified'] = True
                row['gates']['two']['false_declaration'] = True
            else:
                row['world']['benefit'] = .1
            rows.append(row)
        entry = run.summarize(rows, n_bootstrap=20)['beneficial|3']
        self.assertEqual(entry['n'], 2)
        self.assertEqual(entry['gates']['two']['null_denominator'], 1)
        self.assertEqual(entry['gates']['two']['false'], 1)
        self.assertEqual(entry['gates']['two']['false_fraction_given_null'], 1.)
        self.assertEqual(entry['gates']['two']['certified_fraction'], .5)
        self.assertEqual(entry['gates']['three']['false'], 0)
        self.assertEqual(len(entry['paired']['certified']['bootstrap_95']), 2)

    def test_fail_closed_memory_before_rng(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(run, 'enforce_memory_limit', side_effect=run.InvalidRun('no cap')), \
                 patch.object(run, 'rng_for', side_effect=AssertionError('RNG must not run')):
                with self.assertRaises(run.InvalidRun):
                    run._worker(tmp)
            self.assertTrue((Path(tmp) / 'worker_failure.json').exists())
            self.assertFalse((Path(tmp) / 'checkpoints.jsonl').exists())
        with patch.object(run.resource, 'getrlimit', return_value=(-1, -1)), \
             patch.object(run.resource, 'setrlimit', side_effect=OSError('denied')):
            with self.assertRaises(run.InvalidRun):
                run.enforce_memory_limit()

    def test_manifest_postcheck_digest_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            hashes = run.source_hashes()
            self.assertTrue(any(x.endswith('test_aggregate_independent.py') for x in hashes))
            manifest.write_text(json.dumps({'sha256': hashes}), encoding='utf8')
            manifest_digest, source = run.verify_manifest(manifest)
            out = root / 'ok'
            self.assertEqual(run.supervise(out, manifest, manifest_digest, source,
                                           target=_success_worker, seconds=2), 'complete')
            output = json.loads((out / 'output_hashes.json').read_text())['sha256']
            self.assertEqual(output['sample.json'], run.digest(out / 'sample.json'))
            self.assertNotIn('completed.json', output)
            with self.assertRaises(FileExistsError):
                run.supervise(out, manifest, manifest_digest, source, target=_success_worker, seconds=2)
            manifest.write_text('{}', encoding='utf8')
            out2 = root / 'changed'
            self.assertEqual(run.supervise(out2, manifest, manifest_digest, source,
                                           target=_success_worker, seconds=2), 'incomplete')
            self.assertFalse((out2 / 'completed.json').exists())
            with self.assertRaises(ValueError):
                run.verify_manifest(manifest)

    def test_watchdog_and_real_signal_reap_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'sha256': run.source_hashes()}), encoding='utf8')
            md, source = run.verify_manifest(manifest)
            out = root / 'timeout'
            self.assertEqual(run.supervise(out, manifest, md, source, target=_hang_worker, seconds=.05), 'incomplete')
            self.assertTrue((out / 'started.json').exists())
            self.assertTrue((out / 'incomplete.json').exists())
            self.assertFalse((out / 'completed.json').exists())
            code = '''\
import os, sys, time
from pathlib import Path
from personalized_charging.bias_robust_study_v1 import run
def worker(outdir):
    (Path(outdir) / "worker.pid").write_text(str(os.getpid()))
    time.sleep(30)
md, source = run.verify_manifest(sys.argv[2])
run.supervise(sys.argv[1], sys.argv[2], md, source, target=worker, seconds=30)
'''
            for signum in (signal.SIGTERM, signal.SIGINT):
                with self.subTest(signum=signum):
                    target = root / str(signum)
                    proc = subprocess.Popen([sys.executable, '-c', code, str(target), str(manifest)],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        deadline = time.monotonic()+5
                        while not (target/'worker.pid').exists() and time.monotonic() < deadline:
                            if proc.poll() is not None:
                                break
                            time.sleep(.01)
                        self.assertTrue((target/'worker.pid').exists(), proc.communicate(timeout=1) if proc.poll() is not None else '')
                        pid = int((target/'worker.pid').read_text())
                        proc.send_signal(signum)
                        proc.communicate(timeout=5)
                        self.assertTrue((target/'incomplete.json').exists())
                        self.assertFalse((target/'completed.json').exists())
                        with self.assertRaises(ProcessLookupError):
                            os.kill(pid, 0)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
