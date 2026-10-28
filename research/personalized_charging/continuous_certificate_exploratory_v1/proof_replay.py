"""Recompute and replay a complete exploratory comparator proof tree.

This checker independently implements traversal and bound calculations but
shares the P3d interval arithmetic with the producer. It does not verify the
statistical response model, the physical model, or the interval primitives.
"""

from decimal import Decimal
from fractions import Fraction

from personalized_charging.p3d_diagnostic_v1.interval import I, sigmoid


class ReplayError(Exception):
    pass


def _require(condition, message):
    if not condition:
        raise ReplayError(message)


def _number(value):
    _require(isinstance(value, str), 'expected exact decimal string')
    number = Decimal(value)
    _require(number.is_finite(), 'nonfinite decimal')
    return number


def _validate_inputs(history, mixture, epsilon, max_nodes):
    history, mixture = tuple(history), tuple(mixture)
    for event in history:
        _require(isinstance(event, (tuple, list)) and len(event) == 2 and
                 event[0] in ('p', 'r') and type(event[1]) is bool,
                 'invalid history')
    _require(mixture, 'empty mixture')
    total = Fraction(0)
    for point in mixture:
        _require(isinstance(point, (tuple, list)) and len(point) == 3, 'invalid mixture')
        weight, theta, tau = map(_number, point)
        _require(weight > 0 and 0 <= theta <= Decimal('.25') and
                 Decimal('.05') <= tau <= Decimal('.4'), 'invalid mixture point')
        total += Fraction(point[0])
    _require(total == 1, 'mixture weights do not sum to one')
    eps = _number(epsilon)
    _require(eps >= 0, 'negative service allowance')
    _require(type(max_nodes) is int and max_nodes > 0, 'invalid node cap')
    return history, mixture, eps


def _probabilities(theta, tau):
    one = I('1')
    return (sigmoid((I('.1') - theta) / tau),
            sigmoid((I('.1') - theta / I('2')) / tau))


def _prefixes(history, theta, tau):
    one, value = I('1'), I('1')
    p, r = _probabilities(theta, tau)
    output = []
    for contrast, response in history:
        probability = p if contrast == 'p' else r
        value = value * (probability if response else one - probability)
        output.append(value)
    return output


def _thresholds(history, mixture):
    values = [I('0') for _ in history]
    for weight, theta, tau in mixture:
        prefixes = _prefixes(history, I(theta), I(tau))
        values = [old + I(weight) * prefix for old, prefix in zip(values, prefixes)]
    return [I('.05') * value for value in values]


def _bounds(theta, tau):
    p, r = _probabilities(theta, tau)
    one = I('1')
    benefit = p * (I('.07') - theta) + (one - p) * r * (I('.05') - theta / I('2'))
    service = I('.005') * (p + (one - p) * r)
    return benefit, I(max(service.lo, Decimal(0)), min(service.hi, Decimal('.005')))


def _parse_box(node):
    box = node['box']
    _require(isinstance(box, list) and len(box) == 4, 'invalid box')
    a, b, c, d = map(_number, box)
    _require(Decimal('0') <= a < b <= Decimal('.25') and
             Decimal('.05') <= c < d <= Decimal('.4'), 'box outside prior')
    return a, b, c, d


def _partition(parent, left, right):
    a, b, c, d = parent
    la, lb, lc, ld = left
    ra, rb, rc, rd = right
    theta_split = (la == a and rb == b and lb == ra and a < lb < b and
                   lc == rc == c and ld == rd == d)
    tau_split = (lc == c and rd == d and ld == rc and c < ld < d and
                 la == ra == a and lb == rb == b)
    return theta_split or tau_split


