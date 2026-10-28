"""Conservative three-contrast, count-only confidence gate for toy P3c physics.

Inputs are observed acceptance and total counts, never hidden preferences.
Conditional Bernoulli responses use one persistent common logit shift. The
three fixed contrasts are (.1,1), (.1,.5), (.2,1), in credits and hours.
This prototype shares P3d Decimal interval primitives and has not been used
in a scientific experiment.
"""
from decimal import Decimal

from personalized_charging.p3d_diagnostic_v1.interval import (
    I, directed, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_EVEN,
)

MAX_COUNT = 10**12
CONTRASTS = ('p', 'r', 'third')
ONE = I('1')
ZERO = Decimal('0')


def _next_minus(value):
    return directed(ROUND_FLOOR, lambda context: context.next_minus(value))


def _next_plus(value):
    return directed(ROUND_CEILING, lambda context: context.next_plus(value))


def log_interval(value):
    """Enclose ln(x), using correct HALF_EVEN rounding plus adjacent values."""
    if value.lo <= ZERO:
        raise ArithmeticError('logarithm requires a positive interval')
    lower = directed(ROUND_HALF_EVEN, lambda context: context.ln(value.lo))
    upper = directed(ROUND_HALF_EVEN, lambda context: context.ln(value.hi))
    return I(_next_minus(lower), _next_plus(upper))


def radius_upper(n):
    """Upper bound on sqrt(log(120*n*(n+1))/(2*n)), with n exact."""
    if type(n) is not int or not 1 <= n <= MAX_COUNT:
        raise ValueError('n must be an integer between 1 and MAX_COUNT')
    argument = Decimal(str(120 * n * (n + 1)))
    logarithm = directed(ROUND_HALF_EVEN, lambda context: context.ln(argument))
    logarithm_upper = _next_plus(logarithm)
    quotient_upper = directed(ROUND_CEILING, lambda context: context.divide(
        logarithm_upper, Decimal(str(2 * n))))
    root = directed(ROUND_HALF_EVEN, lambda context: context.sqrt(quotient_upper))
    return _next_plus(root)


def _counts(data):
    if not isinstance(data, dict) or set(data) != set(CONTRASTS):
        raise ValueError('counts must contain exactly p, r and third')
    result = {}
    for contrast in CONTRASTS:
        pair = data[contrast]
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError('each count must be (accepts, total)')
        successes, total = pair
        if (type(successes) is not int or type(total) is not int or
                not 0 <= successes <= total <= MAX_COUNT):
            raise ValueError('invalid or excessive count')
        result[contrast] = (successes, total)
    return result


def probability_band(successes, total):
    """Closed outward band and point-interval empirical proportion."""
    if (type(successes) is not int or type(total) is not int or
            not 0 <= successes <= total <= MAX_COUNT):
        raise ValueError('invalid or excessive count')
    if total == 0:
        raise ValueError('probability band requires at least one sample')
    empirical = I(str(successes)) / I(str(total))
    radius = I(radius_upper(total))
    lower = max(ZERO, (empirical - radius).lo)
    upper = min(Decimal('1'), (empirical + radius).hi)
    return I(lower, upper), empirical


def logit(value):
    """Monotonic endpoint enclosure of log(x/(1-x)) for an interior band."""
    if value.lo <= ZERO or value.hi >= Decimal('1'):
        raise ArithmeticError('logit band touches zero or one')
    lower = log_interval(I(value.lo) / (ONE - I(value.lo)))
    upper = log_interval(I(value.hi) / (ONE - I(value.hi)))
    return I(lower.lo, upper.hi)


