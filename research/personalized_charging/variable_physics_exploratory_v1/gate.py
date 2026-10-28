"""Variable known physical costs over audited common-shift inference bounds.

The known inputs are exact decimal strings. The imported inference gates
retain their original confidence assumptions and shared Decimal arithmetic.
No hidden driver parameter is supplied here.
"""
from decimal import Decimal, InvalidOperation

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.two_contrast_bias_exploratory_v1.gate import evaluate as two_evaluate
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import evaluate as three_evaluate

ONE = I('1')
ZERO = Decimal('0')


def _known_decimal(value, label, maximum=None):
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError(f'{label} must be an exact decimal string')
    number = Decimal(value)
    if not number.is_finite() or number < ZERO or (maximum is not None and number > maximum):
        raise ValueError(f'{label} outside domain')
    # Restrict input precision/exponent to a reviewed working range rather than
    # silently relying on Decimal underflow/subnormal behavior at extremes.
    if len(number.as_tuple().digits) > 80 or (number and not -100 <= number.adjusted() <= 100):
        raise ValueError(f'{label} exceeds supported precision or exponent')
    return number


def coefficients(g0, g1, g2, delta, penalty):
    """Outward a,b enclosures; inputs are exact nonnegative Decimal objects."""
    g0, g1, g2, delta, penalty = map(I, (g0, g1, g2, delta, penalty))
    urgent_increment = delta * (penalty - g2)
    return g0 - g2 - urgent_increment, g1 - g2 - urgent_increment


def benefit_service_bounds(p, r, theta, a, b, delta):
    if not (ZERO <= p.lo <= p.hi <= 1 and ZERO <= r.lo <= r.hi <= 1 and
            ZERO <= theta.lo <= theta.hi <= Decimal('0.25') and
            ZERO <= delta.lo <= delta.hi <= 1):
        raise ArithmeticError('invalid common-model box')
    def corner(pp, rr, tt):
        pp, rr, tt = I(pp), I(rr), I(tt)
        return pp * (a - tt) + (ONE - pp) * rr * (b - tt / I('2'))
    lower = min(corner(pp, rr, theta.hi).lo for pp in (p.lo, p.hi) for rr in (r.lo, r.hi))
    upper = max(corner(pp, rr, theta.lo).hi for pp in (p.lo, p.hi) for rr in (r.lo, r.hi))
    pp, rr = I(p.hi), I(r.hi)
    service = (delta * (pp + (ONE - pp) * rr)).hi
    return I(lower, upper), min(service, delta.hi)


def evaluate(counts, *, method, g0, g1, g2, W, delta, epsilon):
    """Re-evaluate valid inference outputs for the supplied known physics."""
    try:
        if method not in ('two', 'three'):
            raise ValueError('method must be two or three')
        g0, g1, g2 = (_known_decimal(v, label) for v, label in
                      ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
        penalty = _known_decimal(W, 'W')
        delta = _known_decimal(delta, 'delta', Decimal('1'))
        allowance = _known_decimal(epsilon, 'epsilon')
    except (ValueError, TypeError, InvalidOperation):
        return {'decision': 'ABSTAIN', 'reason': 'invalid_physics'}
    try:
        inference = (two_evaluate if method == 'two' else three_evaluate)(counts, epsilon=epsilon)
        if (not isinstance(inference, dict) or inference.get('decision') not in ('ALLOW', 'ABSTAIN') or
                inference.get('reason') not in ('outward_bounds', 'benefit_not_positive', 'service_not_certified')):
            return {'decision': 'ABSTAIN', 'reason': 'inference_unresolved',
                    'inference_reason': inference.get('reason') if isinstance(inference, dict) else None}
        if not inference.get('central_witness'):
            return {'decision': 'ABSTAIN', 'reason': 'inference_unresolved'}
        p, r = (I(*inference['bands'][key]) for key in ('p', 'r'))
        theta = I(*inference['theta_outer'])
        a, b = coefficients(g0, g1, g2, delta, penalty)
        benefit, service = benefit_service_bounds(p, r, theta, a, b, I(delta))
        permitted = benefit.lo > ZERO and service <= allowance
        reason = ('outward_bounds' if permitted else
                  'benefit_not_positive' if benefit.lo <= ZERO else 'service_not_certified')
        return {'decision': 'ALLOW' if permitted else 'ABSTAIN', 'reason': reason,
                'inference_reason': inference['reason'], 'bands': inference['bands'],
                'central_witness': inference['central_witness'], 'theta_outer': theta.json(),
                'a': a.json(), 'b': b.json(), 'benefit_interval': benefit.json(),
                'candidate_service_upper': str(service), 'baseline_service_upper': '0'}
    except (ArithmeticError, ValueError, TypeError, KeyError, IndexError):
        return {'decision': 'ABSTAIN', 'reason': 'arithmetic_or_inference_failure'}
