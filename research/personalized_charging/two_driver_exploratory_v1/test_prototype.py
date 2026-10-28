import math
import unittest
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import radius_upper as old_radius
from personalized_charging.two_driver_exploratory_v1.gate import (
    benefit_service_bounds, evaluate, prior_only, radius_upper,
)
from personalized_charging.two_driver_exploratory_v1.physical import simulate
from personalized_charging.two_driver_exploratory_v1.schedule import plan, prior_plan
from personalized_charging.variable_physics_exploratory_v1.gate import coefficients


def counts(theta, tau, shift, n):
    with localcontext() as context:
        context.prec = 80
        theta, tau, shift = Decimal(theta), Decimal(tau), Decimal(shift)
        logits = ((Decimal('.1')-theta)/tau+shift, (Decimal('.1')-theta/2)/tau+shift,
                  (Decimal('.2')-theta)/tau+shift)
        probabilities = [Decimal(1)/(Decimal(1)+(-value).exp()) for value in logits]
        return ({key: (int((value*n).to_integral_value(rounding=ROUND_HALF_UP)), n)
                 for key, value in zip(('p', 'r', 'third'), probabilities)}, probabilities)


class TwoDriverTests(unittest.TestCase):
    def test_six_stream_alpha_and_outward_radius(self):
        for n in (1, 100, 10**6, 10**12):
            with localcontext() as context:
                context.prec = 80
                reference = (Decimal(240*n*(n+1)).ln()/Decimal(2*n)).sqrt()
            self.assertGreaterEqual(radius_upper(n), reference)
            self.assertGreater(radius_upper(n), old_radius(n))
        self.assertEqual(6*Fraction(1, 120), Fraction(1, 20))
        self.assertEqual(4*Fraction(1, 120), Fraction(1, 30))

    def test_six_cycle_exogenous_roles_and_single_step_difference(self):
        natural = [plan(i, 'natural') for i in range(6)]
        forced = [plan(i, 'forced') for i in range(6)]
        self.assertEqual(natural, [('AB', 'first_p'), ('BA', 'second_r'), ('AB', 'first_third'),
                                   ('BA', 'first_p'), ('AB', 'candidate'), ('BA', 'first_third')])
        self.assertEqual([i for i in range(6) if natural[i] != forced[i]], [4])
        self.assertEqual(forced[4], ('AB', 'second_r'))
        self.assertEqual([prior_plan(i, True) for i in range(2)], [('AB', 'candidate'), ('BA', 'baseline')])
        self.assertEqual(prior_plan(0, False), ('AB', 'baseline'))
        self.assertEqual(plan(6, 'natural'), natural[0])

    def test_suppressed_feedback_and_role_specific_delay(self):
        base = dict(g0='.568', g1='.548', g2='.4', W='20', delta='.005',
                    theta_a='.08', theta_b='.02', p_a='.6', r_a='.4', third_a='.7',
                    p_b='.3', r_b='.8', third_b='.9', u_A_p='0', u_A_r='0',
                    u_A_third='0', u_B_p='0', u_B_r='0', u_B_third='0', u_urgent='0')
        accepted = simulate('AB', 'candidate', **base)
        self.assertEqual(accepted.feedback, (('A', 'p', True),))
        self.assertEqual(accepted.events[1].driver, 'B')
        self.assertIsNone(accepted.events[1].offer)
        self.assertIsNone(accepted.events[1].accepted)
        self.assertEqual(accepted.added_delay, Fraction(2, 25))
        self.assertEqual(accepted.unmet_kwh, 1)
        rejected_args = dict(base, u_A_p='.99')
        reached = simulate('AB', 'candidate', **rejected_args)
        self.assertEqual(reached.feedback, (('A', 'p', False), ('B', 'r', True)))
        self.assertEqual(reached.added_delay, Fraction(1, 100))
        self.assertEqual(reached.driver_private_cost+reached.operator_private_cost, reached.system_cost)
        ba = simulate('BA', 'second_r', **base)
        self.assertEqual(ba.feedback, (('A', 'r', True),))
        self.assertEqual(ba.added_delay, Fraction(1, 25))

    def test_different_driver_parameters_and_signed_corner_bounds(self):
        a, b = coefficients(Decimal('.568'), Decimal('.548'), Decimal('.4'),
                            Decimal('.005'), Decimal('20'))
        gain, service = benefit_service_bounds(I('.6'), I('.4'), I('.08'), I('.02'), a, b, I('.005'))
        self.assertLessEqual(gain.lo, Decimal('.0004'))
        self.assertGreaterEqual(gain.hi, Decimal('.0004'))
        self.assertGreaterEqual(service, Decimal('.0038'))
        reverse, _ = benefit_service_bounds(I('.6'), I('.4'), I('.02'), I('.08'), a, b, I('.005'))
        self.assertLessEqual(reverse.lo, Decimal('.0316'))
        self.assertGreaterEqual(reverse.hi, Decimal('.0316'))
        negative, _ = benefit_service_bounds(I('.4', '.6'), I('.4', '.7'), I('.1', '.2'),
                                            I('.1', '.2'), a, b, I('.005'))
        self.assertLessEqual(negative.lo, Decimal('-.092'))

    def test_gates_use_separate_driver_witnesses_and_no_hidden_truth(self):
        ca, qa = counts('.02', '.2', '.2', 10**10)
        cb, qb = counts('.04', '.15', '-.1', 10**10)
        data = {'A': ca, 'B': cb}
        physics = dict(g0='.8', g1='.7', g2='.4', W='20', delta='.005', epsilon='.005')
        for method in ('two', 'three'):
            result = evaluate(data, method=method, **physics)
            self.assertEqual(result['decision'], 'ALLOW', result)
            self.assertLessEqual(Decimal(result['theta_outer']['A'][0]), Decimal('.02'))
            self.assertGreaterEqual(Decimal(result['theta_outer']['A'][1]), Decimal('.02'))
            self.assertLessEqual(Decimal(result['theta_outer']['B'][0]), Decimal('.04'))
            self.assertGreaterEqual(Decimal(result['theta_outer']['B'][1]), Decimal('.04'))
            with localcontext() as context:
                context.prec = 70
                true_b = qa[0]*(Decimal('.302')-Decimal('.02'))+(1-qa[0])*qb[1]*(Decimal('.202')-Decimal('.04')/2)
            self.assertLessEqual(Decimal(result['benefit_interval'][0]), true_b)
            self.assertGreaterEqual(Decimal(result['benefit_interval'][1]), true_b)
            tight = dict(physics, epsilon='0')
            self.assertEqual(evaluate(data, method=method, **tight)['reason'], 'service_not_certified')
        invalid = {'A': dict(ca, theta=.02), 'B': cb}
        self.assertEqual(evaluate(invalid, method='two', **physics)['reason'], 'invalid_input')

    def test_missing_suppressed_and_boundary_streams_abstain(self):
        ca, _ = counts('.02', '.2', '.2', 10**8)
        cb, _ = counts('.04', '.15', '-.1', 10**8)
        physics = dict(g0='.8', g1='.7', g2='.4', W='20', delta='.005', epsilon='.005')
        data = {'A': ca, 'B': dict(cb, third=(0, 0))}
        self.assertEqual(evaluate(data, method='three', **physics)['reason'], 'missing_stream')
        self.assertNotEqual(evaluate(data, method='two', **physics)['reason'], 'missing_stream')
        data = {'A': dict(ca, p=(1, 1)), 'B': cb}
        self.assertEqual(evaluate(data, method='two', **physics)['reason'], 'noninterior_probability_band')
        self.assertEqual(prior_only(**physics)['decision'], 'ALLOW')
        self.assertFalse(prior_only(**physics)['uniform_positive_margin'])

    def test_impossible_relationship_and_invalid_physics_abstain(self):
        normal, _ = counts('.02', '.2', '.2', 10**8)
        impossible = {'p': (800000, 1000000), 'r': (900000, 1000000),
                      'third': (200000, 1000000)}
        physics = dict(g0='.8', g1='.7', g2='.4', W='20', delta='.005', epsilon='.005')
        self.assertEqual(evaluate({'A': impossible, 'B': normal}, method='three', **physics)['reason'],
                         'empty_or_unresolved_outer')
        for key, value in (('g0', '-1'), ('W', 'NaN'), ('delta', '1.1'), ('epsilon', .005)):
            bad = dict(physics)
            bad[key] = value
            self.assertEqual(evaluate({'A': normal, 'B': normal}, method='two', **bad)['reason'], 'invalid_input')


if __name__ == '__main__':
    unittest.main()