def central_witness(empirical):
    """Verify prior feasibility of the exact model fitting empirical centers.

    Three empirical proportions uniquely determine lambda, theta and c through
    the logits. Every returned interval contains its exact central value; if
    a parameter enclosure crosses a prior boundary, the proof is inconclusive.
    """
    logits = [logit(empirical[key]) for key in CONTRASTS]
    lam = I('10') * (logits[2] - logits[0])
    v = I('2') * (logits[1] - logits[0])
    if lam.lo <= ZERO:
        return None
    theta = v / lam
    tau = ONE / lam
    shift = logits[0] - I('0.1') * lam + v
    if not (Decimal('0') <= theta.lo <= theta.hi <= Decimal('0.25') and
            Decimal('0.05') <= tau.lo <= tau.hi <= Decimal('0.4')):
        return None
    return {'lambda': lam.json(), 'theta_over_tau': v.json(),
            'theta': theta.json(), 'tau': tau.json(), 'common_shift': shift.json()}


def theta_outer(bands):
    """Enclose feasible theta without breaking common-model correlations."""
    lp, lr, lt = [logit(bands[key]) for key in CONTRASTS]
    lam_raw = I('10') * (lt - lp)
    v_raw = I('2') * (lr - lp)
    lam_lo, lam_hi = max(lam_raw.lo, Decimal('2.5')), min(lam_raw.hi, Decimal('20'))
    v_lo, v_hi = max(v_raw.lo, ZERO), min(v_raw.hi, Decimal('5'))
    if lam_lo > lam_hi or v_lo > v_hi or lam_lo <= ZERO:
        return None
    theta_lo = max(ZERO, (I(v_lo) / I(lam_hi)).lo)
    theta_hi = min(Decimal('0.25'), (I(v_hi) / I(lam_lo)).hi)
    if theta_lo > theta_hi:
        return None
    return I(theta_lo, theta_hi)


def benefit_service_bounds(p, r, theta):
    """Outer extrema; benefit is decreasing in theta and bilinear in p,r."""
    if not (ZERO <= p.lo <= p.hi <= 1 and ZERO <= r.lo <= r.hi <= 1 and
            ZERO <= theta.lo <= theta.hi <= Decimal('0.25')):
        raise ArithmeticError('bounds outside the declared model domain')

    def corner(prob_p, prob_r, preference):
        pp, rr, th = I(prob_p), I(prob_r), I(preference)
        return pp * (I('0.07') - th) + (ONE - pp) * rr * (I('0.05') - th / I('2'))

    low = min(corner(pp, rr, theta.hi).lo for pp in (p.lo, p.hi) for rr in (r.lo, r.hi))
    high = max(corner(pp, rr, theta.lo).hi for pp in (p.lo, p.hi) for rr in (r.lo, r.hi))
    # The exact function p+(1-p)r is nondecreasing in each probability.
    pp, rr = I(p.hi), I(r.hi)
    service_upper = (I('0.005') * (pp + (ONE - pp) * rr)).hi
    return I(low, high), min(service_upper, Decimal('0.005'))


def evaluate(data, *, epsilon='0.005'):
    """Return ALLOW only after a nonempty-set, benefit and service proof."""
    counts = _counts(data)
    if not isinstance(epsilon, str):
        raise ValueError('epsilon must be an exact decimal string')
    allowance = Decimal(epsilon)
    if not allowance.is_finite() or allowance < 0:
        raise ValueError('epsilon must be finite and nonnegative')
    if any(total == 0 for _, total in counts.values()):
        return {'decision': 'ABSTAIN', 'reason': 'missing_contrast'}
    try:
        pairs = {key: probability_band(*counts[key]) for key in CONTRASTS}
        bands = {key: pair[0] for key, pair in pairs.items()}
        empirical = {key: pair[1] for key, pair in pairs.items()}
        if any(value.lo <= ZERO or value.hi >= Decimal('1') for value in bands.values()):
            return {'decision': 'ABSTAIN', 'reason': 'noninterior_probability_band',
                    'bands': {key: value.json() for key, value in bands.items()}}
        outer = theta_outer(bands)
        if outer is None:
            return {'decision': 'ABSTAIN', 'reason': 'empty_or_nonpositive_outer'}
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
    except ArithmeticError:
        return {'decision': 'ABSTAIN', 'reason': 'arithmetic_failure'}
