"""Independent tiny exact-probability audit; never runs the study catalog.

This test does not import the prospective runner or any decision gate. It
compares exact branch enumeration against the proposed aggregate law and
against the separately implemented physical episode model.
"""
from collections import defaultdict
from fractions import Fraction as F
from itertools import product
from math import comb
import unittest

from personalized_charging.sequential_identification_v1.physical import simulate_episode


Q = F(3, 7)
DELTA = F(1, 200)
THETA = F(2, 25)


def bernoulli_mass(value, probability):
    return probability if value else 1 - probability


def branch_mass(branch):
    weight = F(1)
    for accepted, urgent in branch:
        weight *= bernoulli_mass(accepted, Q) * bernoulli_mass(urgent, DELTA)
    return weight


def totals(branch):
    k = sum(accepted for accepted, _ in branch)
    u = sum(accepted and urgent for accepted, urgent in branch)
    v = sum(not accepted and urgent for accepted, urgent in branch)
    return k, u, v


def binomial_mass(successes, total, probability):
    return (comb(total, successes) * probability ** successes *
            (1 - probability) ** (total - successes))


def branches(m):
    # Full sequence is independently constructed; no aggregate runner is used.
    return product(product((False, True), repeat=2), repeat=m)


class IndependentAggregateAudit(unittest.TestCase):
    def test_exact_joint_law_matches_conditional_binomials(self):
        for m in (2, 3):
            with self.subTest(episodes=m):
                exhaustive = defaultdict(F)
                for branch in branches(m):
                    exhaustive[totals(branch)] += branch_mass(branch)
                self.assertEqual(sum(exhaustive.values()), 1)
                for k in range(m + 1):
                    for u in range(k + 1):
                        for v in range(m - k + 1):
                            expected = (binomial_mass(k, m, Q) *
                                        binomial_mass(u, k, DELTA) *
                                        binomial_mass(v, m - k, DELTA))
                            self.assertEqual(exhaustive[(k, u, v)], expected,
                                             (m, k, u, v))

    def test_each_weighted_branch_matches_physical_and_welfare_ledger(self):
        # In the physical module, the third offer is the same first-request
        # slot-2 reservation, with its distinct response law supplied explicitly.
        # Its promotional price is a transfer between operator and driver;
        # it changes choice probabilities but cancels in their combined ledger.
        scenarios = (
            ('p', 'collect_p', F(42, 250), F(1), F(2, 5)),
            ('r', 'collect_r', F(37, 250), F(1, 2), F(2, 5)),
            ('third', 'collect_p', F(42, 250), F(1), F(3, 10)),
        )
        for m in (2, 3):
            for label, policy, procurement_saving, delay_hours, accepted_price in scenarios:
                with self.subTest(episodes=m, contrast=label):
                    total_mass = F(0)
                    weighted_benefit = 0.0
                    weighted_unmet = 0.0
                    for branch in branches(m):
                        weight = branch_mass(branch)
                        total_mass += weight
                        k, u, _ = totals(branch)
                        paired = 0.0
                        unmet = 0.0
                        for accepted, urgent in branch:
                            # 0 is always below 3/7; .999 is always above it.
                            response_draw = 0.0 if accepted else .999
                            urgent_draw = 0.0 if urgent else .999
                            up = response_draw if policy == 'collect_p' else .314
                            ur = response_draw if policy == 'collect_r' else .314
                            model_args = (float(THETA), .2, up, ur, urgent_draw)
                            selected = simulate_episode(policy, *model_args,
                                                        p_response=float(Q), r_response=float(Q))
                            baseline = simulate_episode('baseline', *model_args,
                                                        p_response=float(Q), r_response=float(Q))
                            exposed = [event for event in selected.events if event.offer is not None]
                            self.assertEqual(len(exposed), 1)
                            self.assertIs(exposed[0].accepted, accepted)
                            self.assertEqual([e for e in baseline.events if e.offer is not None], [])
                            paired += baseline.loss - selected.loss
                            unmet += selected.unmet_kwh

                            # Equal-weight combined accounts cancel retail payment.
                            retail = accepted_price if accepted else F(1, 2)
                            operator_revenue = retail
                            driver_payment = -retail
                            self.assertEqual(operator_revenue + driver_payment, 0)
                        expected = k * (procurement_saving - delay_hours * THETA) - F(98, 5) * u
                        self.assertAlmostEqual(paired, float(expected), places=11)
                        self.assertEqual(unmet, float(u))
                        weighted_benefit += float(weight) * paired
                        weighted_unmet += float(weight) * unmet
                    self.assertEqual(total_mass, 1)
                    exact_expected = m * Q * (procurement_saving - delay_hours * THETA - F(98, 5) * DELTA)
                    self.assertAlmostEqual(weighted_benefit, float(exact_expected), places=11)
                    self.assertAlmostEqual(weighted_unmet, float(m * Q * DELTA), places=12)


if __name__ == '__main__':
    unittest.main()
