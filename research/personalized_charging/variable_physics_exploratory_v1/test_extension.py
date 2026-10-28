import itertools
import unittest
from decimal import Decimal, ROUND_HALF_UP, localcontext
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.sequential_identification_v1.physical import simulate_episode
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import evaluate as old_three
from personalized_charging.two_contrast_bias_exploratory_v1.gate import evaluate as old_two
from personalized_charging.variable_physics_exploratory_v1.gate import (
    benefit_service_bounds, coefficients, evaluate,
)
from personalized_charging.variable_physics_exploratory_v1.physical import simulate
from personalized_charging.variable_physics_exploratory_v1.prior_gate import evaluate as prior_only


def deterministic_counts(theta, tau, shift, n):
    with localcontext() as context:
        context.prec = 80
        theta, tau, shift = Decimal(theta), Decimal(tau), Decimal(shift)
        logits = ((Decimal('.1')-theta)/tau+shift,
                  (Decimal('.1')-theta/2)/tau+shift,
                  (Decimal('.2')-theta)/tau+shift)
        probs = [Decimal(1)/(Decimal(1)+(-x).exp()) for x in logits]
        return {key: (int((q*n).to_integral_value(rounding=ROUND_HALF_UP)), n)
                for key, q in zip(('p', 'r', 'third'), probs)}


