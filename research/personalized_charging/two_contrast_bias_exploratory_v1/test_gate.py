import unittest
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import (
    MAX_COUNT, benefit_service_bounds, evaluate as three_evaluate,
)
from personalized_charging.two_contrast_bias_exploratory_v1.gate import evaluate


def deterministic_counts(theta, tau, shift, n):
    """Rounded population expectations for deterministic controls only."""
    with localcontext() as context:
        context.prec = 80
        theta, tau, shift = Decimal(theta), Decimal(tau), Decimal(shift)
        logits = ((Decimal('.1')-theta)/tau+shift,
                  (Decimal('.1')-theta/2)/tau+shift,
                  (Decimal('.2')-theta)/tau+shift)
        probs = [Decimal(1)/(Decimal(1)+(-x).exp()) for x in logits]
        counts = {key: (int((q*n).to_integral_value(rounding=ROUND_HALF_UP)), n)
                  for key, q in zip(('p', 'r', 'third'), probs)}
        benefit = probs[0]*(Decimal('.07')-theta)+(1-probs[0])*probs[1]*(Decimal('.05')-theta/2)
        unmet = Decimal('.005')*(probs[0]+(1-probs[0])*probs[1])
        return counts, benefit, unmet


def first_two(counts):
    return {key: counts[key] for key in ('p', 'r')}


class TwoContrastBiasTests(unittest.TestCase):
    def test_observationally_equivalent_worlds_never_gain_false_certainty(self):
        with localcontext() as context:
            context.prec = 80
            for n in (10**6, 10**9, MAX_COUNT):
                a, benefit_a, _ = deterministic_counts('.08', '.2', '.2', n)
                b, benefit_b, _ = deterministic_counts(Decimal(2)/35, Decimal(1)/7, 0, n)
                self.assertEqual(first_two(a), first_two(b))
                self.assertLess(benefit_a, 0)
                self.assertGreater(benefit_b, 0)
                decision = evaluate(first_two(a))
                self.assertEqual(decision['decision'], 'ABSTAIN', decision)
                self.assertEqual(decision['reason'], 'benefit_not_positive')
                self.assertLess(Decimal(decision['benefit_interval'][0]), 0)
                self.assertGreater(Decimal(decision['benefit_interval'][1]), 0)
                self.assertLessEqual(Decimal(decision['theta_outer'][0]), Decimal('.02'))
                self.assertGreaterEqual(Decimal(decision['theta_outer'][1]), Decimal('.16'))

    def test_easy_positive_and_tight_service(self):
        counts, benefit, unmet = deterministic_counts('.01', '.2', '.2', 10**11)
        decision = evaluate(first_two(counts))
        self.assertGreater(benefit, 0)
        self.assertEqual(decision['decision'], 'ALLOW', decision)
        self.assertLessEqual(Decimal(decision['benefit_interval'][0]), benefit)
        self.assertGreaterEqual(Decimal(decision['candidate_service_upper']), unmet)
        tight = evaluate(first_two(counts), epsilon='0.004')
        self.assertGreater(unmet, Decimal('.004'))
        self.assertEqual(tight['decision'], 'ABSTAIN')
        self.assertEqual(tight['reason'], 'service_not_certified')

    def test_central_witness_is_required_and_prior_enforced(self):
        data = {'p': (5000, 10000), 'r': (4900, 10000)}
        self.assertEqual(evaluate(data)['reason'], 'central_witness_not_verified')
        conflict = {'p': (800000, 1000000), 'r': (200000, 1000000)}
        self.assertEqual(evaluate(conflict)['reason'], 'empty_outer')
        data = {'p': (0, 0), 'r': (0, 0)}
        self.assertEqual(evaluate(data)['reason'], 'missing_contrast')
        data = {'p': (1, 1), 'r': (1, 1)}
        self.assertEqual(evaluate(data)['reason'], 'noninterior_probability_band')

    def test_corner_signs_and_invalid_counts(self):
        benefit, service = benefit_service_bounds(I('0.4', '0.6'), I('0.4', '0.7'), I('0.1', '0.2'))
        self.assertLessEqual(benefit.lo, Decimal('-.092'))
        self.assertGreaterEqual(service, Decimal('.0044'))
        for data in ({'p': (True, 4), 'r': (1, 4)},
                     {'p': (4, 3), 'r': (1, 4)},
                     {'p': (0, MAX_COUNT+1), 'r': (1, 4)},
                     {'p': (1, 4), 'r': (1, 4), 'true_theta': .1}):
            self.assertEqual(evaluate(data)['reason'], 'invalid_input')
        self.assertEqual(evaluate({'p': (1, 4), 'r': (1, 4)}, epsilon=0.005)['reason'], 'invalid_input')

    def test_common_bands_and_alpha_accounting_with_three_contrasts(self):
        counts, _, _ = deterministic_counts('.01', '.2', '.2', 10**11)
        two = evaluate(first_two(counts))
        three = three_evaluate(counts)
        self.assertEqual(two['decision'], 'ALLOW', two)
        self.assertEqual(three['decision'], 'ALLOW', three)
        self.assertEqual(two['bands']['p'], three['bands']['p'])
        self.assertEqual(two['bands']['r'], three['bands']['r'])
        for n in (1, 20, 1000):
            spent_one = sum((Fraction(1, 60*k*(k+1)) for k in range(1, n+1)), Fraction())
            self.assertLessEqual(3 * spent_one, Fraction(1, 20))


if __name__ == '__main__':
    unittest.main()
