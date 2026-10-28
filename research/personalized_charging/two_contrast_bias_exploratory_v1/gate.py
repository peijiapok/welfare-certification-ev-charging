"""Two-contrast common-shift robust gate for the fixed P3c comparison.

Only p/r acceptance counts are inputs. This exploratory gate reuses the
three-contrast alpha/3 bands and shared interval arithmetic; it is not an
independent numerical verification and has not been scientifically evaluated.
"""

from decimal import Decimal, InvalidOperation

from personalized_charging.p3d_diagnostic_v1.interval import I
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import (
    MAX_COUNT, benefit_service_bounds, logit, probability_band,
)

ZERO = Decimal('0')


def _counts(data):
    if not isinstance(data, dict) or set(data) != {'p', 'r'}:
        raise ValueError('counts must contain exactly p and r')
    result = {}
    for name in ('p', 'r'):
        pair = data[name]
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError('each count must be (acceptances,total)')
        successes, total = pair
        if (type(successes) is not int or type(total) is not int or
                not 0 <= successes <= total <= MAX_COUNT):
            raise ValueError('invalid or excessive count')
        result[name] = (successes, total)
    return result


def central_witness(empirical):
    """Verify the exact empirical-center model with lambda=20 and tau=.05."""
    lp, lr = logit(empirical['p']), logit(empirical['r'])
    k = I('2') * (lr - lp)
    if k.lo < ZERO or k.hi > Decimal('5'):
        return None
    theta = k / I('20')
    # lp=.1*lambda-k+c, and lambda is 20 at the chosen witness.
    common_shift = lp - I('2') + k
    if not ZERO <= theta.lo <= theta.hi <= Decimal('0.25'):
        return None
    return {'theta_over_tau': k.json(), 'theta': theta.json(),
            'tau': ['0.05', '0.05'], 'common_shift': common_shift.json()}


def theta_outer(bands):
    """Sharp prior theta envelope for the outer interval of k=theta/tau."""
    lp, lr = logit(bands['p']), logit(bands['r'])
    raw = I('2') * (lr - lp)
    lo, hi = max(ZERO, raw.lo), min(Decimal('5'), raw.hi)
    if lo > hi:
        return None
    theta_lo = max(ZERO, (I(lo) / I('20')).lo)
    theta_hi = min(Decimal('0.25'), (I('0.4') * I(hi)).hi)
    if theta_lo > theta_hi:
        return None
    return I(theta_lo, theta_hi)


def evaluate(data, *, epsilon='0.005'):
    """Certify positive same-model benefit/service or explicitly abstain."""
    try:
        counts = _counts(data)
        if not isinstance(epsilon, str):
            raise ValueError('epsilon must be an exact decimal string')
        allowance = Decimal(epsilon)
        if not allowance.is_finite() or allowance < ZERO:
            raise ValueError('epsilon must be finite and nonnegative')
    except (ValueError, TypeError, InvalidOperation):
        return {'decision': 'ABSTAIN', 'reason': 'invalid_input'}
    if any(total == 0 for _, total in counts.values()):
        return {'decision': 'ABSTAIN', 'reason': 'missing_contrast'}
    try:
        pairs = {key: probability_band(*counts[key]) for key in ('p', 'r')}
        bands = {key: pair[0] for key, pair in pairs.items()}
        empirical = {key: pair[1] for key, pair in pairs.items()}
        if any(value.lo <= ZERO or value.hi >= Decimal('1') for value in bands.values()):
            return {'decision': 'ABSTAIN', 'reason': 'noninterior_probability_band',
                    'bands': {key: value.json() for key, value in bands.items()}}
        outer = theta_outer(bands)
        if outer is None:
            return {'decision': 'ABSTAIN', 'reason': 'empty_outer'}
        witness = central_witness(empirical)
        if witness is None:
            return {'decision': 'ABSTAIN', 'reason': 'central_witness_not_verified',
                    'theta_outer': outer.json()}
        benefit, service = benefit_service_bounds(bands['p'], bands['r'], outer)
        allowed = benefit.lo > ZERO and service <= allowance
        reason = ('outward_bounds' if allowed else
                  'benefit_not_positive' if benefit.lo <= ZERO else 'service_not_certified')
        return {'decision': 'ALLOW' if allowed else 'ABSTAIN', 'reason': reason,
                'bands': {key: value.json() for key, value in bands.items()},
                'theta_outer': outer.json(), 'central_witness': witness,
                'benefit_interval': benefit.json(), 'candidate_service_upper': str(service),
                'baseline_service_upper': '0'}
    except (ArithmeticError, ValueError):
        return {'decision': 'ABSTAIN', 'reason': 'arithmetic_failure'}
