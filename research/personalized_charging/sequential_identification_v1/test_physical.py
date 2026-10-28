import math
import unittest

import numpy as np

from personalized_charging.sequential_identification_v1.physical import (
    simulate_episode,
)


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def exact_expected(policy, theta, tau):
    """Enumerate all independent Bernoulli paths, without Monte Carlo."""
    p = sigmoid((.1 - theta) / tau)
    r = sigmoid((.1 - theta / 2) / tau)
    loss, unmet = [], []
    for hit_p, wp, up in ((True, p, p / 2), (False, 1 - p, (1 + p) / 2)):
        for hit_r, wr, ur in ((True, r, r / 2), (False, 1 - r, (1 + r) / 2)):
            for urgent, wu, uu in ((True, .005, .002), (False, .995, .5)):
                episode = simulate_episode(policy, theta, tau, up, ur, uu)
                weight = wp * wr * wu
                loss.append(weight * episode.loss)
                unmet.append(weight * episode.unmet_kwh)
    return math.fsum(loss), math.fsum(unmet)


class PhysicalTests(unittest.TestCase):
    def test_candidate_acceptance_keeps_commitment_and_skips_second_offer(self):
        episode = simulate_episode("candidate", .1, .2, .1, .1, .1)
        first, second = episode.events
        self.assertEqual((first.offer, first.accepted, first.assigned_slot), ("p", True, 2))
        self.assertEqual((second.offer, second.accepted, second.assigned_slot), (None, None, 1))
        self.assertEqual(second.occupied_after, (False, True, True))
        self.assertAlmostEqual(episode.procurement_cost, .4 + .548)
        self.assertAlmostEqual(episode.delay_loss, .1)

    def test_rejection_keeps_fallback_and_allows_second_offer(self):
        episode = simulate_episode("candidate", .1, .2, .9, .1, .002)
        first, second, urgent = episode.events
        self.assertEqual((first.offer, first.accepted, first.assigned_slot), ("p", False, 0))
        self.assertEqual((second.offer, second.accepted, second.assigned_slot), ("r", True, 2))
        self.assertEqual((urgent.assigned_slot, episode.unmet_kwh), (None, 1))
        self.assertEqual(urgent.occupied_after, (True, False, True))
        self.assertEqual(episode.unmet_penalty, 20)
        self.assertAlmostEqual(episode.delay_loss, .05)

    def test_urgent_served_on_free_slot_and_defaults_have_no_feedback(self):
        episode = simulate_episode("baseline", .2, .2, .1, .1, 0)
        first, second, urgent = episode.events
        self.assertEqual([(e.offer, e.accepted) for e in episode.events], [(None, None)] * 3)
        self.assertEqual([e.assigned_slot for e in episode.events], [0, 1, 2])
        self.assertEqual(urgent.occupied_after, (True, True, True))
        self.assertEqual(episode.unmet_kwh, 0)
        self.assertAlmostEqual(episode.loss, .568 + .548 + .4)
        self.assertEqual(episode.utility, -episode.loss)

    def test_independent_offer_inputs_are_used_for_their_own_offers(self):
        # p=.5 and r>.5: first rejects only because u_p=.9; r accepts
        # only because u_r=.1. Reusing u_p for r would reject both.
        episode = simulate_episode("candidate", .1, .2, .9, .1, .5)
        self.assertEqual([(e.offer, e.accepted) for e in episode.events],
                         [("p", False), ("r", True)])
        no_r = simulate_episode("collect_p", .1, .2, .9, .1, .5)
        only_r = simulate_episode("collect_r", .1, .2, .1, .9, .5)
        self.assertEqual([(e.offer, e.accepted) for e in no_r.events],
                         [("p", False), (None, None)])
        self.assertEqual([(e.offer, e.accepted) for e in only_r.events],
                         [(None, None), ("r", False)])

    def test_numpy_uniform_scalars_produce_builtin_boolean_responses(self):
        first = simulate_episode("candidate", .1, .2, np.float64(.1),
                                 np.float64(.1), np.float64(.5))
        self.assertIs(first.events[0].accepted, True)
        self.assertEqual(first.events[0].assigned_slot, 2)
        self.assertIsNone(first.events[1].accepted)
        second = simulate_episode("candidate", .1, .2, np.float64(.9),
                                  np.float64(.1), np.float64(.5))
        self.assertIs(second.events[0].accepted, False)
        self.assertIs(second.events[1].accepted, True)
        self.assertEqual(second.events[1].assigned_slot, 2)

    def test_no_path_assigns_a_port_twice_or_revokes_a_commitment(self):
        for policy in ("baseline", "collect_p", "collect_r", "candidate"):
            for up in (0, .999):
                for ur in (0, .999):
                    for uu in (0, .999):
                        episode = simulate_episode(policy, .1, .2, up, ur, uu)
                        committed = set()
                        for event in episode.events:
                            if event.assigned_slot is not None:
                                self.assertNotIn(event.assigned_slot, committed)
                                committed.add(event.assigned_slot)
                            self.assertEqual(event.occupied_after,
                                             tuple(slot in committed for slot in range(3)))
                        self.assertEqual(len(episode.events) == 3, uu == 0)

    def test_exact_path_enumeration_matches_welfare_and_service_formulas(self):
        for theta, tau in ((0, .05), (.07, .2), (.2, .2), (.25, .4)):
            with self.subTest(theta=theta, tau=tau):
                p = sigmoid((.1 - theta) / tau)
                r = sigmoid((.1 - theta / 2) / tau)
                baseline, base_unmet = exact_expected("baseline", theta, tau)
                loss_p, unmet_p = exact_expected("collect_p", theta, tau)
                loss_r, unmet_r = exact_expected("collect_r", theta, tau)
                candidate, unmet = exact_expected("candidate", theta, tau)
                self.assertAlmostEqual(baseline, .568 + .548 + .005 * .4)
                self.assertEqual(base_unmet, 0)
                self.assertAlmostEqual(baseline - loss_p, p * (.07 - theta))
                self.assertAlmostEqual(baseline - loss_r, r * (.05 - theta / 2))
                self.assertAlmostEqual(baseline - candidate,
                                       p * (.07 - theta) + (1 - p) * r * (.05 - theta / 2))
                self.assertAlmostEqual(unmet_p, .005 * p)
                self.assertAlmostEqual(unmet_r, .005 * r)
                self.assertAlmostEqual(unmet, .005 * (p + (1 - p) * r))

    def test_misspecified_response_overrides_change_responses_not_welfare_rule(self):
        episode = simulate_episode("candidate", .1, .2, .1, .9, .5,
                                   p_response=0, r_response=1)
        self.assertEqual([(e.offer, e.accepted) for e in episode.events],
                         [("p", False), ("r", True)])
        self.assertAlmostEqual(episode.loss, .568 + .4 + .05)
        ordinary = simulate_episode("candidate", .1, .2, .1, .9, .5)
        self.assertTrue(ordinary.events[0].accepted)
        for invalid in (-.01, 1.01, float("nan"), True):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    simulate_episode("candidate", .1, .2, .1, .1, .1,
                                     p_response=invalid)
                with self.assertRaises(ValueError):
                    simulate_episode("candidate", .1, .2, .1, .1, .1,
                                     r_response=invalid)

    def test_boundaries_invalid_inputs_and_ties(self):
        simulate_episode("candidate", 0, .05, 0, 0, 0)
        simulate_episode("candidate", .25, .4, .999, .999, .999)
        # Identical numeric innovations remain legal; independence is an input assumption.
        simulate_episode("candidate", .1, .2, .5, .5, .5)
        self.assertFalse(simulate_episode("collect_p", .1, .2, .5, 0, 1/200).events[0].accepted)
        for policy, theta, tau, up, ur, uu in (
            ("invalid", .1, .2, .1, .1, .1),
            ("baseline", -.01, .2, .1, .1, .1),
            ("baseline", .1, 0, .1, .1, .1),
            ("baseline", .1, .2, 1, .1, .1),
            ("baseline", .1, .2, .1, float("nan"), .1),
            ("baseline", True, .2, .1, .1, .1),
        ):
            with self.subTest(policy=policy, theta=theta, tau=tau, up=up, ur=ur, uu=uu):
                with self.assertRaises(ValueError):
                    simulate_episode(policy, theta, tau, up, ur, uu)


if __name__ == "__main__":
    unittest.main()
