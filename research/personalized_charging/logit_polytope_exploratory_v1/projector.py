"""Exact rational 2-D projection with outward shared logit/band arithmetic.

This is a conservative method-inspired research prototype, not a claim to
implement PRISM or the original Schnitzer et al. software. Statistical
validity assumes the fixed common-shift conditional Bernoulli model.
"""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from itertools import combinations

from personalized_charging.p3d_diagnostic_v1.interval import I, sigmoid
from personalized_charging.three_contrast_confidence_exploratory_v1.gate import MAX_COUNT, logit
from personalized_charging.two_driver_exploratory_v1.gate import probability_band, benefit_service_bounds
from personalized_charging.variable_physics_exploratory_v1.gate import _known_decimal, coefficients

ZERO = Decimal('0')
OFFSETS = {'p': (Fraction(0), Fraction(0)),
           'r': (Fraction(0), Fraction(1, 2)),
           'third': (Fraction(1, 10), Fraction(0))}


def _fraction_interval(value):
    return I(str(value.numerator)) / I(str(value.denominator))


def vertices(constraints):
    """Enumerate all vertices of a bounded rational polygon a*x+b*y<=c.

    The caller must supply the compact lambda/v prior constraints. Exact
    arithmetic handles full-dimensional, line and singleton feasible sets.
    """
    constraints = tuple(tuple(Fraction(x) for x in row) for row in constraints)
    found = set()
    for (a, b, c), (d, e, f) in combinations(constraints, 2):
        determinant = a*e-b*d
        if determinant == 0:
            continue
        x, y = (c*e-b*f)/determinant, (a*f-c*d)/determinant
        if all(u*x+v*y <= w for u, v, w in constraints):
            found.add((x, y))
    return tuple(sorted(found))


def _validate_bands(bands, method):
    if method not in ('two', 'three') or not isinstance(bands, dict):
        raise ValueError('invalid method or band mapping')
    required = ('p', 'r') if method == 'two' else ('p', 'r', 'third')
    if not set(required) <= set(bands) <= set(OFFSETS):
        raise ValueError('missing or extra bands')
    parsed = {}
    for key in required:
        value = bands[key]
        if isinstance(value, I):
            interval = value
        elif isinstance(value, (tuple, list)) and len(value) == 2 and all(isinstance(x, str) for x in value):
            interval = I(*value)
        else:
            raise ValueError('band endpoints must be exact decimal strings')
        if not ZERO <= interval.lo <= interval.hi <= Decimal('1'):
            raise ValueError('band outside [0,1]')
        if interval.lo == interval.hi and interval.lo in (ZERO, Decimal('1')):
            raise ValueError('singleton zero/one incompatible with finite logits')
        parsed[key] = interval
    return parsed


def _logit_constraints(bands):
    """Use only finite logit sides, each relaxed outward before rational use."""
    lower, upper = {}, {}
    for key, band in bands.items():
        if band.lo > ZERO:
            lower[key] = Fraction(logit(I(band.lo)).lo)
        if band.hi < Decimal('1'):
            upper[key] = Fraction(logit(I(band.hi)).hi)
    return lower, upper


def _polygon_constraints(lower, upper):
    # lambda in [5/2,20], v in [0,lambda/4].
    constraints = [(Fraction(-1), Fraction(0), Fraction(-5, 2)),
                   (Fraction(1), Fraction(0), Fraction(20)),
                   (Fraction(0), Fraction(-1), Fraction(0)),
                   (Fraction(-1, 4), Fraction(1), Fraction(0))]
    for lo_key, lo in lower.items():
        for hi_key, hi in upper.items():
            # h >= lo - s_lo and h <= hi - s_hi.
            lo_lam, lo_v = OFFSETS[lo_key]
            hi_lam, hi_v = OFFSETS[hi_key]
            constraints.append((hi_lam-lo_lam, hi_v-lo_v, hi-lo))
    return tuple(constraints)


def _slope(contrast, lam, v):
    a, b = OFFSETS[contrast]
    return a*lam+b*v


def _verified_witness(points, lower, upper, bands):
    """Find a finite h/lambda/v witness and check original probability bands."""
    if not points:
        return None
    centroid = (sum((p[0] for p in points), Fraction())/len(points),
                sum((p[1] for p in points), Fraction())/len(points))
    for lam, v in (centroid, *points):
        h_lows = [value-_slope(key, lam, v) for key, value in lower.items()]
        h_highs = [value-_slope(key, lam, v) for key, value in upper.items()]
        low = max(h_lows) if h_lows else None
        high = min(h_highs) if h_highs else None
        if low is not None and high is not None:
            if low > high:
                continue
            h = (low+high)/2
        elif low is not None:
            h = low+1
        elif high is not None:
            h = high-1
        else:
            h = Fraction(0)
        ok = True
        for key, band in bands.items():
            if band.lo == ZERO and band.hi == 1:
                continue
            z = _fraction_interval(h+_slope(key, lam, v))
            try:
                q = sigmoid(z)
            except ArithmeticError:
                ok = False
                break
            if q.lo < band.lo or q.hi > band.hi:
                ok = False
                break
        if ok:
            return {'h': str(h), 'lambda': str(lam), 'v': str(v),
                    'theta': str(v/lam), 'tau': str(1/lam),
                    'common_shift': str(h-Fraction(1, 10)*lam+v)}
    return None


