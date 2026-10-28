import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from personalized_charging.continuous_certificate_exploratory_v1.comparator import (
    benefit_service, evaluate, mixture_thresholds, point_regression_mixture,
    prefix_likelihoods, prospective_mixture,
)
from personalized_charging.p3d_diagnostic_v1.interval import I


def independent_reference(history, theta, tau):
    """High-precision point calculation independent of interval expressions."""
    with localcontext() as context:
        context.prec = 80
        theta, tau = Decimal(theta), Decimal(tau)
        logistic = lambda x: Decimal(1) / (Decimal(1) + (-x).exp())
        p = logistic((Decimal('.1') - theta) / tau)
        r = logistic((Decimal('.1') - theta / 2) / tau)
        value = Decimal(1)
        prefixes = []
        for contrast, accepted in history:
            q = p if contrast == 'p' else r
            value *= q if accepted else 1 - q
            prefixes.append(value)
        benefit = p * (Decimal('.07') - theta) + (1 - p) * r * (Decimal('.05') - theta / 2)
        service = Decimal('.005') * (p + (1 - p) * r)
        return prefixes, benefit, service


class ContinuousComparatorTests(unittest.TestCase):
    def test_arbitrary_prefixes_and_mixture_against_independent_arithmetic(self):
        history = (('p', True), ('r', False), ('p', False), ('r', True))
        mixture = (('0.5', '0', '0.05'), ('0.5', '0.2', '0.2'))
        left, _, _ = independent_reference(history, '0', '0.05')
        right, _, _ = independent_reference(history, '0.2', '0.2')
        with localcontext() as context:
            context.prec = 75
            expected = [(a + b) * Decimal('.025') for a, b in zip(left, right)]
        actual = mixture_thresholds(history, mixture)
        for interval, truth in zip(actual, expected):
            self.assertLessEqual(interval.lo, truth)
            self.assertGreaterEqual(interval.hi, truth)
        for theta, tau in (('0', '0.05'), ('0.1', '0.3'), ('0.2', '0.2')):
            exact, benefit, service = independent_reference(history, theta, tau)
            for interval, truth in zip(prefix_likelihoods(history, I(theta), I(tau)), exact):
                self.assertLessEqual(interval.lo, truth)
                self.assertGreaterEqual(interval.hi, truth)
            b, u = benefit_service(I(theta), I(tau))
            self.assertLessEqual(b.lo, benefit)
            self.assertGreaterEqual(b.hi, benefit)
            self.assertLessEqual(u.lo, service)
            self.assertGreaterEqual(u.hi, service)

    def test_prior_and_two_acceptances_have_a_negative_witness(self):
        for history in ((), (('p', True), ('r', True))):
            result = evaluate(history, mixture=point_regression_mixture())
            self.assertEqual(result['decision'], 'ABSTAIN')
            self.assertEqual(result['reason'], 'nonpositive_benefit_witness')
            self.assertEqual(result['witness'], ('0.2', '0.2'))

    def test_thirteen_acceptances_point_alternative_known_answer(self):
        history = (('p', True), ('r', True)) + (('p', True),) * 11
        result = evaluate(history, mixture=point_regression_mixture(), max_nodes=10000)
        self.assertEqual(result['decision'], 'ALLOW', result)
        self.assertGreater(Decimal(result['benefit_lower']), 0)
        self.assertLessEqual(Decimal(result['candidate_service_upper']), Decimal('.005'))

    def test_thirteen_acceptances_two_point_mixture_known_answer(self):
        # The independently derived analytic bound eliminates p<=352/525.
        self.assertGreater(Fraction(99, 100) * Fraction(21, 16) ** 12 *
                           Fraction(22, 25), 20)
        history = (('p', True), ('r', True)) + (('p', True),) * 11
        mixture = (('0.99', '0', '0.05'), ('0.01', '0.2', '0.2'))
        result = evaluate(history, mixture=mixture, max_nodes=10000)
        self.assertEqual(result['decision'], 'ALLOW', result)
        self.assertGreater(Decimal(result['benefit_lower']), 0)

    def test_box_bounds_enclose_multiple_shared_model_points(self):
        theta_box, tau_box = I('0.06', '0.12'), I('0.1', '0.3')
        history = (('p', False), ('r', True), ('p', True), ('r', False))
        bound_prefixes = prefix_likelihoods(history, theta_box, tau_box)
        b, u = benefit_service(theta_box, tau_box)
        for theta in ('0.06', '0.09', '0.12'):
            for tau in ('0.1', '0.2', '0.3'):
                prefixes, benefit, service = independent_reference(history, theta, tau)
                for interval, truth in zip(bound_prefixes, prefixes):
                    self.assertLessEqual(interval.lo, truth)
                    self.assertGreaterEqual(interval.hi, truth)
                self.assertLessEqual(b.lo, benefit)
                self.assertGreaterEqual(b.hi, benefit)
                self.assertLessEqual(u.lo, service)
                self.assertGreaterEqual(u.hi, service)

    def test_tight_service_never_uses_full_prior_bound_to_allow(self):
        history = (('p', True), ('r', True)) + (('p', True),) * 11
        result = evaluate(history, mixture=point_regression_mixture(), epsilon='0.0045')
        self.assertEqual(result['decision'], 'ABSTAIN')
        self.assertEqual(result['reason'], 'service_violation_witness')

    def test_nontrivial_mixture_and_node_limit_abstain(self):
        self.assertEqual(len(prospective_mixture()), 25)
        history = (('p', True), ('r', True)) + (('p', True),) * 11
        result = evaluate(history, mixture=prospective_mixture(), max_nodes=1)
        self.assertEqual(result['decision'], 'ABSTAIN')
        self.assertIn(result['reason'], ('nonpositive_benefit_witness', 'node_limit'))

    def test_invalid_inputs_and_nondefault_events(self):
        with self.assertRaises(ValueError):
            evaluate((('default', True),), mixture=point_regression_mixture())
        with self.assertRaises(ValueError):
            evaluate((('p', 1),), mixture=point_regression_mixture())
        with self.assertRaises(ValueError):
            evaluate((), mixture=(('0.2', '0', '0.05'),))
        with self.assertRaises(ValueError):
            evaluate((), mixture=point_regression_mixture(), epsilon=0.005)


if __name__ == '__main__':
    unittest.main()
