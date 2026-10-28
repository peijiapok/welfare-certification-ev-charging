"""Independent exact 12-cell / two-driver physics audit; no scientific run.

This test does not import the study runner or a gate. Unexposed potential
responses are evaluator-only and are used solely for paired path calculations.
"""
from collections import defaultdict
from fractions import Fraction as F
from itertools import product
from math import factorial
import unittest

from personalized_charging.two_driver_exploratory_v1.physical import simulate


PARAMETERS = {
    'AB': {
        'first': 'A', 'second': 'B', 'theta_first': F(2, 25), 'theta_second': F(3, 25),
        'p': F(3, 10), 'r': F(11, 20), 'third': F(3, 5),
        'first_states': ((True, True, '0.1', F(3, 10)),
                         (False, True, '0.45', F(3, 10)),
                         (False, False, '0.8', F(2, 5))),
    },
    'BA': {
        'first': 'B', 'second': 'A', 'theta_first': F(3, 25), 'theta_second': F(2, 25),
        'p': F(1, 5), 'r': F(2, 5), 'third': F(7, 10),
        'first_states': ((True, True, '0.1', F(1, 5)),
                         (False, True, '0.45', F(1, 2)),
                         (False, False, '0.8', F(3, 10))),
    },
}
DELTA = F(1, 50)


def cells(role):
    config = PARAMETERS[role]
    result = []
    for (p, third, first_u, first_mass), second, urgent in product(
            config['first_states'], (False, True), (False, True)):
        r_mass = config['r'] if second else 1 - config['r']
        urgency_mass = DELTA if urgent else 1 - DELTA
        result.append(dict(p=p, third=third, r=second, urgent=urgent,
                           first_u=first_u, second_u='0.1' if second else '0.9',
                           urgent_u='0.01' if urgent else '0.5',
                           weight=first_mass * r_mass * urgency_mass))
    return result


def independent_gain_and_unmet(plan, row, role, g0, g1, g2, penalty):
    config = PARAMETERS[role]
    t_first, t_second = config['theta_first'], config['theta_second']
    if plan == 'baseline':
        return F(0), 0
    if plan == 'candidate':
        use_first = int(row['p'])
        use_second = int(not row['p'] and row['r'])
    elif plan == 'first_p':
        use_first, use_second = int(row['p']), 0
    elif plan == 'first_third':
        use_first, use_second = int(row['third']), 0
    elif plan == 'second_r':
        use_first, use_second = 0, int(row['r'])
    else:
        raise AssertionError('unknown plan')
    blocked = int(row['urgent'] and (use_first or use_second))
    gain = (use_first * (g0 - g2 - t_first) +
            use_second * (g1 - g2 - t_second / 2) - blocked * (penalty - g2))
    return gain, blocked


def inputs(row, world):
    return dict(g0=world[0], g1=world[1], g2=world[2], W=world[3],
                delta='0.02', theta_a='0.08', theta_b='0.12',
                p_a='0.3', r_a='0.4', third_a='0.6',
                p_b='0.2', r_b='0.55', third_b='0.7',
                u_A_p=row['first_u'], u_A_third=row['first_u'], u_A_r=row['second_u'],
                u_B_p=row['first_u'], u_B_third=row['first_u'], u_B_r=row['second_u'],
                u_urgent=row['urgent_u'])


