import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

from personalized_charging.matched_verifiers_v1 import run


def _hang_worker(_outdir):
    time.sleep(1)


def _success_worker(outdir):
    run.write_json(Path(outdir) / 'sample.json', {'sample': True})
    run.write_json(Path(outdir) / 'worker_finished.json', {'status': 'finished'})


def _fast_abstain(history, epsilon):
    return {'outcome': 'node_limit', 'result': {'decision': 'ABSTAIN',
            'reason': 'node_limit', 'nodes': 99}, 'replay': None, 'elapsed': 0.001}


class MatchedStudyTests(unittest.TestCase):
    def test_probabilities_and_shifted_actual_target(self):
        p, r, benefit, unmet = run.true_values(.1, .2, 0.)
        self.assertEqual(p, .5)
        self.assertAlmostEqual(r, 1 / (1 + math.exp(-.25)))
        self.assertAlmostEqual(benefit, -.015)
        self.assertAlmostEqual(unmet, (.5 + .5 * r) / 200)
        ps, rs, shifted_benefit, shifted_unmet = run.true_values(.1, .2, 2.)
        self.assertGreater(ps, p)
        self.assertGreater(rs, r)
        self.assertAlmostEqual(shifted_benefit, ps * (-.03))
        self.assertLessEqual(shifted_unmet, .005)

    def test_streams_fresh_deterministic_and_independent_event_keys(self):
        t, s, values = run.streams(0, 0, count=6)
        t2, s2, values2 = run.streams(0, 0, count=6)
        self.assertEqual((t, s), (t2, s2))
        np.testing.assert_array_equal(values, values2)
        self.assertFalse(np.array_equal(values[:, 0], values[:, 1]))
        self.assertFalse(np.array_equal(values, run.streams(0, 1, count=6)[2]))
        self.assertFalse(np.array_equal(values, run.streams(1, 0, count=6)[2]))

    def test_collection_pairing_and_matched_verifier_histories(self):
        seen = []
        def collector_call(history, epsilon):
            seen.append((history, epsilon))
            return _fast_abstain(history, epsilon)
        innovations = np.full((6, 3), .1)
        rows = run.simulate_unit('easy', 0, 0., .05, '0.005', False, innovations,
                                 collection=4, deployment=2, checkpoints=(2, 4), call=collector_call)
        self.assertEqual(len(rows), 4)
        for collector in run.COLLECTORS:
            paired = [row for row in rows if row['collector'] == collector]
            self.assertEqual(paired[0]['history'], paired[1]['history'])
            self.assertEqual(paired[0]['checkpoints'], paired[1]['checkpoints'])
        self.assertEqual([e[0] for e in rows[0]['history']], ['p'] * 4)
        alternating = next(row for row in rows if row['collector'] == 'alternating')
        self.assertEqual([e[0] for e in alternating['history']], ['p', 'r', 'p', 'r'])
        self.assertEqual([e[0] for e in seen[0][0]], ['p', 'p'])
        self.assertEqual([e[0] for e in seen[2][0]], ['p', 'r'])
        self.assertTrue(all(not row['certified'] for row in rows))
        self.assertTrue(all(row['deployment_advantage'] == 0 for row in rows))

    def test_episode_ledger_covers_paired_and_selected_events(self):
        events = []
        rows = run.simulate_unit('easy', 0, 0., .05, '0.005', False, np.full((6, 3), .1),
                                 collection=4, deployment=2, checkpoints=(2, 4),
                                 call=_fast_abstain, event_writer=events.append)
        innovations = [e for e in events if e['kind'] == 'innovation']
        self.assertEqual(len(innovations), 6)
        self.assertEqual([e['episode_index'] for e in innovations], list(range(6)))
        episodes = [e for e in events if e['kind'] == 'episode']
        self.assertEqual(len([e for e in episodes if e['phase'] == 'paired_default']), 6)
        self.assertEqual(len([e for e in episodes if e['phase'] == 'paired_candidate']), 2)
        self.assertEqual(len([e for e in episodes if e['phase'] == 'collection']), 8)
        deployed = [e for e in episodes if e['phase'] == 'deployment']
        self.assertEqual(len(deployed), 8)
        self.assertTrue(all(e['policy'] == 'baseline' for e in deployed))
        self.assertTrue(all(len(e['events']) >= 2 and 'occupied_after' in e['events'][0]
                            for e in episodes))
        self.assertEqual({e['gate'] for e in deployed}, set(run.GATES))
        self.assertTrue(all(not r['certified'] for r in rows))

    def test_tight_service_prevents_p_only_latching(self):
        innovations = np.zeros((18, 3))
        rows = run.simulate_unit('tight', 0, 0., .05, '0.0045', False, innovations,
                                 collection=16, deployment=2, checkpoints=(12, 16), call=_fast_abstain)
        p_row = next(row for row in rows if row['collector'] == 'p_only' and row['gate'] == 'p_only')
        self.assertFalse(p_row['certified'])
        self.assertEqual([v['p_only_status'] for v in p_row['checkpoints']], ['service_bound'] * 2)
        self.assertAlmostEqual(p_row['expected_collection_unmet'], 16 * p_row['actual_p'] / 200)
        self.assertLess(p_row['expected_collection_unmet'], 16 * .0045)

    def test_per_call_timeout_and_replay_failure(self):
        def slow_solver(*args, **kwargs):
            time.sleep(.05)
        result = run.continuous_call((), '0.005', seconds=.01, solver=slow_solver)
        self.assertEqual(result['outcome'], 'elapsed_limit')
        self.assertIsNone(result['result'])

        def allow_solver(*args, **kwargs):
            return {'decision': 'ALLOW', 'reason': 'outward_bounds', 'nodes': 5,
                    'proof': {'placeholder': True}}
        def slow_checker(*args, **kwargs):
            time.sleep(.05)
        result = run.continuous_call((), '0.005', seconds=.01, solver=allow_solver, checker=slow_checker)
        self.assertEqual(result['outcome'], 'elapsed_limit')
        self.assertEqual(result['result']['decision'], 'ALLOW')
        result = run.continuous_call((), '0.005', solver=allow_solver,
                                     checker=lambda *a, **k: (False, 'corrupt'))
        self.assertEqual(result['outcome'], 'invalid_replay')
        def invalid_call(history, epsilon):
            return result
        with self.assertRaises(run.InvalidRun):
            run.simulate_unit('easy', 0, 0., .05, '0.005', False, np.zeros((3, 3)),
                              collection=2, deployment=1, checkpoints=(2,), call=invalid_call)

    def test_solver_schema_and_unverified_witness_labels(self):
        def alleged(*args, **kwargs):
            return {'decision': 'ABSTAIN', 'reason': 'nonpositive_benefit_witness',
                    'nodes': 0, 'witness': ('0.2', '0.2')}
        value = run.continuous_call((), '0.005', solver=alleged)
        self.assertEqual(value['outcome'], 'unverified_nonpositive_benefit_witness')
        def malformed(*args, **kwargs):
            return {'decision': 'ABSTAIN', 'reason': 'nonpositive_benefit_witness',
                    'nodes': 101, 'witness': ('0.2', '0.2')}
        self.assertEqual(run.continuous_call((), '0.005', solver=malformed)['outcome'], 'invalid_solver')
        def malformed_witness(*args, **kwargs):
            return {'decision': 'ABSTAIN', 'reason': 'service_violation_witness',
                    'nodes': 0, 'witness': ('NaN', '0.2')}
        self.assertEqual(run.continuous_call((), '0.005', solver=malformed_witness)['outcome'], 'invalid_solver')

    def test_real_proof_replay_before_allow(self):
        history = (('p', True),) * 32 + (('r', True),) * 8
        result = run.continuous_call(history, '0.005')
        self.assertEqual(result['outcome'], 'allow', result)
        self.assertTrue(result['replay']['valid'])
        self.assertIn('proof', result['result'])

    def test_stratification_denominators_and_paired_bootstrap(self):
        rows = []
        for driver, band, feasible in ((0, 'nonpositive', True),
                                       (1, 'positive_at_or_below_margin', True),
                                       (2, 'above_margin', False)):
            for collector in run.COLLECTORS:
                for gate in run.GATES:
                    certified = driver != 1
                    rows.append({'group': 'easy', 'driver': driver, 'collector': collector, 'gate': gate,
                                 'benefit_band': band, 'service_feasible': feasible,
                                 'truth_eligible': driver == 1, 'certified': certified,
                                 'false_declaration': certified, 'p_margin_false': gate == 'p_only' and driver == 0,
                                 'actual_B': -.01 if driver == 0 else .01,
                                 'first_crossing': 16 if certified else None,
                                 'checkpoints': [], 'collection_unmet': 0., 'expected_collection_unmet': 0.,
                                 'deployment_unmet': 0., 'expected_deployment_unmet': 0.,
                                 'collection_advantage': 0., 'deployment_advantage': 0.,
                                 'lifecycle_advantage': 0., 'stop_counterfactual_advantage': 0.})
        result = run.summarize(rows, n_bootstrap=20)['easy']
        method = result['methods']['p_only:p_only']
        self.assertEqual(method['n'], 3)
        self.assertEqual(method['false_null_denominator'], 2)
        self.assertEqual(method['false_n'], 2)
        self.assertEqual(method['strata']['nonpositive|service_True']['n'], 1)
        self.assertEqual(method['strata']['positive_at_or_below_margin|service_False']['n'], 0)
        self.assertIsNone(method['strata']['positive_at_or_below_margin|service_False']['false_wilson_95'])
        self.assertEqual(len(result['paired']), 6)

    def test_manifest_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'manifest.json'
            hashes = run.source_hashes()
            for suffix in ('test_physical.py', 'test_certificate.py', 'test_comparator.py',
                           'test_proof_replay.py'):
                self.assertTrue(any(name.endswith(suffix) for name in hashes))
            path.write_text(json.dumps({'sha256': hashes}), encoding='utf8')
            _, found = run.verify_manifest(path)
            self.assertEqual(found, hashes)
            hashes[next(iter(hashes))] = '0' * 64
            path.write_text(json.dumps({'sha256': hashes}), encoding='utf8')
            with self.assertRaises(ValueError):
                run.verify_manifest(path)
            path.write_text(json.dumps({'sha256': {}}), encoding='utf8')
            with self.assertRaises(ValueError):
                run.verify_manifest(path)

    def test_global_timeout_and_exclusive_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'timeout'
            status = run.supervise(out, 'dummy', run.source_hashes(), target=_hang_worker, seconds=.05)
            self.assertEqual(status, 'incomplete')
            self.assertTrue((out / 'started.json').exists())
            self.assertTrue((out / 'incomplete.json').exists())
            self.assertFalse((out / 'completed.json').exists())
            with self.assertRaises(FileExistsError):
                run.supervise(out, 'dummy', run.source_hashes(), target=_hang_worker, seconds=.05)

    def test_source_postcheck_and_output_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'complete'
            status = run.supervise(out, 'dummy', run.source_hashes(), target=_success_worker, seconds=2.)
            self.assertEqual(status, 'complete')
            self.assertTrue((out / 'completed.json').exists())
            hashes = json.loads((out / 'output_hashes.json').read_text())['sha256']
            self.assertEqual(hashes['sample.json'], run.digest(out / 'sample.json'))
            self.assertNotIn('completed.json', hashes)
            bad = run.source_hashes()
            bad[next(iter(bad))] = '0' * 64
            out2 = Path(tmp) / 'postcheck_fail'
            status = run.supervise(out2, 'dummy', bad, target=_success_worker, seconds=2.)
            self.assertEqual(status, 'incomplete')
            self.assertFalse((out2 / 'completed.json').exists())

    def test_real_sigterm_and_sigint_reap_worker(self):
        code = '''\
import os, sys, time
from pathlib import Path
from personalized_charging.matched_verifiers_v1 import run
def worker(outdir):
    (Path(outdir) / "worker.pid").write_text(str(os.getpid()))
    time.sleep(30)
run.supervise(sys.argv[1], "dummy", run.source_hashes(), target=worker, seconds=30)
'''
        with tempfile.TemporaryDirectory() as tmp:
            for signum in (signal.SIGTERM, signal.SIGINT):
                with self.subTest(signum=signum):
                    out = Path(tmp) / str(signum)
                    proc = subprocess.Popen([sys.executable, '-c', code, str(out)],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    try:
                        deadline = time.monotonic() + 5
                        while not (out / 'worker.pid').exists() and time.monotonic() < deadline:
                            if proc.poll() is not None:
                                break
                            time.sleep(.01)
                        self.assertTrue((out / 'worker.pid').exists(), proc.communicate(timeout=1) if proc.poll() is not None else '')
                        worker_pid = int((out / 'worker.pid').read_text())
                        proc.send_signal(signum)
                        proc.communicate(timeout=5)
                        self.assertTrue((out / 'incomplete.json').exists())
                        self.assertFalse((out / 'completed.json').exists())
                        with self.assertRaises(ProcessLookupError):
                            os.kill(worker_pid, 0)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
