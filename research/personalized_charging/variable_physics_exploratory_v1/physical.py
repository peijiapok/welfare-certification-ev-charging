"""Exact-rational synthetic three-slot episode with supplied innovations.

Retail prices are .5 at default, .4 for p/r delayed offers, .3 for the third
collection-only promotion, and .4 for served urgent energy. Within the
equal-weight operator/driver boundary they cancel. The urgent penalty is
assigned to the operator account solely as a declared accounting convention.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction


def _number(value, name, *, maximum=None, strict_max=False):
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError(f'{name} must be an exact decimal string')
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f'invalid {name}') from exc
    if (not number.is_finite() or number < 0 or
            (maximum is not None and (number > maximum or (strict_max and number == maximum)))):
        raise ValueError(f'{name} outside domain')
    if len(number.as_tuple().digits) > 80 or (number and not -100 <= number.adjusted() <= 100):
        raise ValueError(f'{name} exceeds supported precision or exponent')
    return Fraction(number)


@dataclass(frozen=True)
class Event:
    request: str
    offer: str | None
    accepted: bool | None
    assigned_slot: int | None
    occupied_after: tuple[bool, bool, bool]


@dataclass(frozen=True)
class Episode:
    events: tuple[Event, ...]
    procurement: Fraction
    added_delay: Fraction
    unmet_penalty: Fraction
    retail_payment: Fraction
    driver_private_cost: Fraction
    operator_private_cost: Fraction
    system_cost: Fraction
    unmet_kwh: int


def simulate(policy, *, g0, g1, g2, W, delta, theta, p, r, third,
             u_p, u_r, u_third, u_urgent):
    """Execute one reset episode; all numeric inputs are exact decimal strings.

    The caller must supply independent uniforms consistent with the declared
    response and urgency laws for expected-value claims. Observable events do
    not contain hidden welfare parameters or unexposed responses.
    """
    if policy not in ('baseline', 'candidate', 'collect_p', 'collect_r', 'collect_third'):
        raise ValueError('unknown policy')
    prices = tuple(_number(value, name) for value, name in ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
    penalty = _number(W, 'W')
    delta = _number(delta, 'delta', maximum=Decimal('1'))
    theta = _number(theta, 'theta', maximum=Decimal('0.25'))
    probs = {key: _number(value, key, maximum=Decimal('1'))
             for key, value in (('p', p), ('r', r), ('third', third))}
    draws = {key: _number(value, 'u_'+key, maximum=Decimal('1'), strict_max=True)
             for key, value in (('p', u_p), ('r', u_r), ('third', u_third), ('urgent', u_urgent))}
    occupied = [False, False, False]
    events = []
    procurement = delay = retail = Fraction(0)

    def focal(request, default_slot, offer):
        nonlocal procurement, delay, retail
        accepted = draws[offer] < probs[offer] if offer else None
        slot = 2 if accepted else default_slot
        if occupied[slot]:
            raise ArithmeticError('committed slot already occupied')
        occupied[slot] = True
        procurement += prices[slot]
        delay += theta * Fraction(slot-default_slot, 2)
        retail += (Fraction(3, 10) if offer == 'third' else Fraction(2, 5)) if accepted else Fraction(1, 2)
        events.append(Event(request, offer, accepted, slot, tuple(occupied)))

    first_offer = ('third' if policy == 'collect_third' else
                   'p' if policy in ('candidate', 'collect_p') else None)
    focal('first', 0, first_offer)
    second_offer = 'r' if policy in ('candidate', 'collect_r') and not occupied[2] else None
    focal('second', 1, second_offer)

    unmet = 0
    if draws['urgent'] < delta:
        if occupied[2]:
            unmet = 1
            assigned = None
        else:
            occupied[2] = True
            procurement += prices[2]
            retail += Fraction(2, 5)
            assigned = 2
        events.append(Event('urgent', None, None, assigned, tuple(occupied)))
    unmet_penalty = penalty * unmet
    driver = retail + delay
    operator = procurement + unmet_penalty - retail
    system = procurement + delay + unmet_penalty
    return Episode(tuple(events), procurement, delay, unmet_penalty, retail,
                   driver, operator, system, unmet)
