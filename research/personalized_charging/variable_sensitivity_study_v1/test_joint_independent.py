"""Exact tiny joint-law and variable-physics audit, independent of any runner.

Potential unoffered responses exist only in this evaluator and are never
passed to a decision gate. This test does not generate a scientific catalog.
"""
from collections import defaultdict
from fractions import Fraction as F
from itertools import product
from math import factorial
import unittest

from personalized_charging.variable_physics_exploratory_v1.physical import simulate


# (p accepts, third accepts, shared first-request uniform, exact mass)
FIRST_STATES = (
    (True, True, '0.1', F(3, 10)),
    (False, True, '0.45', F(3, 10)),
    (False, False, '0.8', F(2, 5)),
)
R_STATES = ((True, '0.2', F(2, 5)), (False, '0.8', F(3, 5)))
URGENT_STATES = ((True, '0.01', F(1, 50)), (False, '0.5', F(49, 50)))
THETA = F(2, 25)


def categories():
    result = []
    for (first, third, first_u, first_weight), (second, second_u, second_weight), (urgent, urgent_u, urgent_weight) in product(FIRST_STATES, R_STATES, URGENT_STATES):
        result.append(dict(first=first, third=third, second=second, urgent=urgent,
                           first_u=first_u, second_u=second_u, urgent_u=urgent_u,
                           weight=first_weight * second_weight * urgent_weight))
    return result


def multinomial_two_probability(counts, weights):
    """The n=2 multinomial law calculated directly from exact masses."""
    coefficient = factorial(2)
    probability = F(1)
    for count, weight in zip(counts, weights):
        coefficient //= factorial(count)
        probability *= weight ** count
    return coefficient * probability


def expected_gain_and_unmet(policy, category, g0, g1, g2, penalty):
    """Independent evaluator formula for one physical episode, as Fractions."""
    p, r, third, urgent = (category[k] for k in ('first', 'second', 'third', 'urgent'))
    if policy == 'baseline':
        return F(0), 0
    if policy == 'candidate':
        use_first = int(p)
        use_second = int((not p) and r)
        occupied = bool(use_first or use_second)
        saving = use_first * (g0 - g2 - THETA) + use_second * (g1 - g2 - THETA / 2)
    elif policy == 'collect_p':
        occupied = p
        saving = int(p) * (g0 - g2 - THETA)
    elif policy == 'collect_third':
        occupied = third
        saving = int(third) * (g0 - g2 - THETA)
    elif policy == 'collect_r':
        occupied = r
        saving = int(r) * (g1 - g2 - THETA / 2)
    else:
        raise AssertionError('unknown test policy')
    unmet = int(urgent and occupied)
    return saving - unmet * (penalty - g2), unmet


class IndependentJointAudit(unittest.TestCase):
    def test_categories_and_exact_two_episode_multinomial(self):
        cases = categories()
        self.assertEqual(len(cases), 12)
        self.assertEqual(sum((x['weight'] for x in cases), F(0)), 1)
        self.assertEqual(sum((x['weight'] for x in cases if x['first']), F(0)), F(3, 10))
        self.assertEqual(sum((x['weight'] for x in cases if x['third']), F(0)), F(3, 5))
        self.assertEqual(sum((x['weight'] for x in cases if x['second']), F(0)), F(2, 5))
        self.assertEqual(sum((x['weight'] for x in cases if x['urgent']), F(0)), F(1, 50))
        self.assertFalse(any(x['first'] and not x['third'] for x in cases))
        weights = [x['weight'] for x in cases]
        ordered = defaultdict(F)
        for first, second in product(range(12), repeat=2):
            counts = [0] * 12
            counts[first] += 1
            counts[second] += 1
            ordered[tuple(counts)] += weights[first] * weights[second]
        self.assertEqual(len(ordered), 78)  # C(12+2-1,2)
        self.assertEqual(sum(ordered.values()), 1)
        for counts, probability in ordered.items():
            self.assertEqual(probability, multinomial_two_probability(counts, weights))

    def test_every_category_against_exact_variable_physics(self):
        # Include the standard case, W<g2, zero costs, and a prior-positive case.
        worlds = (
            ('0.568', '0.548', '0.4', '20'),
            ('0.51', '0.46', '0.5', '0.2'),
            ('0', '0', '0', '0'),
            ('0.8', '0.65', '0.4', '20'),
        )
        policies = ('baseline', 'candidate', 'collect_p', 'collect_r', 'collect_third')
        for world in worlds:
            g0, g1, g2, penalty = map(F, world)
            for index, case in enumerate(categories()):
                with self.subTest(world=world, category=index):
                    inputs = dict(g0=world[0], g1=world[1], g2=world[2], W=world[3],
                                  delta='0.02', theta='0.08', p='0.3', r='0.4', third='0.6',
                                  u_p=case['first_u'], u_third=case['first_u'],
                                  u_r=case['second_u'], u_urgent=case['urgent_u'])
                    episodes = {policy: simulate(policy, **inputs) for policy in policies}
                    baseline = episodes['baseline']
                    self.assertEqual(baseline.unmet_kwh, 0)
                    self.assertEqual(baseline.system_cost, g0 + g1 + int(case['urgent']) * g2)
                    for policy, episode in episodes.items():
                        gain, unmet = expected_gain_and_unmet(policy, case, g0, g1, g2, penalty)
                        self.assertEqual(baseline.system_cost - episode.system_cost, gain)
                        self.assertEqual(episode.unmet_kwh, unmet)
                        self.assertEqual(episode.driver_private_cost + episode.operator_private_cost,
                                         episode.system_cost)
                        observed = [(e.offer, e.accepted) for e in episode.events if e.offer]
                        if policy == 'baseline':
                            self.assertEqual(observed, [])
                        elif policy == 'candidate':
                            expected = [('p', case['first'])]
                            if not case['first']:
                                expected.append(('r', case['second']))
                            self.assertEqual(observed, expected)
                        else:
                            offer, response = {'collect_p': ('p', case['first']),
                                               'collect_r': ('r', case['second']),
                                               'collect_third': ('third', case['third'])}[policy]
                            self.assertEqual(observed, [(offer, response)])


if __name__ == '__main__':
    unittest.main()