class TwoDriverIndependentAudit(unittest.TestCase):
    def test_exact_12_cell_law_and_two_episode_multinomial(self):
        for role in ('AB', 'BA'):
            with self.subTest(role=role):
                cases = cells(role)
                self.assertEqual(len(cases), 12)
                weights = [row['weight'] for row in cases]
                self.assertEqual(sum(weights, F(0)), 1)
                for key in ('p', 'r', 'third'):
                    self.assertEqual(sum((row['weight'] for row in cases if row[key]), F(0)),
                                     PARAMETERS[role][key])
                self.assertEqual(sum((row['weight'] for row in cases if row['urgent']), F(0)), DELTA)
                self.assertFalse(any(row['p'] and not row['third'] for row in cases))
                ordered = defaultdict(F)
                for i, j in product(range(12), repeat=2):
                    count = [0] * 12
                    count[i] += 1
                    count[j] += 1
                    ordered[tuple(count)] += weights[i] * weights[j]
                self.assertEqual(len(ordered), 78)
                self.assertEqual(sum(ordered.values(), F(0)), 1)
                for count, probability in ordered.items():
                    coefficient = factorial(2)
                    expected = F(1)
                    for n, weight in zip(count, weights):
                        coefficient //= factorial(n)
                        expected *= weight ** n
                    self.assertEqual(probability, coefficient * expected)

    def test_all_categories_physics_reach_and_exact_expected_welfare(self):
        worlds = (
            ('0.568', '0.548', '0.4', '20'),
            ('0.51', '0.46', '0.5', '0.2'),  # W < g2
            ('0', '0', '0', '0'),
            ('0.8', '0.65', '0.4', '20'),
        )
        plans = ('baseline', 'candidate', 'first_p', 'second_r', 'first_third')
        for role, world in product(('AB', 'BA'), worlds):
            g0, g1, g2, penalty = map(F, world)
            expected_gain = defaultdict(F)
            expected_unmet = defaultdict(F)
            natural_r_reach = forced_r_reach = F(0)
            for row in cells(role):
                with self.subTest(role=role, world=world, cell=row):
                    episodes = {plan: simulate(role, plan, **inputs(row, world)) for plan in plans}
                    baseline = episodes['baseline']
                    self.assertEqual(baseline.system_cost, g0 + g1 + int(row['urgent']) * g2)
                    self.assertEqual(baseline.unmet_kwh, 0)
                    for plan, episode in episodes.items():
                        gain, unmet = independent_gain_and_unmet(plan, row, role, g0, g1, g2, penalty)
                        self.assertEqual(baseline.system_cost - episode.system_cost, gain)
                        self.assertEqual(episode.unmet_kwh, unmet)
                        self.assertEqual(episode.driver_private_cost + episode.operator_private_cost,
                                         episode.system_cost)
                        observed = [(e.driver, e.offer, e.accepted) for e in episode.events if e.offer]
                        first, second = PARAMETERS[role]['first'], PARAMETERS[role]['second']
                        if plan == 'baseline':
                            expected = []
                        elif plan == 'candidate':
                            expected = [(first, 'p', row['p'])]
                            if not row['p']:
                                expected.append((second, 'r', row['r']))
                            natural_r_reach += row['weight'] * int(not row['p'])
                        elif plan == 'first_p':
                            expected = [(first, 'p', row['p'])]
                        elif plan == 'first_third':
                            expected = [(first, 'third', row['third'])]
                        else:
                            expected = [(second, 'r', row['r'])]
                            forced_r_reach += row['weight']
                        self.assertEqual(observed, expected)
                        expected_gain[plan] += row['weight'] * gain
                        expected_unmet[plan] += row['weight'] * unmet
            config = PARAMETERS[role]
            p, r = config['p'], config['r']
            a = g0 - g2 - DELTA * (penalty - g2)
            b = g1 - g2 - DELTA * (penalty - g2)
            self.assertEqual(expected_gain['candidate'],
                             p * (a - config['theta_first']) +
                             (1-p) * r * (b - config['theta_second']/2))
            self.assertEqual(expected_unmet['candidate'], DELTA * (p + (1-p)*r))
            self.assertEqual(natural_r_reach, 1 - p)
            self.assertEqual(forced_r_reach, 1)

    def test_urgent_probability_endpoints(self):
        world = ('0.51', '0.46', '0.5', '0.2')
        g0, g1, g2, penalty = map(F, world)
        for role, delta in product(('AB', 'BA'), ('0', '1')):
            for original in cells(role):
                if original['urgent']:
                    continue
                row = dict(original, urgent=(delta == '1'), urgent_u='0.5')
                args = inputs(row, world)
                args['delta'] = delta
                baseline = simulate(role, 'baseline', **args)
                for plan in ('candidate', 'first_p', 'second_r', 'first_third'):
                    episode = simulate(role, plan, **args)
                    gain, unmet = independent_gain_and_unmet(plan, row, role, g0, g1, g2, penalty)
                    self.assertEqual(baseline.system_cost - episode.system_cost, gain)
                    self.assertEqual(episode.unmet_kwh, unmet)


if __name__ == '__main__':
    unittest.main()
