"""Exploratory conservative two-contrast confidence-set gate.

This is a fixed P3c toy-model comparator, not a general robust solver. It
uses the frozen P3d outward Decimal interval primitives, so it is not an
independent implementation of those primitives. Histories contain only real
non-default offers and their binary responses. The caller must ensure feasible,
predictable selection and the specified conditional response law.
"""

from decimal import Decimal
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I, sigmoid

ONE = I('1')
ALPHA = I('0.05')
DELTA = I('0.005')
ZERO = Decimal('0')


def point_regression_mixture():
    """P3c's fixed alternative, solely for known-answer regression."""
    return (('1', '0', '0.05'),)


def prospective_mixture():
    """A fixed 25-point prior-supported mixture; weights do not depend on data."""
    return tuple(('0.04', str(Decimal(i) * Decimal('0.0625')),
                  str(Decimal('0.05') + Decimal(j) * Decimal('0.0875')))
                 for i in range(5) for j in range(5))


def _validate(history, mixture, epsilon, max_nodes):
    history = tuple(history)
    if any(not isinstance(event, tuple) or len(event) != 2 or
           event[0] not in ('p', 'r') or type(event[1]) is not bool
           for event in history):
        raise ValueError('history must contain (p or r, bool) tuples')
    if not isinstance(epsilon, str) or not Decimal(epsilon).is_finite() or Decimal(epsilon) < 0:
        raise ValueError('epsilon must be a nonnegative exact decimal string')
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError('max_nodes must be a positive integer')
    mixture = tuple(mixture)
    if not mixture:
        raise ValueError('mixture cannot be empty')
    weights = []
    for item in mixture:
        if len(item) != 3 or any(not isinstance(x, str) for x in item):
            raise ValueError('mixture values must be exact decimal strings')
        w, theta, tau = map(Decimal, item)
        if not all(x.is_finite() for x in (w, theta, tau)):
            raise ValueError('mixture values must be finite')
        if not (w > 0 and ZERO <= theta <= Decimal('0.25') and
                Decimal('0.05') <= tau <= Decimal('0.4')):
            raise ValueError('mixture point or weight outside allowed domain')
        weights.append(Fraction(item[0]))
    if sum(weights, Fraction(0)) != 1:
        raise ValueError('mixture weights must sum exactly to one')
    return history, mixture, Decimal(epsilon)


def probabilities(theta, tau):
    return (sigmoid((I('0.1') - theta) / tau),
            sigmoid((I('0.1') - theta / I('2')) / tau))


def prefix_likelihoods(history, theta, tau):
    """Outward enclosures for every response prefix at the same model box."""
    p, r = probabilities(theta, tau)
    likelihood = ONE
    result = []
    for contrast, accepted in history:
        q = p if contrast == 'p' else r
        likelihood = likelihood * (q if accepted else ONE - q)
        result.append(likelihood)
    return tuple(result)


def mixture_thresholds(history, mixture):
    """Outward alpha times fixed mixture likelihood at every prefix."""
    totals = [I('0') for _ in history]
    for weight, theta, tau in mixture:
        values = prefix_likelihoods(history, I(theta), I(tau))
        totals = [total + I(weight) * value for total, value in zip(totals, values)]
    return tuple(ALPHA * total for total in totals)


def benefit_service(theta, tau):
    p, r = probabilities(theta, tau)
    benefit = p * (I('0.07') - theta) + (ONE - p) * r * (I('0.05') - theta / I('2'))
    service = DELTA * (p + (ONE - p) * r)
    # The physical process can block at most one urgent kWh. This exact bound
    # improves natural interval dependency without narrowing the true set.
    service = I(max(service.lo, ZERO), min(service.hi, DELTA.hi))
    return benefit, service


def _strict_point(history, thresholds, theta, tau):
    values = prefix_likelihoods(history, I(theta), I(tau))
    return all(value.lo > threshold.hi for value, threshold in zip(values, thresholds))


def _exclusion(history, thresholds, theta, tau):
    values = prefix_likelihoods(history, theta, tau)
    for index, (value, threshold) in enumerate(zip(values, thresholds)):
        if value.hi <= threshold.lo:
            return index, value.hi, threshold.lo
    return None


def _box(theta, tau):
    return [str(theta.lo), str(theta.hi), str(tau.lo), str(tau.hi)]