class VariablePhysicsTests(unittest.TestCase):
    def test_exhaustive_exact_rational_branches_and_private_ledgers(self):
        scenarios = (
            ('0.8', '0.7', '0.4', '20', '0.005'),
            ('0.45', '0.4', '0.4', '20', '0.02'),
            ('0.568', '0.548', '0.4', '20', '0.005'),
            ('0.4', '0.4', '0.4', '0.4', '0.3'),
            ('0.3', '0.5', '0.6', '0.1', '0.25'),
            ('0.5', '0.5', '0.5', '0', '0'),
            ('0.25', '0.25', '0.8', '0', '1'),
        )
        probabilities = (Fraction(3, 5), Fraction(2, 5), Fraction(7, 10))
        theta = Fraction(2, 25)
        policies = ('baseline', 'candidate', 'collect_p', 'collect_r', 'collect_third')
        for g0, g1, g2, penalty, delta in scenarios:
            with self.subTest(physics=(g0, g1, g2, penalty, delta)):
                d = Fraction(delta)
                totals = {name: [Fraction(0), Fraction(0)] for name in policies}
                for outcomes in itertools.product((False, True), repeat=4):
                    probability = Fraction(1)
                    for value, q in zip(outcomes, (*probabilities, d)):
                        probability *= q if value else 1-q
                    if not probability:
                        continue
                    up, ur, ut, uu = ('0' if flag else '.99' for flag in outcomes)
                    for policy in policies:
                        episode = simulate(policy, g0=g0, g1=g1, g2=g2, W=penalty, delta=delta,
                                           theta='.08', p='.6', r='.4', third='.7',
                                           u_p=up, u_r=ur, u_third=ut, u_urgent=uu)
                        self.assertEqual(episode.driver_private_cost + episode.operator_private_cost,
                                         episode.system_cost)
                        totals[policy][0] += probability * episode.system_cost
                        totals[policy][1] += probability * episode.unmet_kwh
                a = Fraction(g0)-Fraction(g2)-d*(Fraction(penalty)-Fraction(g2))
                b = Fraction(g1)-Fraction(g2)-d*(Fraction(penalty)-Fraction(g2))
                p, r, third = probabilities
                expected = p*(a-theta)+(1-p)*r*(b-theta/2)
                self.assertEqual(totals['baseline'][0]-totals['candidate'][0], expected)
                self.assertEqual(totals['candidate'][1], d*(p+(1-p)*r))
                self.assertEqual(totals['baseline'][1], 0)
                self.assertEqual(totals['baseline'][0]-totals['collect_p'][0], p*(a-theta))
                self.assertEqual(totals['baseline'][0]-totals['collect_r'][0], r*(b-theta/2))
                self.assertEqual(totals['baseline'][0]-totals['collect_third'][0], third*(a-theta))
                self.assertEqual(totals['collect_third'][1], d*third)

    def test_original_constants_match_frozen_physical_model(self):
        for policy in ('baseline', 'candidate', 'collect_p', 'collect_r'):
            for up, ur, urgent in itertools.product(('0', '.99'), repeat=3):
                new = simulate(policy, g0='.568', g1='.548', g2='.4', W='20', delta='.005',
                               theta='.08', p='.6', r='.4', third='.7', u_p=up, u_r=ur,
                               u_third='0', u_urgent=urgent)
                old = simulate_episode(policy, .08, .2, float(up), float(ur), float(urgent),
                                       p_response=.6, r_response=.4)
                self.assertAlmostEqual(float(new.system_cost), old.loss)
                self.assertEqual(new.unmet_kwh, old.unmet_kwh)
                self.assertEqual([(e.offer, e.accepted, e.assigned_slot) for e in new.events],
                                 [(e.offer, e.accepted, e.assigned_slot) for e in old.events])

    def test_original_gate_bounds_and_prior_benefit_abstentions(self):
        with localcontext() as context:
            context.prec = 80
            counts = deterministic_counts(Decimal(2)/35, Decimal(1)/7, 0, 10**11)
        original = {'g0': '.568', 'g1': '.548', 'g2': '.4', 'W': '20',
                    'delta': '.005', 'epsilon': '.005'}
        old = old_three(counts)
        new = evaluate(counts, method='three', **original)
        self.assertEqual(old['decision'], 'ALLOW')
        self.assertEqual(new['decision'], 'ALLOW')
        self.assertEqual(list(map(Decimal, old['benefit_interval'])),
                         list(map(Decimal, new['benefit_interval'])))
        self.assertEqual(Decimal(old['candidate_service_upper']), Decimal(new['candidate_service_upper']))

        two_counts = {key: counts[key] for key in ('p', 'r')}
        self.assertEqual(old_two(two_counts)['reason'], 'benefit_not_positive')
        positive = evaluate(two_counts, method='two', g0='.8', g1='.7', g2='.4',
                            W='20', delta='.005', epsilon='.005')
        self.assertEqual(positive['inference_reason'], 'benefit_not_positive')
        self.assertEqual(positive['decision'], 'ALLOW')

    def test_general_corners_zero_and_unit_arrival_and_inverted_penalty(self):
        a, b = coefficients(Decimal('.568'), Decimal('.548'), Decimal('.4'),
                            Decimal('.005'), Decimal('20'))
        benefit, service = benefit_service_bounds(I('.4', '.6'), I('.4', '.7'),
                                                  I('.1', '.2'), a, b, I('.005'))
        self.assertLessEqual(benefit.lo, Decimal('-.092'))
        self.assertGreaterEqual(service, Decimal('.0044'))
        counts = deterministic_counts('.08', '.2', '.2', 10**11)
        two_counts = {key: counts[key] for key in ('p', 'r')}
        none = evaluate(two_counts, method='two', g0='.8', g1='.7', g2='.4',
                        W='20', delta='0', epsilon='0')
        self.assertEqual(none['decision'], 'ALLOW', none)
        self.assertEqual(Decimal(none['candidate_service_upper']), 0)
        all_urgent = evaluate(two_counts, method='two', g0='.8', g1='.7', g2='.4',
                              W='.4', delta='1', epsilon='.005')
        self.assertEqual(all_urgent['reason'], 'service_not_certified')
        inverted = evaluate(two_counts, method='two', g0='.7', g1='.7', g2='.4',
                            W='.1', delta='.005', epsilon='.005')
        self.assertEqual(inverted['decision'], 'ALLOW')
        self.assertLessEqual(Decimal(inverted['a'][0]), Decimal('.3015'))
        self.assertGreaterEqual(Decimal(inverted['a'][1]), Decimal('.3015'))

    def test_invalid_nonfinite_and_unresolved_inputs_fail_closed(self):
        data = {'p': (0, 0), 'r': (0, 0)}
        physics = {'g0': '.8', 'g1': '.7', 'g2': '.4', 'W': '20',
                   'delta': '.005', 'epsilon': '.005'}
        self.assertEqual(evaluate(data, method='two', **physics)['reason'], 'inference_unresolved')
        for key, value in (('g0', '-1'), ('g1', 'NaN'), ('g2', float(.4)),
                           ('W', 'Infinity'), ('delta', '1.1'), ('epsilon', '-.1')):
            kwargs = dict(physics)
            kwargs[key] = value
            self.assertEqual(evaluate(data, method='two', **kwargs)['reason'], 'invalid_physics')
        counts = deterministic_counts('.08', '.2', '.2', 10**11)
        kwargs = dict(physics)
        kwargs['g0'] = '1e1000'
        self.assertEqual(evaluate({key: counts[key] for key in ('p', 'r')}, method='two', **kwargs)['decision'], 'ABSTAIN')

    def test_prior_only_strict_boundaries_service_and_negative_penalty_difference(self):
        basic = {'g0': '.25', 'g1': '.125', 'g2': '0', 'W': '0', 'delta': '0', 'epsilon': '0'}
        self.assertEqual(prior_only(**basic)['reason'], 'prior_not_certified')
        for update in ({'g0': '.251'}, {'g1': '.126'}):
            inputs = dict(basic)
            inputs.update(update)
            result = prior_only(**inputs)
            self.assertEqual(result['decision'], 'ALLOW')
            self.assertFalse(result['uniform_positive_margin'])
        inputs = {'g0': '.65', 'g1': '.53', 'g2': '.4', 'W': '.4',
                  'delta': '.005', 'epsilon': '.0049'}
        self.assertEqual(prior_only(**inputs)['reason'], 'service_not_certified')
        inputs['epsilon'] = '.005'
        self.assertEqual(prior_only(**inputs)['decision'], 'ALLOW')
        self.assertEqual(prior_only(g0='.45', g1='.33', g2='.4', W='0',
                                    delta='.5', epsilon='.5')['decision'], 'ALLOW')


if __name__ == '__main__':
    unittest.main()
