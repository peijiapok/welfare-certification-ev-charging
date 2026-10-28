"""Deterministic checks of schedule counts and each aggregate physical cell."""
from fractions import Fraction as F
from itertools import product
import unittest
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from personalized_charging.two_driver_exploratory_v1.test_independent_fraction import (
    PARAMETERS, cells, inputs, independent_gain_and_unmet)
from personalized_charging.two_driver_exploratory_v1.physical import simulate
from personalized_charging.two_driver_exploratory_v1.schedule import plan
from personalized_charging.two_driver_study_v1 import run

class StudyRunnerControls(unittest.TestCase):
    def world(self, physics):
        return {'physics':dict(zip(('g0','g1','g2','W'),physics),delta='.02',epsilon='.02'),
            'users':{'A':dict(theta=.08,p=.3,r=.4,third=.6),
                     'B':dict(theta=.12,p=.2,r=.55,third=.7)}}

    def test_calendar_counts_and_no_gaps(self):
        for start,end in ((0,16),(16,64),(64,256),(99,100), (0,1000000)):
            for pos in range(6):
                expected=max(0,(end+5-pos)//6-(start+5-pos)//6)
                self.assertEqual(run.schedule_count(start,end,pos),expected)
            self.assertEqual(sum(run.schedule_count(start,end,p) for p in range(6)),end-start)
        for variant in run.SCHEDULES:
            for pos in range(6):
                role,action=plan(pos,variant)
                self.assertEqual(role,'AB' if pos%2==0 else 'BA')
                self.assertEqual(action,('first_p','second_r','first_third','first_p',
                    'candidate' if variant=='natural' else 'second_r','first_third')[pos])

    def test_aggregates_match_independent_physical_every_cell(self):
        worlds=(('0.568','0.548','0.4','20'),('0.51','0.46','0.5','0.2'),
                ('0','0','0','0'),('0.8','0.65','0.4','20'))
        for values,pos,variant in product(worlds,range(6),run.SCHEDULES):
            role,action=plan(pos,variant)
            config=PARAMETERS[role]; w=self.world(values)
            for idx,row in enumerate(cells(role)):
                one=[0]*12; one[idx]=1
                actual=run.ledger(w,role,pos,one,variant)
                episode=simulate(role,action,**inputs(row,values))
                baseline=simulate(role,'baseline',**inputs(row,values))
                self.assertAlmostEqual(actual['gain'],float(baseline.system_cost-episode.system_cost),places=12)
                self.assertEqual(actual['unmet'],episode.unmet_kwh)
                observed={(e.driver,e.offer):int(e.accepted) for e in episode.events if e.offer}
                for user in ('A','B'):
                    for offer in run.OFFERS:
                        key=(user,offer)
                        self.assertEqual(actual['observed'][user][offer],
                                         [observed.get(key,0),int(key in observed)])
                if role=='AB':
                    candidate=simulate(role,'candidate',**inputs(row,values))
                    self.assertAlmostEqual(actual['candidate_gain'],float(baseline.system_cost-candidate.system_cost),places=12)
                    self.assertEqual(actual['candidate_unmet'],candidate.unmet_kwh)
                else:
                    self.assertEqual(actual['candidate_gain'],0)
                self.assertEqual(actual['suppressed'],int(pos==4 and variant=='natural' and row['p']))

    def test_constructed_identical_feedback_opposite_welfare(self):
        a,b,ap=run.world(4,0),run.world(5,0),run.world(6,0)
        self.assertLess(a['benefit'],0); self.assertGreater(b['benefit'],0)
        self.assertLess(ap['benefit'],0)
        for i in ('A','B'):
            for c in ('p','r'):
                self.assertEqual(a['users'][i][c],b['users'][i][c])
                self.assertEqual(ap['users'][i][c],b['users'][i][c])
            self.assertEqual(ap['users'][i]['third'],b['users'][i]['third'])

    def test_empty_or_bad_manifest_rejected(self):
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode='w') as f:
            json.dump({'sha256':{}},f); f.flush()
            with self.assertRaises(ValueError): run.sources(f.name)

    def test_rejects_fabricated_certificates(self):
        from copy import deepcopy
        from personalized_charging.two_driver_exploratory_v1.test_prototype import counts
        phys=run.GROUPS[0][1]
        actual=run.prior_only(**phys)
        run.validate_prior(actual,phys)
        for invalid in ({'decision':'ALLOW','reason':'invalid_input'},
                        dict(actual,service_upper='0'),dict(actual,reason='unknown')):
            with self.assertRaises(ValueError): run.validate_prior(invalid,phys)
        ca,_=counts('.02','.2','.2',10**10)
        cb,_=counts('.04','.15','-.1',10**10)
        observed={'A':ca,'B':cb}
        for method in ('two','three'):
            result=run.evaluate(observed,method=method,**phys)
            self.assertEqual(result['decision'],'ALLOW')
            run.validate_gate(result,observed,method,phys)
            fake=deepcopy(result); fake.pop('witness')
            with self.assertRaises(ValueError): run.validate_gate(fake,observed,method,phys)
            fake=deepcopy(result); fake['benefit_interval']=['999','1000']
            with self.assertRaises(ValueError): run.validate_gate(fake,observed,method,phys)
            with self.assertRaises(ValueError): run.validate_gate({'decision':'ABSTAIN','reason':'unknown'},observed,method,phys)
            with self.assertRaises(ValueError): run.validate_gate({'decision':'ABSTAIN','reason':'missing_stream'},observed,method,phys)

    def test_incomplete_receipt_on_timeout_or_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with self.assertRaises(TimeoutError): run.finish_receipt(out,{'status':'complete'},time.monotonic()-601)
            self.assertFalse((out/'completed.json').exists())
        for error in (TimeoutError('alarm'),InterruptedError('SIGTERM')):
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory)
                with patch.object(run,'write_json',side_effect=error):
                    with self.assertRaises(type(error)): run.finish_receipt(out,{'status':'complete'},time.monotonic())
                self.assertFalse((out/'completed.json').exists())
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            run.finish_receipt(out,{'status':'complete'},time.monotonic())
            self.assertTrue((out/'completed.json').exists())
            self.assertFalse((out/'completion_pending.json').exists())

    def test_signal_after_pending_check_uses_atomic_commit_point(self):
        import subprocess, sys
        code = """
import os, signal, tempfile, time, threading
from pathlib import Path
from unittest.mock import patch
from personalized_charging.two_driver_study_v1 import run

def interrupted(*args):
    raise InterruptedError('SIGTERM delivered')
original=os.replace
signal.signal(signal.SIGTERM,interrupted)
with tempfile.TemporaryDirectory() as directory:
    out=Path(directory)
    def commit_with_pending_signal(src,dst):
        signal.pthread_kill(threading.get_ident(), signal.SIGTERM)
        original(src,dst)
    try:
        with patch.object(run.os,'replace',side_effect=commit_with_pending_signal):
            run.finish_receipt(out,{'status':'complete'},time.monotonic())
    except InterruptedError:
        assert (out/'completed.json').exists()
    else:
        raise AssertionError('pending signal not delivered')
"""
        child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=10)
        self.assertEqual(child.returncode,0,child.stderr)

if __name__=='__main__': unittest.main()
