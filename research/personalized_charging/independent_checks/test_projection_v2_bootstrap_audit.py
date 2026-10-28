"""Analytic fixtures for the post-completion audit; no scientific RNG."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from personalized_charging.independent_checks import projection_v2_bootstrap_audit as check


class AuditTests(unittest.TestCase):
    def test_exact_analytic_bootstrap_control(self):
        rows=[{'methods':{'a':{'lifecycle_gain':a,'stop_lifecycle_gain':2*a,'certified':ca},
                          'b':{'lifecycle_gain':0,'stop_lifecycle_gain':0,'certified':False}}}
              for a,ca in ((0.,False),(2.,True))]
        indices=np.array([[0,0],[0,1],[1,1]])
        result=check.paired_metrics(rows,'a','b',indices)
        self.assertEqual(result['mean'],1.)
        self.assertEqual(result['certified_difference'],.5)
        self.assertEqual(result['stop_gain_difference'],2.)
        self.assertEqual(result['bootstrap_95'],[.05,1.95])
        self.assertEqual(result['certified_bootstrap_95'],[.025,.975])
        self.assertEqual(result['stop_gain_bootstrap_95'],[.1,3.9])
        self.assertEqual(len(set(check.comparisons())),22)

    def test_incomplete_refused_before_any_random_generator(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(check.np.random,'Generator',side_effect=AssertionError('must not generate')):
                with self.assertRaisesRegex(ValueError,'no completion receipt'):
                    check.audit(directory)
            Path(directory,'completed.json').write_text('{"status":"incomplete"}')
            with patch.object(check.np.random,'Generator',side_effect=AssertionError('must not generate')):
                with self.assertRaisesRegex(ValueError,'incomplete receipt'):
                    check.audit(directory)


if __name__=='__main__': unittest.main()
