import copy
import json
import unittest
from decimal import Decimal
from unittest.mock import patch

from personalized_charging.continuous_certificate_exploratory_v1.comparator import (
    evaluate, point_regression_mixture, prospective_mixture,
)
from personalized_charging.continuous_certificate_exploratory_v1.proof_replay import replay


class ProofReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = (('p', True), ('r', True)) + (('p', True),) * 11
        cls.mixture = point_regression_mixture()
        cls.result = evaluate(cls.history, mixture=cls.mixture)
        if cls.result['decision'] != 'ALLOW':
            raise AssertionError(cls.result)

    def check(self, result, **overrides):
        inputs = {'history': self.history, 'mixture': self.mixture,
                  'epsilon': '0.005', 'max_nodes': 10000}
        inputs.update(overrides)
        return replay(result, **inputs)

    def test_complete_tree_and_json_round_trip(self):
        valid, reason = self.check(self.result)
        self.assertTrue(valid, reason)
        valid, reason = self.check(json.loads(json.dumps(self.result)))
        self.assertTrue(valid, reason)
        kinds = {node['kind'] for node in self.result['proof']['nodes']}
        self.assertEqual(kinds, {'split', 'accept', 'exclude'})

    def test_two_point_mixture_tree(self):
        mixture = (('0.99', '0', '0.05'), ('0.01', '0.2', '0.2'))
        result = evaluate(self.history, mixture=mixture)
        valid, reason = self.check(result, mixture=mixture)
        self.assertTrue(valid, reason)

    def test_replay_mixed_acceptances_and_rejections(self):
        history = (('p', True), ('r', False), ('p', False)) + (('p', True),) * 36
        result = evaluate(history, mixture=self.mixture)
        valid, reason = self.check(result, history=history)
        self.assertTrue(valid, (result, reason))

    def test_prospective_mixture_has_distinct_replayable_control(self):
        history = (('p', True),) * 32 + (('r', True),) * 8
        mixture = prospective_mixture()
        result = evaluate(history, mixture=mixture)
        valid, reason = self.check(result, history=history, mixture=mixture)
        self.assertTrue(valid, (result, reason))

    def test_root_gap_truncation_and_unreachable_nodes_rejected(self):
        bad = copy.deepcopy(self.result)
        bad['proof']['nodes'][0]['box'][0] = '0.001'
        self.assertFalse(self.check(bad)[0])

        bad = copy.deepcopy(self.result)
        root = bad['proof']['nodes'][0]
        left = bad['proof']['nodes'][root['children'][0]]['box']
        # The root splits one of its dimensions. Change its left upper endpoint.
        root_box = root['box']
        upper_index = 1 if left[1] != root_box[1] else 3
        left[upper_index] = str(Decimal(left[upper_index]) - Decimal('.000001'))
        self.assertFalse(self.check(bad)[0])

        bad = copy.deepcopy(self.result)
        bad['proof']['nodes'].pop()
        bad['nodes'] -= 1
        self.assertFalse(self.check(bad)[0])

        bad = copy.deepcopy(self.result)
        bad['proof']['nodes'].append(copy.deepcopy(bad['proof']['nodes'][-1]))
        bad['nodes'] += 1
        self.assertFalse(self.check(bad)[0])

    def test_each_leaf_bound_is_recomputed(self):
        for kind, field, replacement in (('accept', 'benefit_lower', '999'),
                                         ('accept', 'service_upper', '0'),
                                         ('exclude', 'likelihood_upper', '0'),
                                         ('exclude', 'threshold_lower', '999')):
            bad = copy.deepcopy(self.result)
            leaf = next(node for node in bad['proof']['nodes'] if node['kind'] == kind)
            leaf[field] = replacement
            self.assertFalse(self.check(bad)[0], (kind, field))
        bad = copy.deepcopy(self.result)
        leaf = next(node for node in bad['proof']['nodes'] if node['kind'] == 'exclude')
        leaf['prefix'] = -1
        self.assertFalse(self.check(bad)[0])

    def test_metadata_witness_and_global_claim_rejected_when_changed(self):
        bad = copy.deepcopy(self.result)
        bad['proof']['history'][0][1] = False
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['proof']['history'][0][1] = 1
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['proof']['version'] = True
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['proof']['mixture'][0][1] = '0.1'
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['proof']['epsilon'] = '0.0045'
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['proof']['max_nodes'] += 1
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['witness'] = ['0.2', '0.2']
        self.assertFalse(self.check(bad)[0])
        bad = copy.deepcopy(self.result)
        bad['benefit_lower'] = '100'
        self.assertFalse(self.check(bad)[0])
        self.assertFalse(self.check(self.result, epsilon='0.0045')[0])
        self.assertFalse(self.check(self.result, history=self.history[:-1])[0])

    def test_resource_limited_run_and_forged_completion_rejected(self):
        result = evaluate(self.history, mixture=self.mixture, max_nodes=1)
        self.assertEqual(result['reason'], 'node_limit')
        self.assertFalse(self.check(result, max_nodes=1)[0])
        result['decision'], result['reason'] = 'ALLOW', 'outward_bounds'
        self.assertFalse(self.check(result, max_nodes=1)[0])

    def test_arithmetic_error_reports_created_nodes(self):
        target = 'personalized_charging.continuous_certificate_exploratory_v1.comparator._exclusion'
        with patch(target, side_effect=ArithmeticError('injected')):
            result = evaluate(self.history, mixture=self.mixture)
        self.assertEqual(result['reason'], 'arithmetic_failure')
        self.assertEqual(result['nodes'], 1)


if __name__ == '__main__':
    unittest.main()