def replay(result, *, history, mixture, epsilon='0.005', max_nodes=10000):
    """Return (valid, reason); inputs must be independently supplied by caller.

    Every accepted or excluded leaf is recomputed and all children must form an
    exact partition of the root. Truncations, unreachable nodes and resource-
    limited/abstaining producer results are rejected.
    """
    try:
        history, mixture, epsilon = _validate_inputs(history, mixture, epsilon, max_nodes)
        _require(isinstance(result, dict) and result.get('decision') == 'ALLOW' and
                 result.get('reason') == 'outward_bounds', 'not a completed allow result')
        proof = result['proof']
        _require(type(proof['version']) is int and proof['version'] == 1 and
                 proof['alpha'] == '0.05', 'wrong proof version or alpha')
        _require(isinstance(proof['history'], list) and all(
            isinstance(event, list) and len(event) == 2 and type(event[1]) is bool
            for event in proof['history']), 'invalid history metadata types')
        _require(proof['history'] == [list(e) for e in history], 'history metadata mismatch')
        _require(proof['mixture'] == [list(m) for m in mixture], 'mixture metadata mismatch')
        _require(_number(proof['epsilon']) == epsilon, 'service metadata mismatch')
        _require(type(proof['max_nodes']) is int and proof['max_nodes'] == max_nodes,
                 'node cap metadata mismatch')
        nodes = proof['nodes']
        _require(isinstance(nodes, list) and nodes and len(nodes) <= max_nodes and
                 type(result['nodes']) is int and result['nodes'] == len(nodes), 'incomplete node list')
        _require(_parse_box(nodes[0]) == (Decimal('0'), Decimal('.25'),
                                          Decimal('.05'), Decimal('.4')), 'root does not cover prior')
        thresholds = _thresholds(history, mixture)
        witness = result['witness']
        _require(isinstance(witness, (tuple, list)) and len(witness) == 2, 'invalid witness')
        theta, tau = map(_number, witness)
        _require(Decimal(0) <= theta <= Decimal('.25') and
                 Decimal('.05') <= tau <= Decimal('.4'), 'witness outside prior')
        witness_prefixes = _prefixes(history, I(str(theta)), I(str(tau)))
        _require(all(value.lo > cutoff.hi for value, cutoff in zip(witness_prefixes, thresholds)),
                 'witness is not strictly feasible')

        pending, visited = [0], set()
        accepted = []
        while pending:
            index = pending.pop()
            _require(type(index) is int and 0 <= index < len(nodes) and index not in visited,
                     'invalid, duplicated, or cyclic node')
            visited.add(index)
            node = nodes[index]
            box = _parse_box(node)
            theta_box, tau_box = I(str(box[0]), str(box[1])), I(str(box[2]), str(box[3]))
            kind = node['kind']
            if kind == 'split':
                children = node['children']
                _require(isinstance(children, list) and len(children) == 2 and
                         all(type(i) is int and 0 <= i < len(nodes) for i in children) and
                         children[0] != children[1], 'invalid children')
                _require(_partition(box, _parse_box(nodes[children[0]]),
                                    _parse_box(nodes[children[1]])), 'children do not partition parent')
                pending.extend(children)
            elif kind == 'exclude':
                prefix = node['prefix']
                _require(type(prefix) is int and 0 <= prefix < len(history), 'invalid exclusion prefix')
                value = _prefixes(history, theta_box, tau_box)[prefix]
                cutoff = thresholds[prefix]
                _require(value.hi <= cutoff.lo, 'exclusion not proven')
                _require(_number(node['likelihood_upper']) == value.hi and
                         _number(node['threshold_lower']) == cutoff.lo, 'exclusion bound mismatch')
            elif kind == 'accept':
                benefit, service = _bounds(theta_box, tau_box)
                _require(benefit.lo > 0 and service.hi <= epsilon, 'acceptance bounds do not pass')
                _require(_number(node['benefit_lower']) == benefit.lo and
                         _number(node['service_upper']) == service.hi, 'acceptance bound mismatch')
                accepted.append((benefit.lo, service.hi))
            else:
                raise ReplayError('unknown or unfinished node kind')
        _require(len(visited) == len(nodes) and accepted, 'unreachable node or no accepted leaf')
        _require(_number(result['benefit_lower']) == min(x[0] for x in accepted) and
                 _number(result['candidate_service_upper']) == max(x[1] for x in accepted) and
                 _number(result['baseline_service_upper']) == 0, 'global bound mismatch')
        return True, 'complete tree and bounds replayed'
    except (ReplayError, ArithmeticError, TypeError, ValueError, KeyError, IndexError) as exc:
        return False, str(exc) or type(exc).__name__