def evaluate(history, *, mixture, epsilon='0.005', max_nodes=10000):
    """Sound yes-or-abstain gate using exhaustive outward box refinement.

    A strict feasible point prevents a vacuous pass for an empty confidence
    intersection. If any boxes remain unresolved at the cap, the gate abstains.
    Results concern the fixed candidate versus always-default policy only.
    """
    history, mixture, epsilon = _validate(history, mixture, epsilon, max_nodes)
    created = 0
    try:
        thresholds = mixture_thresholds(history, mixture)
        candidates = [(theta, tau) for _, theta, tau in mixture]
        candidates += [('0.01', '0.2'), ('0.2', '0.2')]
        witness = None
        for theta, tau in candidates:
            if not _strict_point(history, thresholds, theta, tau):
                continue
            witness = witness or (theta, tau)
            benefit, service = benefit_service(I(theta), I(tau))
            if benefit.hi <= ZERO:
                return {'decision': 'ABSTAIN', 'reason': 'nonpositive_benefit_witness',
                        'witness': (theta, tau), 'nodes': 0}
            if service.lo > epsilon:
                return {'decision': 'ABSTAIN', 'reason': 'service_violation_witness',
                        'witness': (theta, tau), 'nodes': 0}
        if witness is None:
            return {'decision': 'ABSTAIN', 'reason': 'no_strict_witness', 'nodes': 0}

        proof_nodes = [{'box': _box(I('0', '0.25'), I('0.05', '0.4'))}]
        stack = [0]
        created = 1
        kept = 0
        benefit_lower = None
        service_upper = ZERO
        while stack:
            node_id = stack.pop()
            node = proof_nodes[node_id]
            th_lo, th_hi, ta_lo, ta_hi = node['box']
            theta, tau = I(th_lo, th_hi), I(ta_lo, ta_hi)
            excluded = _exclusion(history, thresholds, theta, tau)
            if excluded is not None:
                index, likelihood_upper, threshold_lower = excluded
                node.update({'kind': 'exclude', 'prefix': index,
                             'likelihood_upper': str(likelihood_upper),
                             'threshold_lower': str(threshold_lower)})
                continue
            benefit, service = benefit_service(theta, tau)
            if benefit.lo > ZERO and service.hi <= epsilon:
                node.update({'kind': 'accept', 'benefit_lower': str(benefit.lo),
                             'service_upper': str(service.hi)})
                kept += 1
                benefit_lower = benefit.lo if benefit_lower is None else min(benefit_lower, benefit.lo)
                service_upper = max(service_upper, service.hi)
                continue
            if created + 2 > max_nodes:
                return {'decision': 'ABSTAIN', 'reason': 'node_limit',
                        'witness': witness, 'nodes': created}
            if theta.width() * Decimal('0.35') >= tau.width() * Decimal('0.25'):
                midpoint = theta.midpoint()
                if not theta.lo < midpoint < theta.hi:
                    return {'decision': 'ABSTAIN', 'reason': 'precision_limit', 'nodes': created}
                children = ((I(theta.lo, midpoint), tau), (I(midpoint, theta.hi), tau))
            else:
                midpoint = tau.midpoint()
                if not tau.lo < midpoint < tau.hi:
                    return {'decision': 'ABSTAIN', 'reason': 'precision_limit', 'nodes': created}
                children = ((theta, I(tau.lo, midpoint)), (theta, I(midpoint, tau.hi)))
            ids = [created, created + 1]
            node.update({'kind': 'split', 'children': ids})
            proof_nodes.extend({'box': _box(child_t, child_s)}
                               for child_t, child_s in children)
            stack.extend(ids)
            created += 2
        if not kept:
            return {'decision': 'ABSTAIN', 'reason': 'no_retained_boxes', 'nodes': created}
        return {'decision': 'ALLOW', 'reason': 'outward_bounds', 'witness': witness,
                'nodes': created, 'benefit_lower': str(benefit_lower),
                'candidate_service_upper': str(service_upper), 'baseline_service_upper': '0',
                'proof': {'version': 1, 'alpha': '0.05',
                          'history': [list(event) for event in history],
                          'mixture': [list(point) for point in mixture],
                          'epsilon': str(epsilon), 'max_nodes': max_nodes,
                          'nodes': proof_nodes}}
    except ArithmeticError:
        return {'decision': 'ABSTAIN', 'reason': 'arithmetic_failure', 'nodes': created}
