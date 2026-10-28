import unittest
from decimal import Decimal, localcontext, ROUND_HALF_UP
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import (
    MAX_COUNT, benefit_service_bounds, evaluate, logit, probability_band, radius_upper,
)


def deterministic_counts(theta, tau, shift, n, third_shift_extra=Decimal(0)):
    """Rounded ideal probabilities, purely deterministic known-answer inputs."""
    with localcontext() as context:
        context.prec = 80
        theta, tau, shift = Decimal(theta), Decimal(tau), Decimal(shift)
        logits = ((Decimal('.1')-theta)/tau+shift,
                  (Decimal('.1')-theta/2)/tau+shift,
                  (Decimal('.2')-theta)/tau+shift+third_shift_extra)
        probs = [Decimal(1)/(Decimal(1)+(-x).exp()) for x in logits]
        counts = {key: (int((q*n).to_integral_value(rounding=ROUND_HALF_UP)), n)
                  for key, q in zip(('p', 'r', 'third'), probs)}
        benefit = probs[0]*(Decimal('.07')-theta)+(1-probs[0])*probs[1]*(Decimal('.05')-theta/2)
        service = Decimal('.005')*(probs[0]+(1-probs[0])*probs[1])
        return counts, probs, benefit, service


class ThreeContrastTests(unittest.TestCase):
    def test_alpha_telescoping(self):
        for n in (1, 10, 1000):
            probability = sum((Fraction(1, 60*k*(k+1)) for k in range(1, n+1)), Fraction())
            self.assertEqual(probability, Fraction(n, 60*(n+1)))
            self.assertLess(3 * probability, Fraction(1, 20))

    def test_radius_probability_and_logit_outward_enclosures(self):
        with localcontext() as context:
            context.prec = 80
            for n in (1, 100, 10**6, MAX_COUNT):
                exact = (Decimal(120*n*(n+1)).ln()/Decimal(2*n)).sqrt()
                self.assertGreaterEqual(radius_upper(n), exact)
            for s, n in ((1, 3), (21, 100), (7201, 10000)):
                band, mean = probability_band(s, n)
                value = Decimal(s)/n
                self.assertLessEqual(mean.lo, value)
                self.assertGreaterEqual(mean.hi, value)
                self.assertLessEqual(band.lo, value)
                self.assertGreaterEqual(band.hi, value)
            for q in ('0.01', '0.3', '0.5', '0.99'):
                qd = Decimal(q)
                exact = (qd/(1-qd)).ln()
                interval = logit(I(q))
                self.assertLessEqual(interval.lo, exact)
                self.assertGreaterEqual(interval.hi, exact)

    def test_missing_noninterior_invalid_and_huge_counts(self):
        self.assertEqual(evaluate({'p': (0, 0), 'r': (0, 0), 'third': (0, 0)})['reason'], 'missing_contrast')
        self.assertEqual(evaluate({'p': (1, 1), 'r': (1, 1), 'third': (1, 1)})['reason'], 'noninterior_probability_band')
        for bad in ({'p': (True, 5), 'r': (1, 5), 'third': (1, 5)},
                    {'p': (2, 1), 'r': (1, 5), 'third': (1, 5)},
                    {'p': (0, MAX_COUNT+1), 'r': (1, 5), 'third': (1, 5)}):
            with self.assertRaises(ValueError):
                evaluate(bad)
        with self.assertRaises(ValueError):
            evaluate({'p': (1, 10), 'r': (1, 10), 'third': (1, 10)}, epsilon=0.005)

    def test_central_witness_must_be_certified(self):
        data = {'p': (5000, 10000), 'r': (4900, 10000), 'third': (6000, 10000)}
        self.assertEqual(evaluate(data)['reason'], 'central_witness_not_verified')
        # A strict q3<q1 conflict cannot support a positive inverse temperature.
        data = {'p': (800000, 1000000), 'r': (810000, 1000000),
                'third': (200000, 1000000)}
        self.assertEqual(evaluate(data)['reason'], 'empty_or_nonpositive_outer')

    def test_four_corners_with_negative_coefficients_and_service(self):
        benefit, service = benefit_service_bounds(I('0.4', '0.6'), I('0.4', '0.7'), I('0.1', '0.2'))
        self.assertLessEqual(benefit.lo, Decimal('-.092'))
        self.assertGreaterEqual(service, Decimal('.0044'))
        self.assertLessEqual(service, Decimal('.005'))

    def test_fixed_adverse_and_beneficial_common_shift_models(self):
        n = 10**11
        with localcontext() as context:
            context.prec = 80
            models = ((Decimal('.08'), Decimal('.2'), Decimal('.2')),
                      (Decimal(2)/35, Decimal(1)/7, Decimal(0)),
                      (Decimal('.02'), Decimal('.2'), Decimal('1')))
            for index, (theta, tau, shift) in enumerate(models):
                data, probs, actual_b, actual_u = deterministic_counts(theta, tau, shift, n)
                result = evaluate(data)
                self.assertIn('central_witness', result, result)
                self.assertLessEqual(Decimal(result['theta_outer'][0]), theta)
                self.assertGreaterEqual(Decimal(result['theta_outer'][1]), theta)
                self.assertLessEqual(Decimal(result['benefit_interval'][0]), actual_b)
                self.assertGreaterEqual(Decimal(result['benefit_interval'][1]), actual_b)
                self.assertGreaterEqual(Decimal(result['candidate_service_upper']), actual_u)
                if index == 0:
                    self.assertLess(actual_b, 0)
                    self.assertLess(Decimal(result['benefit_interval'][1]), 0)
                    self.assertEqual(result['decision'], 'ABSTAIN')
                else:
                    self.assertGreater(actual_b, 0)
                    self.assertEqual(result['decision'], 'ALLOW', result)

    def test_tight_service_abstention(self):
        data, _, _, service = deterministic_counts('.02', '.2', '1', 10**11)
        self.assertGreater(service, Decimal('.004'))
        result = evaluate(data, epsilon='0.004')
        self.assertEqual(result['decision'], 'ABSTAIN')
        self.assertEqual(result['reason'], 'service_not_certified')

    def test_contrast_specific_shift_is_not_detectable_from_three_counts(self):
        with localcontext() as context:
            context.prec = 80
            a, _, benefit_a, _ = deterministic_counts('.08', '.2', '.2', 10**11, Decimal('.2'))
            b, _, benefit_b, _ = deterministic_counts(Decimal(2)/35, Decimal(1)/7, 0, 10**11)
        self.assertEqual(a, b)
        self.assertLess(benefit_a, 0)
        self.assertGreater(benefit_b, 0)
        # The gate assumes a common shift and cannot detect this violation.
        self.assertEqual(evaluate(a)['decision'], 'ALLOW')


if __name__ == '__main__':
    unittest.main()
