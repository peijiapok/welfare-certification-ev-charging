"""Exact-rational two-driver one-port reset; only executed offers give labels."""
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from personalized_charging.variable_physics_exploratory_v1.physical import _number


@dataclass(frozen=True)
class Event:
    driver: str | None
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

    @property
    def feedback(self):
        return tuple((e.driver, e.offer, e.accepted) for e in self.events if e.offer is not None)


def simulate(role, plan, *, g0, g1, g2, W, delta, theta_a, theta_b,
             p_a, r_a, third_a, p_b, r_b, third_b,
             u_A_p, u_A_r, u_A_third, u_B_p, u_B_r, u_B_third, u_urgent):
    """One AB or BA reset; numeric inputs are exact decimal strings.

    Each driver requires 1 kWh, each slot is half an hour, and port power is
    2 kW. The caller supplies correctly coupled, fresh innovations. The urgent
    penalty is assigned to the operator account as a ledger convention.
    """
    if role not in ('AB', 'BA') or plan not in ('baseline', 'first_p', 'second_r', 'first_third', 'candidate'):
        raise ValueError('unknown role or plan')
    procurement_rates = tuple(_number(v, k) for v, k in ((g0, 'g0'), (g1, 'g1'), (g2, 'g2')))
    penalty = _number(W, 'W')
    arrival = _number(delta, 'delta', maximum=Decimal('1'))
    theta = {'A': _number(theta_a, 'theta_a', maximum=Decimal('.25')),
             'B': _number(theta_b, 'theta_b', maximum=Decimal('.25'))}
    probabilities = {
        ('A', 'p'): _number(p_a, 'p_a', maximum=Decimal('1')),
        ('A', 'r'): _number(r_a, 'r_a', maximum=Decimal('1')),
        ('A', 'third'): _number(third_a, 'third_a', maximum=Decimal('1')),
        ('B', 'p'): _number(p_b, 'p_b', maximum=Decimal('1')),
        ('B', 'r'): _number(r_b, 'r_b', maximum=Decimal('1')),
        ('B', 'third'): _number(third_b, 'third_b', maximum=Decimal('1')),
    }
    raw = {('A', 'p'): u_A_p, ('A', 'r'): u_A_r, ('A', 'third'): u_A_third,
           ('B', 'p'): u_B_p, ('B', 'r'): u_B_r, ('B', 'third'): u_B_third}
    draws = {key: _number(value, 'u_'+key[0]+'_'+key[1], maximum=Decimal('1'), strict_max=True)
             for key, value in raw.items()}
    urgent_draw = _number(u_urgent, 'u_urgent', maximum=Decimal('1'), strict_max=True)
    occupied = [False, False, False]
    events = []
    procurement = delay = retail = Fraction(0)

    def focal(driver, slot, offer):
        nonlocal procurement, delay, retail
        response = draws[(driver, offer)] < probabilities[(driver, offer)] if offer else None
        assigned = 2 if response else slot
        if occupied[assigned]:
            raise ArithmeticError('slot already committed')
        occupied[assigned] = True
        procurement += procurement_rates[assigned]
        delay += theta[driver] * Fraction(assigned-slot, 2)
        retail += (Fraction(3, 10) if offer == 'third' else Fraction(2, 5)) if response else Fraction(1, 2)
        events.append(Event(driver, 'first' if slot == 0 else 'second', offer, response,
                            assigned, tuple(occupied)))

    first, second = role
    first_offer = ('p' if plan in ('first_p', 'candidate') else
                   'third' if plan == 'first_third' else None)
    focal(first, 0, first_offer)
    second_offer = 'r' if plan in ('second_r', 'candidate') and not occupied[2] else None
    focal(second, 1, second_offer)
    unmet = 0
    if urgent_draw < arrival:
        if occupied[2]:
            assigned, unmet = None, 1
        else:
            occupied[2] = True
            procurement += procurement_rates[2]
            retail += Fraction(2, 5)
            assigned = 2
        events.append(Event(None, 'urgent', None, None, assigned, tuple(occupied)))
    unmet_penalty = penalty * unmet
    driver_cost = retail + delay
    operator_cost = procurement + unmet_penalty - retail
    return Episode(tuple(events), procurement, delay, unmet_penalty, retail, driver_cost,
                   operator_cost, procurement+delay+unmet_penalty, unmet)
