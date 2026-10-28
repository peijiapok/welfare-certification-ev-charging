import itertools
import math
import unittest
from collections import Counter
from fractions import Fraction

from personalized_charging.sequential_identification_v1.certificate import (
    BENEFIT_LOWER_BOUND,
    SERVICE_UPPER_BOUND,
    PProbeCertificate,
    _strict_crossing,
    likelihoods,
)


class ExactCertificateTests(unittest.TestCase):
    def test_empty_counts_and_zero_power(self):
        self.assertEqual(likelihoods(0, 0), (Fraction(1), Fraction(1)))
        self.assertEqual(likelihoods(0, 3), (Fraction(3, 25) ** 3, Fraction(1)))
        self.assertFalse(PProbeCertificate().evaluate(SERVICE_UPPER_BOUND).certified)

    def test_independent_integer_formula(self):
        # Derive both likelihoods from integer numerators and denominators,
        # independently of the implementation's Fraction-based q calculation.
        for n in range(1, 17):
            for s in range(n + 1):
                f = n - s
                num, den = (s, n) if 3 * s <= 2 * n else (2, 3)
                alternative = Fraction(22 ** s * 3 ** f, 25 ** n)
                null_maximum = Fraction(num ** s * (den - num) ** f, den ** n)
                self.assertEqual(likelihoods(s, f), (alternative, null_maximum))
                integer_test = 22 ** s * 3 ** f * den ** n > (
                    20 * 25 ** n * num ** s * (den - num) ** f
                )
                self.assertEqual(_strict_crossing(*likelihoods(s, f)), integer_test)

    def test_strict_threshold(self):
        null = Fraction(1, 7)
        self.assertFalse(_strict_crossing(20 * null, null))
        self.assertFalse(_strict_crossing(20 * null - Fraction(1, 10**20), null))
        self.assertTrue(_strict_crossing(20 * null + Fraction(1, 10**20), null))

    def test_sequential_stopping_r_feedback_and_service(self):
        gate = PProbeCertificate()
        for i in range(11):
            # These choices depend on the observed history; r is not evidence
            # for this one-contrast certificate.
            gate.observe("p", True)
            gate.observe("r", i % 2 == 0)
            decision = gate.evaluate(SERVICE_UPPER_BOUND)
            self.assertEqual(decision.certified, i == 10)
        self.assertEqual((gate.accepts, gate.rejects), (11, 0))
        self.assertEqual(decision.benefit_strictly_above, BENEFIT_LOWER_BOUND)
        tight = gate.evaluate(Fraction(1, 201))
        self.assertTrue(tight.p_excluded)
        self.assertFalse(tight.service_sufficient)
        self.assertFalse(tight.certified)
        self.assertIsNone(tight.benefit_strictly_above)
        # A prefix decision is not latched; an actual stopping controller must
        # preserve the earlier decision when it stops at that prefix.
        gate.observe("p", False)
        self.assertFalse(gate.evaluate(SERVICE_UPPER_BOUND).certified)

    def test_exact_short_horizon_anytime_null_calibration(self):
        horizon = 12
        crossed_by_final_accepts = Counter()
        thresholds = {
            (s, f): _strict_crossing(*likelihoods(s, f))
            for s in range(horizon + 1)
            for f in range(horizon + 1 - s)
        }
        for history in itertools.product((False, True), repeat=horizon):
            s = f = 0
            crossed = False
            for outcome in history:
                s += outcome
                f += not outcome
                crossed |= thresholds[s, f]
            if crossed:
                crossed_by_final_accepts[s] += 1
        self.assertGreater(sum(crossed_by_final_accepts.values()), 0)
        for p in (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(2, 3)):
            crossing_probability = sum(
                count * p ** s * (1 - p) ** (horizon - s)
                for s, count in crossed_by_final_accepts.items()
            )
            self.assertLessEqual(crossing_probability, Fraction(1, 20))

    def test_beneficial_low_p_model_is_in_null(self):
        # Independent arithmetic at theta=0, tau=0.4 under the P3c formulas.
        p = 1 / (1 + math.exp(-0.25))
        r = p
        benefit = p * 0.07 + (1 - p) * r * 0.05
        self.assertLess(p, 2 / 3)
        self.assertGreater(benefit, 0)
        # A null model can still have positive benefit. The test therefore
        # cannot be interpreted as a complete test for policy benefit.

    def test_invalid_inputs_and_exact_service_units(self):
        for s, f in ((-1, 0), (0, -1), (True, 0), (0, 1.0)):
            with self.assertRaises(ValueError):
                likelihoods(s, f)
        gate = PProbeCertificate()
        with self.assertRaises(ValueError):
            gate.observe("default", True)
        with self.assertRaises(ValueError):
            gate.observe("p", 1)
        for epsilon in (0.005, True, Fraction(-1, 200)):
            with self.assertRaises(ValueError):
                gate.evaluate(epsilon)


if __name__ == "__main__":
    unittest.main()
