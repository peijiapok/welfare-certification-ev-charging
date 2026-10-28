"""Two-driver AB system comparison with six-stream confidence allocation.

Driver parameters persist and response probabilities are conditionally fixed
for each offered contrast. Inputs contain observed counts and known physics,
not hidden preferences. Shared Decimal primitives are not an independent
numerical implementation.
"""
from decimal import Decimal, InvalidOperation

from personalized_charging.p3d_diagnostic_v1.interval import I, directed, ROUND_CEILING, ROUND_HALF_EVEN
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import (
    MAX_COUNT, log_interval, _next_plus,
    theta_outer as three_theta_outer, central_witness as three_witness,
)
from personalized_charging.two_contrast_bias_exploratory_v1.gate import (
    theta_outer as two_theta_outer, central_witness as two_witness,
)
from personalized_charging.variable_physics_exploratory_v1.gate import _known_decimal, coefficients
from personalized_charging.variable_physics_exploratory_v1.prior_gate import evaluate as prior_only

ZERO = Decimal('0')
ONE = I('1')


def radius_upper(n):
    """Outward h(n)=sqrt(log(240*n*(n+1))/(2*n)); alpha/6 per stream."""
    if type(n) is not int or not 1 <= n <= MAX_COUNT:
        raise ValueError('n outside supported count range')
    argument = I(str(240*n*(n+1)))
    log_upper = log_interval(argument).hi
    quotient = directed(ROUND_CEILING, lambda context: context.divide(log_upper, Decimal(str(2*n))))
    root = directed(ROUND_HALF_EVEN, lambda context: context.sqrt(quotient))
    return _next_plus(root)


def probability_band(successes, total):
    if (type(successes) is not int or type(total) is not int or
            not 0 <= successes <= total <= MAX_COUNT or total == 0):
        raise ValueError('invalid count')
    empirical = I(str(successes)) / I(str(total))
    radius = I(radius_upper(total))
    return I(max(ZERO, (empirical-radius).lo), min(Decimal('1'), (empirical+radius).hi)), empirical


def _counts(data, method):
    if not isinstance(data, dict) or set(data) != {'A', 'B'}:
        raise ValueError('counts must contain exactly A and B')
    required = {'p', 'r'} if method == 'two' else {'p', 'r', 'third'}
    result = {}
    for driver in ('A', 'B'):
        streams = data[driver]
        if not isinstance(streams, dict) or not required <= set(streams) <= {'p', 'r', 'third'}:
            raise ValueError('invalid driver streams')
        result[driver] = {}
        for contrast in sorted(required):
            pair = streams[contrast]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError('invalid count pair')
            s, n = pair
            if type(s) is not int or type(n) is not int or not 0 <= s <= n <= MAX_COUNT:
                raise ValueError('invalid count')
            result[driver][contrast] = (s, n)
    return result


def benefit_service_bounds(p_a, r_b, theta_a, theta_b, a, b, delta):
    """AB system gain extrema over a common-model outer rectangle."""
    if not (ZERO <= p_a.lo <= p_a.hi <= 1 and ZERO <= r_b.lo <= r_b.hi <= 1 and
            ZERO <= theta_a.lo <= theta_a.hi <= Decimal('.25') and
            ZERO <= theta_b.lo <= theta_b.hi <= Decimal('.25') and
            ZERO <= delta.lo <= delta.hi <= 1):
        raise ArithmeticError('invalid interval domain')

    def corner(pp, rr, th_a, th_b):
        pp, rr, th_a, th_b = I(pp), I(rr), I(th_a), I(th_b)
        return pp * (a-th_a) + (ONE-pp)*rr*(b-th_b/I('2'))

    lower = min(corner(pp, rr, theta_a.hi, theta_b.hi).lo
                for pp in (p_a.lo, p_a.hi) for rr in (r_b.lo, r_b.hi))
    upper = max(corner(pp, rr, theta_a.lo, theta_b.lo).hi
                for pp in (p_a.lo, p_a.hi) for rr in (r_b.lo, r_b.hi))
    pp, rr = I(p_a.hi), I(r_b.hi)
    service = (delta*(pp+(ONE-pp)*rr)).hi
    return I(lower, upper), min(service, delta.hi)


def evaluate(counts, *, method, g0, g1, g2, W, delta, epsilon):
    """Return ALLOW only for AB positive expected system advantage and service."""
    try:
        if method not in ('two', 'three'):
            raise ValueError('unknown method')
        counts = _counts(counts, method)
        g0, g1, g2 = (_known_decimal(value, label) for value, label in
                      ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
        W = _known_decimal(W, 'W')
        delta = _known_decimal(delta, 'delta', Decimal('1'))
        allowance = _known_decimal(epsilon, 'epsilon')
    except (ValueError, TypeError, InvalidOperation):
        return {'decision': 'ABSTAIN', 'reason': 'invalid_input'}
    if any(n == 0 for streams in counts.values() for _, n in streams.values()):
        return {'decision': 'ABSTAIN', 'reason': 'missing_stream'}
    try:
        bands, empirical = {}, {}
        for driver, streams in counts.items():
            pairs = {contrast: probability_band(*pair) for contrast, pair in streams.items()}
            bands[driver] = {key: pair[0] for key, pair in pairs.items()}
            empirical[driver] = {key: pair[1] for key, pair in pairs.items()}
        if any(q.lo <= ZERO or q.hi >= 1 for driver in bands.values() for q in driver.values()):
            return {'decision': 'ABSTAIN', 'reason': 'noninterior_probability_band',
                    'bands': {d: {k: v.json() for k, v in streams.items()} for d, streams in bands.items()}}
        outer_function = two_theta_outer if method == 'two' else three_theta_outer
        witness_function = two_witness if method == 'two' else three_witness
        outer = {driver: outer_function(bands[driver]) for driver in ('A', 'B')}
        if any(value is None for value in outer.values()):
            return {'decision': 'ABSTAIN', 'reason': 'empty_or_unresolved_outer'}
        witness = {driver: witness_function(empirical[driver]) for driver in ('A', 'B')}
        if any(value is None for value in witness.values()):
            return {'decision': 'ABSTAIN', 'reason': 'central_witness_not_verified',
                    'theta_outer': {d: value.json() for d, value in outer.items()}}
        a, b = coefficients(g0, g1, g2, delta, W)
        benefit, service = benefit_service_bounds(bands['A']['p'], bands['B']['r'],
                                                  outer['A'], outer['B'], a, b, I(delta))
        allowed = benefit.lo > ZERO and service <= allowance
        reason = ('outward_bounds' if allowed else
                  'benefit_not_positive' if benefit.lo <= ZERO else 'service_not_certified')
        return {'decision': 'ALLOW' if allowed else 'ABSTAIN', 'reason': reason,
                'bands': {d: {k: v.json() for k, v in streams.items()} for d, streams in bands.items()},
                'theta_outer': {d: value.json() for d, value in outer.items()},
                'witness': witness, 'a': a.json(), 'b': b.json(),
                'benefit_interval': benefit.json(), 'candidate_service_upper': str(service),
                'baseline_service_upper': '0'}
    except (ArithmeticError, ValueError, TypeError, KeyError):
        return {'decision': 'ABSTAIN', 'reason': 'arithmetic_failure'}
