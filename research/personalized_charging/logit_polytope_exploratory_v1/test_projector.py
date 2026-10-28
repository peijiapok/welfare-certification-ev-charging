import unittest
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction as F

import mpmath as mp

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import theta_outer as original_outer
from personalized_charging.two_driver_exploratory_v1.gate import probability_band
from personalized_charging.logit_polytope_exploratory_v1.projector import (
    evaluate, project_bands, project_driver, vertices,
)


def prior_constraints():
    return [(-1, 0, F(-5, 2)), (1, 0, 20), (0, -1, 0), (F(-1, 4), 1, 0)]


def rounded_counts(theta, tau, shift, n):
    with localcontext() as context:
        context.prec = 80
        theta, tau, shift = Decimal(theta), Decimal(tau), Decimal(shift)
        logits = ((Decimal('.1')-theta)/tau+shift, (Decimal('.1')-theta/2)/tau+shift,
                  (Decimal('.2')-theta)/tau+shift)
        probabilities = [Decimal(1)/(Decimal(1)+(-z).exp()) for z in logits]
        return {key: (int((q*n).to_integral_value(rounding=ROUND_HALF_UP)), n)
                for key, q in zip(('p', 'r', 'third'), probabilities)}


class RationalProjectionTests(unittest.TestCase):
    def test_exact_vertices_degenerate_segment_and_point(self):
        segment = prior_constraints()+[(0, 1, F(1, 2)), (0, -1, F(-1, 2)), (1, 0, 4)]
        points = vertices(segment)
        self.assertEqual(set(points), {(F(5, 2), F(1, 2)), (F(4), F(1, 2))})
        self.assertEqual((min(v/l for l, v in points), max(v/l for l, v in points)), (F(1, 8), F(1, 5)))
        boundary = prior_constraints()+[(F(1, 4), -1, 0)]
        points = vertices(boundary)
        self.assertEqual({v/l for l, v in points}, {F(1, 4)})
        singleton = prior_constraints()+[(1, 0, 4), (-1, 0, -4), (0, 1, 1), (0, -1, -1)]
        self.assertEqual(vertices(singleton), ((F(4), F(1)),))

    def test_no_one_sided_and_unsampled_bounds_remain_valid(self):
        cases = (
            {'p': ['0', '1'], 'r': ['0', '1'], 'third': ['0', '1']},
            {'p': ['0', '.6'], 'r': ['0', '1'], 'third': ['0', '1']},
            {'p': ['.4', '1'], 'r': ['0', '1'], 'third': ['0', '1']},
        )
        for bands in cases:
            result = project_bands(bands, method='three')
            self.assertEqual(result['status'], 'PROJECTED', result)
            self.assertEqual(list(map(Decimal, result['theta_outer'])), [Decimal(0), Decimal('.25')])
            self.assertIn('h', result['witness'])
        missing = {'p': (0, 0), 'r': (0, 0), 'third': (0, 0)}
        result = project_driver(missing, method='three')
        self.assertEqual(result['status'], 'PROJECTED', result)
        self.assertEqual(list(map(Decimal, result['theta_outer'])), [Decimal(0), Decimal('.25')])

    def test_cross_constraint_tightens_and_witness_is_feasible(self):
        bands = {'p': ['0', '.55'], 'r': ['.6', '1'], 'third': ['0', '1']}
        result = project_bands(bands, method='three')
        self.assertEqual(result['status'], 'PROJECTED', result)
        self.assertGreater(Decimal(result['theta_outer'][0]), 0)
        witness = {key: F(value) for key, value in result['witness'].items()}
        self.assertTrue(F(5, 2) <= witness['lambda'] <= 20)
        self.assertTrue(0 <= witness['theta'] <= F(1, 4))
        self.assertEqual(witness['theta'], witness['v']/witness['lambda'])
        with mp.workdps(80):
            h = mp.mpf(witness['h'].numerator)/witness['h'].denominator
            lam = mp.mpf(witness['lambda'].numerator)/witness['lambda'].denominator
            v = mp.mpf(witness['v'].numerator)/witness['v'].denominator
            for key, z in (('p', h), ('r', h+v/2), ('third', h+lam/10)):
                q = 1/(1+mp.exp(-z))
                self.assertLessEqual(mp.mpf(bands[key][0]), q)
                self.assertGreaterEqual(mp.mpf(bands[key][1]), q)

    def test_correlated_projection_is_inside_naive_outer(self):
        bands = {'p': ['.55', '.60'], 'r': ['.60', '.65'], 'third': ['.68', '.74']}
        result = project_bands(bands, method='three')
        self.assertEqual(result['status'], 'PROJECTED', result)
        old = original_outer({key: I(*value) for key, value in bands.items()})
        new_lo, new_hi = map(Decimal, result['theta_outer'])
        self.assertGreaterEqual(new_lo, old.lo)
        self.assertLessEqual(new_hi, old.hi)

    def test_conflicting_and_invalid_bands_abstain(self):
        data = {'p': ['.8', '.9'], 'r': ['.1', '.2'], 'third': ['.8', '.9']}
        self.assertEqual(project_bands(data, method='three')['reason'], 'empty_outer')
        for value in (['0', '0'], ['1', '1'], ['.7', '.2'], ['NaN', '.5'], ['-.1', '.5']):
            bad = {'p': value, 'r': ['0', '1'], 'third': ['0', '1']}
            self.assertEqual(project_bands(bad, method='three')['status'], 'ABSTAIN')
        bad = {'p': (2, 1), 'r': (0, 0), 'third': (0, 0)}
        self.assertEqual(project_driver(bad, method='three')['status'], 'ABSTAIN')

    def test_shared_alpha_bands_and_unverified_witness(self):
        counts = {'p': (60, 100), 'r': (65, 100), 'third': (70, 100)}
        result = project_driver(counts, method='three')
        self.assertEqual(result['status'], 'PROJECTED', result)
        for key, (successes, total) in counts.items():
            self.assertEqual(result['bands'][key], probability_band(successes, total)[0].json())
        # Feasibility of a rounded outer polytope is not itself a witness for
        # an exact singleton band: the directed probability check must pass.
        exact = {'p': ['.5', '.5'], 'r': ['.5', '.5'], 'third': ['.6', '.6']}
        self.assertEqual(project_bands(exact, method='three')['reason'], 'unverified_feasibility')
        for bad in ({'p': (True, 1), 'r': (0, 0)}, {'p': (0, 10**12+1), 'r': (0, 0)}):
            self.assertEqual(project_driver(bad, method='two')['status'], 'ABSTAIN')

    def test_two_driver_ab_gate_and_service(self):
        data = {'A': rounded_counts('.02', '.2', '.2', 10**10),
                'B': rounded_counts('.04', '.15', '-.1', 10**10)}
        physics = dict(g0='.8', g1='.7', g2='.4', W='20', delta='.005', epsilon='.005')
        for method in ('two', 'three'):
            result = evaluate(data, method=method, **physics)
            self.assertEqual(result['decision'], 'ALLOW', result)
            self.assertGreater(Decimal(result['benefit_interval'][0]), 0)
            self.assertLessEqual(Decimal(result['candidate_service_upper']), Decimal('.005'))
            result = evaluate(data, method=method, **dict(physics, epsilon='0'))
            self.assertEqual(result['decision'], 'ABSTAIN')
            self.assertEqual(result['reason'], 'service_not_certified')
        invalid = dict(data, true_theta='.02')
        self.assertEqual(evaluate(invalid, method='two', **physics)['decision'], 'ABSTAIN')


if __name__ == '__main__':
    unittest.main()
