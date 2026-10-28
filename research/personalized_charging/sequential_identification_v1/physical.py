"""Deterministic one-port episode with externally supplied innovations.

Retail offer contrasts determine responses; procurement costs determine the
physical objective. The fixed policy selector is public and never receives the
latent model, probabilities, or draws. The caller is responsible for supplying
conditionally independent uniform innovations, including across episodes.
"""

from dataclasses import dataclass
from math import exp, fsum, isfinite


PROCUREMENT = (0.568, 0.548, 0.4)
URGENT_PROBABILITY = 1 / 200
URGENT_PENALTY = 20.0
POLICIES = frozenset(("baseline", "collect_p", "collect_r", "candidate"))


@dataclass(frozen=True)
class Event:
    """Observable physical outcome; absent offers have no binary feedback."""

    request: str
    offer: str | None
    accepted: bool | None
    assigned_slot: int | None
    occupied_after: tuple[bool, bool, bool]


@dataclass(frozen=True)
class Episode:
    """Events are policy-visible; utility and its components are evaluator-only."""

    events: tuple[Event, ...]
    procurement_cost: float
    delay_loss: float
    unmet_penalty: float
    loss: float
    utility: float
    unmet_kwh: float


def _number(value, name, low, high, *, include_high=True):
    if (isinstance(value, bool) or not isinstance(value, (float, int))
            or not isfinite(value) or value < low
            or value > high or (not include_high and value == high)):
        bound = "]" if include_high else ")"
        raise ValueError(f"{name} must be finite and in [{low}, {high}{bound}")


def _sigmoid(x):
    # The declared domain makes |x| <= 3; this avoids overflow more generally.
    if x >= 0:
        return 1 / (1 + exp(-x))
    e = exp(x)
    return e / (1 + e)


def simulate_episode(policy, theta, tau, u_p, u_r, u_urgent, *,
                     p_response=None, r_response=None):
    """Execute a reset episode with three half-hour slots and one 2 kW port.

    Policies: baseline defaults both; collect_p offers p only; collect_r
    offers r only; candidate offers p and, only after its rejection, r.
    Each focal request is 1 kWh. An urgent 1 kWh request, when present,
    arrives in slot 2 and must finish in that slot. Loss counts procurement,
    additional delay relative to the focal default, and urgent shortfall.
    Uniform inputs are in [0,1); equal numeric draws are not prohibited,
    because distinct independent random variables can take equal values.
    The optional response overrides allow explicitly labeled misspecification
    scenarios; model-based guarantees apply only when the actual response law
    matches the declared logistic law. Overrides do not alter true welfare.
    """
    if policy not in POLICIES:
        raise ValueError("unknown policy")
    _number(theta, "theta", 0, .25)
    _number(tau, "tau", .05, .4)
    for name, value in (("u_p", u_p), ("u_r", u_r), ("u_urgent", u_urgent)):
        _number(value, name, 0, 1, include_high=False)
    for name, value in (("p_response", p_response), ("r_response", r_response)):
        if value is not None:
            _number(value, name, 0, 1)

    p = _sigmoid((.1 - theta) / tau) if p_response is None else p_response
    r = _sigmoid((.1 - theta / 2) / tau) if r_response is None else r_response
    occupied = [False, False, False]
    events = []
    procurement, delay, penalty = [], [], 0.0

    def focal(request, default_slot, offer, accepted):
        # A slot-2 commitment prevents a later slot-2 offer, and neither
        # default collides with any earlier valid commitment.
        slot = 2 if accepted is True else default_slot
        if occupied[slot]:
            raise RuntimeError("physical slot already committed")
        occupied[slot] = True
        procurement.append(PROCUREMENT[slot])
        delay.append(theta * (slot - default_slot) * .5)
        events.append(Event(request, offer, accepted, slot, tuple(occupied)))

    offer_p = policy in ("collect_p", "candidate")
    p_accepted = bool(u_p < p) if offer_p else None
    focal("first", 0, "p" if offer_p else None, p_accepted)

    offer_r = policy in ("collect_r", "candidate") and not occupied[2]
    r_accepted = bool(u_r < r) if offer_r else None
    focal("second", 1, "r" if offer_r else None, r_accepted)

    unmet = 0.0
    if u_urgent < URGENT_PROBABILITY:
        if occupied[2]:
            unmet = 1.0
            penalty = URGENT_PENALTY
            assigned = None
        else:
            occupied[2] = True
            procurement.append(PROCUREMENT[2])
            assigned = 2
        events.append(Event("urgent", None, None, assigned, tuple(occupied)))

    procurement_cost, delay_loss = fsum(procurement), fsum(delay)
    loss = fsum((procurement_cost, delay_loss, penalty))
    return Episode(tuple(events), procurement_cost, delay_loss, penalty,
                   loss, -loss, unmet)
