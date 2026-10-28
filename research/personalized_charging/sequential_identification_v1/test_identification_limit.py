"""Controls for the post-run observational-equivalence construction."""
from fractions import Fraction as Q
import math
import unittest

from personalized_charging.sequential_identification_v1.physical import simulate_episode


class IdentificationLimitTests(unittest.TestCase):
    def test_exact_logits_and_welfare_increment_signs(self):
        theta_a, tau_a, shift = Q(2, 25), Q(1, 5), Q(1, 5)
        theta_b, tau_b = Q(2, 35), Q(1, 7)
        a = ((Q(1, 10)-theta_a)/tau_a+shift,
             (Q(1, 10)-theta_a/2)/tau_a+shift)
        b = ((Q(1, 10)-theta_b)/tau_b,
             (Q(1, 10)-theta_b/2)/tau_b)
        self.assertEqual(a, (Q(3, 10), Q(1, 2)))
        self.assertEqual(a, b)
        self.assertEqual((Q(7, 100)-theta_a, Q(1, 20)-theta_a/2), (-Q(1, 100), Q(1, 100)))
        self.assertEqual((Q(7, 100)-theta_b, Q(1, 20)-theta_b/2), (Q(9, 700), Q(3, 140)))
        p, r = (1/(1+math.exp(-float(x))) for x in a)
        benefit_a = (-p+(1-p)*r)/100
        benefit_b = p*float(Q(9,700))+(1-p)*r*float(Q(3,140))
        self.assertLess(benefit_a, 0)
        self.assertGreater(benefit_b, 0)
        self.assertLess((p+(1-p)*r)/200, .005)

    def test_hypothetical_additional_price_breaks_this_pair(self):
        offer = Q(1, 5)
        a = (offer-Q(2, 25))/Q(1, 5)+Q(1, 5)
        b = (offer-Q(2, 35))/Q(1, 7)
        self.assertEqual((a, b), (Q(4, 5), Q(1)))
        self.assertNotEqual(a, b)

    def test_three_contrast_inverse_exact_rationals(self):
        theta, tau, bias = Q(2, 25), Q(1, 5), Q(1, 5)
        designs = ((Q(1, 10), Q(1)), (Q(1, 10), Q(1, 2)), (Q(1, 5), Q(1)))
        l1, l2, l3 = tuple((x-theta*d)/tau+bias for x, d in designs)
        lam = 10*(l3-l1)
        recovered_theta = 2*(l2-l1)/lam
        recovered_bias = l1-lam*(Q(1, 10)-recovered_theta)
        self.assertEqual((1/lam, recovered_theta, recovered_bias), (tau, theta, bias))

    def test_sharp_parameter_set_boundaries_and_ambiguous_example(self):
        bounds = lambda k: (k/20, min(2*k/5, Q(1, 4)))
        self.assertEqual(bounds(Q(0)), (Q(0), Q(0)))
        self.assertEqual(bounds(Q(5)), (Q(1, 4), Q(1, 4)))
        low, high = bounds(Q(2, 5))
        self.assertEqual((low, high), (Q(1, 50), Q(4, 25)))
        p, r = 1/(1+math.exp(-.3)), 1/(1+math.exp(-.5))
        a = .07*p+.05*(1-p)*r
        d = p+(1-p)*r/2
        self.assertLess(a-d*float(high), 0)
        self.assertGreater(a-d*float(low), 0)
        self.assertAlmostEqual(a-d*float(high), -.0596466, places=6)
        self.assertAlmostEqual(a-d*float(low), .0393178, places=6)

    def test_hypothetical_two_model_information_numbers(self):
        a, b = 1/(1+math.exp(-.8)), 1/(1+math.exp(-1.))
        kl = lambda x, y: x*math.log(x/y)+(1-x)*math.log((1-x)/(1-y))
        required_mean = kl(.05, .8)/kl(a, b)
        sufficient_fixed = math.ceil(2*math.log(20)/(b-a)**2)
        self.assertAlmostEqual(required_mean, 322.02774519669, places=8)
        self.assertEqual(sufficient_fixed, 3550)
        self.assertLess(math.exp(-sufficient_fixed*(b-a)**2/2), .05)

    def test_physical_observables_match_despite_different_hidden_loss(self):
        p, r = 1/(1+math.exp(-.3)), 1/(1+math.exp(-.5))
        saw_distinct_loss = False
        for policy in ("baseline", "collect_p", "collect_r", "candidate"):
            for up in (.1, .6, .99):
                for ur in (.1, .7, .99):
                    for urgent in (0., .5):
                        a = simulate_episode(policy, .08, .2, up, ur, urgent,
                                             p_response=p, r_response=r)
                        b = simulate_episode(policy, float(Q(2,35)), float(Q(1,7)),
                                             up, ur, urgent, p_response=p, r_response=r)
                        self.assertEqual(a.events, b.events)
                        self.assertEqual(a.unmet_kwh, b.unmet_kwh)
                        saw_distinct_loss |= a.loss != b.loss
        self.assertTrue(saw_distinct_loss)


if __name__ == "__main__":
    unittest.main()
