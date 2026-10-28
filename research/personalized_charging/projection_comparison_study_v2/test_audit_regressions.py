"""Independent regressions for projection and completion-receipt integrity."""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import subprocess
import sys
import tempfile
import time
import unittest

from personalized_charging.projection_comparison_study_v2 import run
from personalized_charging.logit_polytope_exploratory_v1.projector import project_driver

PHYS=dict(g0='.568',g1='.548',g2='.4',delta='.005',W='20',epsilon='.005')
COUNTS={d:{o:(0,0) for o in ('p','r','third')} for d in ('A','B')}

class ProjectionOutputControls(unittest.TestCase):
    def test_fabricated_favorable_without_witness_fails(self):
        bad=dict(decision='ALLOW',reason='outward_bounds',benefit_interval=['.1','.2'],candidate_service_upper='.005')
        with patch.object(run,'projection_evaluate',return_value=bad):
            with self.assertRaises(ValueError):run.call_gate(COUNTS,'projection_three',PHYS)

    def test_unresolved_requires_valid_projected_sides_and_actual_failure(self):
        p=project_driver(COUNTS['A'],method='three')
        self.assertEqual(p['status'],'PROJECTED')
        bad=dict(decision='ABSTAIN',reason='projection_unresolved',projections={'A':p,'B':p})
        with patch.object(run,'projection_evaluate',return_value=bad):
            with self.assertRaises(ValueError):run.call_gate(COUNTS,'projection_three',PHYS)
        altered=deepcopy(p);altered.pop('witness')
        bad=dict(decision='ABSTAIN',reason='projection_unresolved',
                 projections={'A':altered,'B':dict(status='ABSTAIN',reason='empty_outer')})
        with patch.object(run,'projection_evaluate',return_value=bad):
            with self.assertRaises(ValueError):run.call_gate(COUNTS,'projection_three',PHYS)

    def test_timeout_and_signal_before_commit_leave_no_receipt(self):
        for error in (TimeoutError('alarm'),InterruptedError('SIGTERM')):
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory)
                with patch.object(run,'write_json',side_effect=error):
                    with self.assertRaises(type(error)):run.finish_receipt(out,{'status':'complete'},time.monotonic())
                self.assertFalse((out/'completed.json').exists())
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            with self.assertRaises(TimeoutError):run.finish_receipt(out,{'status':'complete'},time.monotonic()-601)
            self.assertFalse((out/'completed.json').exists())

    def test_pending_signal_at_atomic_commit_is_explicitly_committed(self):
        code="""
import os, signal, tempfile, time, threading
from pathlib import Path
from unittest.mock import patch
from personalized_charging.projection_comparison_study_v2 import run

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
