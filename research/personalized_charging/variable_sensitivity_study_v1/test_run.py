import copy
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from personalized_charging.variable_physics_exploratory_v1.physical import simulate
from personalized_charging.variable_physics_exploratory_v1.prior_gate import evaluate as prior_gate
from personalized_charging.variable_sensitivity_study_v1 import run


def _hang_worker(_outdir):
    time.sleep(1)


def _success_worker(outdir):
    run.write_json(Path(outdir)/'sample.json', {'sample': True})
    run.write_json(Path(outdir)/'worker_finished.json', {'status': 'finished'})


class VariableSensitivityStudyTests(unittest.TestCase):
    def test_probability_cells_and_periodic_schedule(self):
        probabilities = run.joint_probabilities(.3, .4, .6, .02)
        self.assertEqual(len(probabilities), 12)
        self.assertAlmostEqual(sum(probabilities), 1.)
        self.assertAlmostEqual(sum(q for q, (first, _, _) in zip(probabilities, run.CATEGORIES) if first == 0), .3)
        self.assertAlmostEqual(sum(q for q, (first, _, _) in zip(probabilities, run.CATEGORIES) if first != 2), .6)
        self.assertAlmostEqual(sum(q for q, (_, r, _) in zip(probabilities, run.CATEGORIES) if r), .4)
        self.assertAlmostEqual(sum(q for q, (_, _, u) in zip(probabilities, run.CATEGORIES) if u), .02)
        with self.assertRaises(run.InvalidRun):
            run.joint_probabilities(.7, .4, .6, .02)
        for start in range(10):
            for end in range(start, start+10):
                exact = {key: sum(i % 3 == j for i in range(start, end))
                         for j, key in enumerate(run.OFFERS)}
                self.assertEqual(run.periodic_counts(start, end), exact)

    def test_each_runtime_category_against_exact_physical_simulator(self):
        for physical in (run.GROUPS[0][1], run.GROUPS[5][1]):
            world = {'theta': .08, 'p': .3, 'r': .4, 'third': .6, 'physics': physical,
                     'unmet': float(physical['delta'])*(.3+.7*.4)}
            for index, (first, rb, urgent) in enumerate(run.CATEGORIES):
                cells = [0]*12
                cells[index] = 1
                first_u = ('0.1', '.45', '.8')[first]
                inputs = dict(g0=physical['g0'], g1=physical['g1'], g2=physical['g2'],
                              W=physical['W'], delta=physical['delta'], theta='.08',
                              p='.3', r='.4', third='.6', u_p=first_u, u_third=first_u,
                              u_r='0.2' if rb else '.8', u_urgent='.001' if urgent else '.5')
                baseline = simulate('baseline', **inputs)
                candidate = simulate('candidate', **inputs)
                for offer in run.OFFERS:
                    with self.subTest(physics=physical, category=index, offer=offer):
                        ledger = run.block_ledger(cells, offer, world)
                        collection = simulate('collect_'+offer, **inputs)
                        self.assertAlmostEqual(ledger['candidate_advantage'], float(baseline.system_cost-candidate.system_cost))
                        self.assertAlmostEqual(ledger['collection_advantage'], float(baseline.system_cost-collection.system_cost))
                        self.assertEqual(ledger['candidate_unmet'], candidate.unmet_kwh)
                        self.assertEqual(ledger['blocked_urgent'], collection.unmet_kwh)
                        self.assertEqual(ledger['urgent_arrivals'], urgent)

    def test_fixed_worlds_prior_rules_and_tie(self):
        a, b, ap = (run.sample_world(i, 0) for i in (6, 7, 8))
        self.assertEqual((a['p'], a['r']), (b['p'], b['r']))
        self.assertEqual((ap['p'], ap['r'], ap['third']), (b['p'], b['r'], b['third']))
        self.assertLess(a['benefit'], 0)
        self.assertLess(ap['benefit'], 0)
        self.assertGreater(b['benefit'], 0)
        for index in (0, 1):
            self.assertEqual(prior_gate(**run.GROUPS[index][1])['decision'], 'ALLOW')
        equal = run.physics('.25', '.125', '0', '0', '0', '0')
        self.assertEqual(prior_gate(**equal)['decision'], 'ABSTAIN')
        tight = dict(run.GROUPS[0][1])
        tight['epsilon'] = '.004'
        self.assertEqual(prior_gate(**tight)['reason'], 'service_not_certified')

    def test_near_zero_selection_is_bounded_and_conditioned(self):
        # A new seed and an out-of-catalog driver identify a small dev fixture.
        with patch.object(run, 'MASTER_SEED', 972001):
            world = run.sample_world(3, 999)
        self.assertLessEqual(abs(world['benefit']), .002)
        self.assertGreaterEqual(world['selection_attempt'], 1)
        self.assertLessEqual(world['selection_attempt'], run.MAX_ATTEMPTS)
        class FakeRng:
            def __init__(self, code):
                self.code = code
            def uniform(self, *_args):
                return (.25, .2, 0.)[self.code]
        with patch.object(run, 'rng_for', side_effect=lambda key: FakeRng(key[-1])):
            with self.assertRaises(run.InvalidRun):
                run.sample_world(3, 0, max_attempts=2)

    def test_common_history_is_only_gate_input_and_keyed_pairing(self):
        seen = []
        def spy(counts, *, method, **physical):
            seen.append((method, dict(counts), dict(physical)))
            return run.data_evaluate(counts, method=method, **physical)
        with patch.object(run, 'MASTER_SEED', 972002):
            rows = run.driver_records(0, 999, checkpoints=(6, 12), deployment_episodes=2, data_gate=spy)
            repeat = run.driver_records(0, 999, checkpoints=(6, 12), deployment_episodes=2)
        self.assertEqual(seen[0][0], 'two')
        self.assertEqual(set(seen[0][1]), {'p', 'r'})
        self.assertEqual(set(seen[1][1]), {'p', 'r', 'third'})
        self.assertEqual(seen[0][1]['p'], seen[1][1]['p'])
        self.assertEqual(seen[0][1]['r'], seen[1][1]['r'])
        self.assertEqual(set(seen[0][2]), {'g0', 'g1', 'g2', 'delta', 'W', 'epsilon'})
        self.assertEqual(rows[0]['block_evaluator_only'], repeat[0]['block_evaluator_only'])
        self.assertEqual(rows[0]['deployment_evaluator_only'], repeat[0]['deployment_evaluator_only'])
        self.assertTrue(rows[0]['methods']['prior']['certified'])
        self.assertEqual(rows[0]['methods']['default']['lifecycle_advantage'], 0.)
        self.assertEqual(rows[0]['methods']['prior']['collection_advantage'],
                         rows[0]['collection_evaluator']['candidate_advantage'])

    def test_stop_counterfactual_runs_candidate_for_remaining_calendar(self):
        def joint(group_index, driver, block_index, offer_index, m, world, *, deployment=False):
            cells = [0]*12
            cells[run.CATEGORIES.index((0, 0, 0))] = m
            return {'m': m, 'stream_key': [block_index, offer_index], 'joint_counts_evaluator_only': cells}
        def allow(data, *, method, **physical):
            return {'decision': 'ALLOW', 'reason': 'outward_bounds'}
        # Isolate calendar bookkeeping; real gate outputs are tested elsewhere.
        with patch.object(run, 'joint_block', side_effect=joint), \
             patch.object(run, '_valid_data_gate', return_value=None):
            rows = run.driver_records(0, 999, checkpoints=(3, 6), deployment_episodes=2, data_gate=allow)
        first, second = rows
        initial = first['collection_evaluator']
        total = second['collection_evaluator']
        method = second['methods']['two']
        self.assertEqual(method['first_crossing'], 3)
        expected = (initial['collection_advantage'] + total['candidate_advantage']-
                    initial['candidate_advantage'] + method['deployment_advantage'])
        self.assertAlmostEqual(method['stop_lifecycle_advantage'], expected)
        self.assertAlmostEqual(method['lifecycle_advantage'], total['collection_advantage']+method['deployment_advantage'])
        self.assertNotEqual(method['stop_lifecycle_advantage'], method['lifecycle_advantage'])

    def test_signed_penalty_and_missing_or_invalid_gates(self):
        data = [0]*12
        data[run.CATEGORIES.index((0, 0, 1))] = 1
        world = {'theta': .08, 'p': .3, 'r': .4, 'third': .6,
                 'physics': run.GROUPS[5][1], 'unmet': .02*(.3+.7*.4)}
        ledger = run.block_ledger(data, 'p', world)
        expected = .51-.5-.08-(.2-.5)
        self.assertAlmostEqual(ledger['candidate_advantage'], expected)
        with self.assertRaises(run.InvalidRun):
            run._valid_data_gate({'decision': 'ABSTAIN', 'reason': 'inference_unresolved',
                                  'inference_reason': 'arithmetic_failure'}, 'two', run.GROUPS[0][1], {})
        unresolved = {'decision': 'ABSTAIN', 'reason': 'inference_unresolved',
                      'inference_reason': 'noninterior_probability_band'}
        self.assertIsNone(run._valid_data_gate(unresolved, 'two', run.GROUPS[0][1], {}))
        malformed = dict(unresolved, decision='ALLOW')
        with self.assertRaises(run.InvalidRun):
            run._valid_data_gate(malformed, 'two', run.GROUPS[0][1], {})
        with self.assertRaises(run.InvalidRun):
            run._valid_data_gate({'decision': 'ALLOW', 'reason': 'outward_bounds'},
                                 'two', run.GROUPS[0][1], {})

    def test_alpha_and_truth_strata_paired_bootstrap(self):
        self.assertEqual(sum((1/60 for _ in range(3))), .05)
        with patch.object(run, 'MASTER_SEED', 972003):
            rows = [run.driver_records(0, driver, checkpoints=(3,), deployment_episodes=1)[0]
                    for driver in (999, 1000)]
        rows[0]['world']['benefit'] = -.1
        rows[0]['methods']['two']['certified'] = True
        rows[0]['methods']['two']['false_declaration'] = True
        rows[1]['world']['benefit'] = .1
        entry = run.summarize(rows, n_bootstrap=20)['prior_positive_1|3']
        self.assertEqual(entry['methods']['two']['null_denominator'], 1)
        self.assertEqual(entry['methods']['two']['false'], 1)
        self.assertEqual(len(entry['paired']), 6)
        self.assertEqual(entry['methods']['default']['certified'], 0)

    def test_fail_closed_memory_before_catalog_rng(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(run, 'enforce_memory_limit', side_effect=run.InvalidRun('no cap')), \
                 patch.object(run, 'rng_for', side_effect=AssertionError('RNG must not run')):
                with self.assertRaises(run.InvalidRun):
                    run._worker(tmp)
            self.assertTrue((Path(tmp)/'worker_failure.json').exists())
            self.assertFalse((Path(tmp)/'checkpoints.jsonl').exists())
        with patch.object(run.resource, 'getrlimit', return_value=(-1, -1)), \
             patch.object(run.resource, 'setrlimit', side_effect=OSError('denied')):
            with self.assertRaises(run.InvalidRun):
                run.enforce_memory_limit()

    def test_manifest_postcheck_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/'manifest.json'
            hashes = run.source_hashes()
            self.assertTrue(any(name.endswith('test_joint_independent.py') for name in hashes))
            manifest.write_text(json.dumps({'sha256': hashes}), encoding='utf8')
            md, source = run.verify_manifest(manifest)
            out = root/'complete'
            self.assertEqual(run.supervise(out, manifest, md, source, target=_success_worker, seconds=2), 'complete')
            saved = json.loads((out/'output_hashes.json').read_text())['sha256']
            self.assertEqual(saved['sample.json'], run.digest(out/'sample.json'))
            with self.assertRaises(FileExistsError):
                run.supervise(out, manifest, md, source, target=_success_worker, seconds=2)
            manifest.write_text('{}', encoding='utf8')
            self.assertEqual(run.supervise(root/'changed', manifest, md, source,
                                           target=_success_worker, seconds=2), 'incomplete')
            with self.assertRaises(ValueError):
                run.verify_manifest(manifest)

    def test_watchdog_and_real_signal_reap_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'sha256': run.source_hashes()}), encoding='utf8')
            md, source = run.verify_manifest(manifest)
            out = root/'timeout'
            self.assertEqual(run.supervise(out, manifest, md, source, target=_hang_worker, seconds=.05), 'incomplete')
            self.assertTrue((out/'started.json').exists())
            self.assertTrue((out/'incomplete.json').exists())
            self.assertFalse((out/'completed.json').exists())
            code = '''\
import os, sys, time
from pathlib import Path
from personalized_charging.variable_sensitivity_study_v1 import run
def worker(outdir):
    (Path(outdir)/"worker.pid").write_text(str(os.getpid()))
    time.sleep(30)
md, source = run.verify_manifest(sys.argv[2])
run.supervise(sys.argv[1], sys.argv[2], md, source, target=worker, seconds=30)
'''
            for signum in (signal.SIGTERM, signal.SIGINT):
                with self.subTest(signum=signum):
                    target = root/str(signum)
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

    def test_pending_signal_during_worker_creation_is_reaped_after_unmask(self):
        class FakeProcess:
            def __init__(self, signum):
                self.signum, self.started, self.terminated, self.joined = signum, False, False, False
            def start(self):
                self.started = True
                if self.signum == signal.SIGALRM:
                    time.sleep(.35)
                else:
                    os.kill(os.getpid(), self.signum)
            def is_alive(self):
                return self.started and not self.terminated
            def terminate(self):
                self.terminated = True
            def join(self, *_args):
                self.joined = True
            def kill(self):
                self.terminated = True
        class FakeContext:
            def __init__(self, process):
                self.process = process
            def Process(self, **_kwargs):
                return self.process
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'sha256': run.source_hashes()}), encoding='utf8')
            md, source = run.verify_manifest(manifest)
            for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT):
                with self.subTest(signum=signum):
                    process = FakeProcess(signum)
                    out = root/f'pending_{signum}'
                    duration = .2 if signum == signal.SIGALRM else 2.
                    with patch.object(run.multiprocessing, 'get_context', return_value=FakeContext(process)):
                        status = run.supervise(out, manifest, md, source, target=_hang_worker, seconds=duration)
                    self.assertEqual(status, 'incomplete')
                    self.assertTrue(process.terminated)
                    self.assertTrue(process.joined)
                    self.assertTrue((out/'incomplete.json').exists())
                    self.assertFalse((out/'completed.json').exists())


if __name__ == '__main__':
    unittest.main()
