"""No-data pointwise favorable rule under the full fixed P3c prior."""
from decimal import Decimal, InvalidOperation

from personalized_charging.variable_physics_exploratory_v1.gate import (
    _known_decimal, coefficients,
)


def evaluate(*, g0, g1, g2, W, delta, epsilon):
    """Certify pointwise B>0 and U<=epsilon, without a uniform gain margin.

    Finite logits imply 0<p,r<1. The true theta is in [0,.25], and the
    common logit shift is finite but unrestricted. This rule uses no data.
    """
    try:
        g0, g1, g2 = (_known_decimal(v, label) for v, label in
                      ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
        penalty = _known_decimal(W, 'W')
        delta = _known_decimal(delta, 'delta', Decimal('1'))
        allowance = _known_decimal(epsilon, 'epsilon')
        a, b = coefficients(g0, g1, g2, delta, penalty)
        if allowance < delta:
            return {'decision': 'ABSTAIN', 'reason': 'service_not_certified',
                    'a': a.json(), 'b': b.json(), 'service_upper': str(delta)}
        enough = (a.lo >= Decimal('0.25') and b.lo >= Decimal('0.125') and
                  (a.lo > Decimal('0.25') or b.lo > Decimal('0.125')))
        return {'decision': 'ALLOW' if enough else 'ABSTAIN',
                'reason': 'prior_pointwise_positive' if enough else 'prior_not_certified',
                'a': a.json(), 'b': b.json(), 'service_upper': str(delta),
                'uniform_positive_margin': False}
    except (ValueError, TypeError, ArithmeticError, InvalidOperation):
        return {'decision': 'ABSTAIN', 'reason': 'invalid_or_arithmetic_failure'}