def project_bands(bands, *, method):
    """Project one driver's supplied outward probability bands; no data access."""
    try:
        bands = _validate_bands(bands, method)
        lower, upper = _logit_constraints(bands)
        constraints = _polygon_constraints(lower, upper)
        points = vertices(constraints)
        if not points:
            return {'status': 'ABSTAIN', 'reason': 'empty_outer'}
        witness = _verified_witness(points, lower, upper, bands)
        if witness is None:
            return {'status': 'ABSTAIN', 'reason': 'unverified_feasibility'}
        values = [v/lam for lam, v in points]
        exact_low, exact_high = min(values), max(values)
        low, high = _fraction_interval(exact_low).lo, _fraction_interval(exact_high).hi
        return {'status': 'PROJECTED', 'reason': 'verified_witness',
                'bands': {key: value.json() for key, value in bands.items()},
                'theta_outer': [str(low), str(high)],
                'theta_bounds_exact_outer': [str(exact_low), str(exact_high)],
                'vertices': [[str(lam), str(v)] for lam, v in points],
                'witness': witness}
    except (ArithmeticError, ValueError, TypeError, InvalidOperation, KeyError):
        return {'status': 'ABSTAIN', 'reason': 'invalid_or_numerical'}


def project_driver(counts, *, method):
    """Construct alpha/6 time-uniform bands, with [0,1] for n=0."""
    try:
        if method not in ('two', 'three') or not isinstance(counts, dict):
            raise ValueError('invalid method or counts')
        required = ('p', 'r') if method == 'two' else ('p', 'r', 'third')
        if not set(required) <= set(counts) <= set(OFFSETS):
            raise ValueError('missing or extra streams')
        bands = {}
        for key in required:
            pair = counts[key]
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError('invalid count pair')
            successes, total = pair
            if (type(successes) is not int or type(total) is not int or
                    not 0 <= successes <= total <= MAX_COUNT):
                raise ValueError('invalid count')
            bands[key] = I('0', '1') if total == 0 else probability_band(successes, total)[0]
        return project_bands(bands, method=method)
    except (ArithmeticError, ValueError, TypeError, InvalidOperation):
        return {'status': 'ABSTAIN', 'reason': 'invalid_or_numerical'}


def evaluate(counts, *, method, g0, g1, g2, W, delta, epsilon):
    """Conservative AB decision using separately projected driver models."""
    try:
        if not isinstance(counts, dict) or set(counts) != {'A', 'B'} or method not in ('two', 'three'):
            raise ValueError('invalid driver counts or method')
        g0, g1, g2 = (_known_decimal(value, name) for value, name in
                      ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
        penalty = _known_decimal(W, 'W')
        delta = _known_decimal(delta, 'delta', Decimal('1'))
        allowance = _known_decimal(epsilon, 'epsilon')
        projections = {driver: project_driver(counts[driver], method=method) for driver in ('A', 'B')}
        if any(value['status'] != 'PROJECTED' for value in projections.values()):
            return {'decision': 'ABSTAIN', 'reason': 'projection_unresolved', 'projections': projections}
        p = I(*projections['A']['bands']['p'])
        r = I(*projections['B']['bands']['r'])
        ta, tb = (I(*projections[driver]['theta_outer']) for driver in ('A', 'B'))
        a, b = coefficients(g0, g1, g2, delta, penalty)
        benefit, service = benefit_service_bounds(p, r, ta, tb, a, b, I(delta))
        allowed = benefit.lo > ZERO and service <= allowance
        reason = ('outward_bounds' if allowed else
                  'benefit_not_positive' if benefit.lo <= ZERO else 'service_not_certified')
        return {'decision': 'ALLOW' if allowed else 'ABSTAIN', 'reason': reason,
                'benefit_interval': benefit.json(), 'candidate_service_upper': str(service),
                'baseline_service_upper': '0', 'a': a.json(), 'b': b.json(),
                'projections': projections}
    except (ArithmeticError, ValueError, TypeError, InvalidOperation, KeyError):
        return {'decision': 'ABSTAIN', 'reason': 'invalid_or_numerical'}
