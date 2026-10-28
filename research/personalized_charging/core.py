"""Shared feasibility and explicit preference ranking; no learned user model."""

from dataclasses import dataclass
from math import fsum, isclose, isfinite
from sys import float_info


def number(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value < minimum:
        raise ValueError(f"{name} must be finite and >= {minimum}")


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


@dataclass(frozen=True)
class Site:
    """Fixed forecasts for one additional vehicle; residual power excludes other load."""

    slot_hours: float
    residual_kw: tuple[float, ...]
    available_ports: tuple[int, ...]
    price_per_kwh: tuple[float, ...]
    charger_kw: float

    def __post_init__(self):
        for field in ("residual_kw", "available_ports", "price_per_kwh"):
            object.__setattr__(self, field, tuple(getattr(self, field)))
        number(self.slot_hours, "slot_hours")
        number(self.charger_kw, "charger_kw")
        if self.slot_hours == 0 or self.charger_kw == 0:
            raise ValueError("slot_hours and charger_kw must be positive")
        if not self.residual_kw or not (len(self.residual_kw) == len(self.available_ports) == len(self.price_per_kwh)):
            raise ValueError("site forecasts must have equal nonzero lengths")
        for x in self.residual_kw:
            number(x, "residual_kw")
        for x in self.available_ports:
            integer(x, "available_ports")
        for x in self.price_per_kwh:
            number(x, "price_per_kwh")


@dataclass(frozen=True)
class Request:
    arrival_slot: int
    ready_by_slot: int
    energy_kwh: float
    max_delay_slots: int
    vehicle_max_kw: float

    def __post_init__(self):
        integer(self.arrival_slot, "arrival_slot")
        integer(self.ready_by_slot, "ready_by_slot", 1)
        integer(self.max_delay_slots, "max_delay_slots")
        number(self.energy_kwh, "energy_kwh")
        number(self.vehicle_max_kw, "vehicle_max_kw")
        if self.energy_kwh == 0 or self.vehicle_max_kw == 0 or self.arrival_slot >= self.ready_by_slot:
            raise ValueError("positive energy/power and arrival before deadline required")


@dataclass(frozen=True)
class Preferences:
    cost: float = 1
    readiness: float = 1
    delay: float = 1

    def __post_init__(self):
        for name in ("cost", "readiness", "delay"):
            number(getattr(self, name), name)
        total = self.cost + self.readiness + self.delay
        if not isfinite(total) or total <= 0:
            raise ValueError("preference weights need a finite positive sum")
        for name in ("cost", "readiness", "delay"):
            object.__setattr__(self, name, getattr(self, name) / total)


@dataclass(frozen=True)
class Feedback:
    """Explicit requested weight changes, each bounded to [-0.25, 0.25]."""

    cost_delta: float = 0
    readiness_delta: float = 0
    delay_delta: float = 0

    def __post_init__(self):
        for value in (self.cost_delta, self.readiness_delta, self.delay_delta):
            number(value, "feedback delta", -0.25)
            if value > 0.25:
                raise ValueError("feedback delta must be <= 0.25")


@dataclass(frozen=True)
class Option:
    start_slot: int
    completion_slot: float
    energy_by_slot: tuple[float, ...]
    cost: float


class NoFeasibleOption(ValueError):
    pass


def feasible_options(site: Site, request: Request) -> tuple[Option, ...]:
    """Enumerate delayed starts; charge continuously at forecast available power.

    The final slot may be partial. A port is required in every occupied slot.
    No pausing across unavailable slots, export, battery losses or reservations.
    """
    if request.ready_by_slot > len(site.residual_kw):
        raise ValueError("deadline exceeds forecast horizon")
    options = []
    last_start = min(request.arrival_slot + request.max_delay_slots, request.ready_by_slot - 1)
    for start in range(request.arrival_slot, last_start + 1):
        remaining = request.energy_kwh
        energy = [0.0] * len(site.residual_kw)
        for slot in range(start, request.ready_by_slot):
            power = min(site.charger_kw, request.vehicle_max_kw, site.residual_kw[slot])
            if site.available_ports[slot] < 1 or power <= 0:
                break
            capacity = power * site.slot_hours
            if not isfinite(capacity) or capacity <= 0:
                raise ValueError("slot energy capacity must be finite and positive")
            delivered = min(remaining, capacity)
            energy[slot] = delivered
            # Stable summation avoids accumulating subtraction error. Accept only
            # machine-roundoff scale deficits (no absolute kWh allowance), while
            # keeping every slot's actual delivery within its physical capacity.
            delivered_total = fsum(energy[start:slot + 1])
            remaining = max(0.0, request.energy_kwh - delivered_total)
            if remaining == 0 or isclose(delivered_total, request.energy_kwh,
                                         rel_tol=8 * float_info.epsilon, abs_tol=0):
                completion = slot + delivered / capacity
                cost = sum(e * p for e, p in zip(energy, site.price_per_kwh))
                if not isfinite(cost):
                    raise ValueError("computed cost must be finite")
                options.append(Option(start, completion, tuple(energy), cost))
                break
    if not options:
        raise NoFeasibleOption("No start meets requested energy, ready-by, delay, power and port constraints; revise the request or forecasts explicitly.")
    return tuple(options)


@dataclass(frozen=True)
class Recommendation:
    mode: str
    option: Option
    score: float
    explanation: str


def preference_score(option: Option, options: tuple[Option, ...], request: Request,
                     weights: Preferences) -> float:
    """Score against the identical full feasible option set, never a menu subset.

    Normalize before multiplying so the two-feature choice model has the same
    floating-point feature units. Malformed/non-finite public inputs raise.
    """
    cost_scale = max(max(o.cost for o in options), 1e-12)
    duration = request.ready_by_slot - request.arrival_slot
    features = (option.cost / cost_scale,
                (option.completion_slot - request.arrival_slot) / duration,
                (option.start_slot - request.arrival_slot) / duration)
    if not isfinite(cost_scale) or not all(isfinite(f) for f in features):
        raise ValueError("normalized ranking features must be finite")
    return weights.cost * features[0] + weights.readiness * features[1] + weights.delay * features[2]


class Assistant:
    """Static onboarding profiles plus isolated, bounded feedback heuristic."""

    def __init__(self, generic=Preferences()):
        self.generic = generic
        self._static = {}
        self._adaptive = {}

    def register(self, driver_id: str, preferences: Preferences):
        if not isinstance(driver_id, str) or not driver_id.strip() or driver_id in self._static:
            raise ValueError("driver ID must be a new nonempty string")
        if not isinstance(preferences, Preferences):
            raise ValueError("preferences must be Preferences")
        self._static[driver_id] = preferences
        self._adaptive[driver_id] = preferences

    def preferences(self, driver_id, mode):
        if driver_id not in self._static:
            raise ValueError("unknown driver")
        if mode == "generic":
            return self.generic
        if mode == "static":
            return self._static[driver_id]
        if mode == "adaptive":
            return self._adaptive[driver_id]
        raise ValueError("mode must be generic, static or adaptive")

    def feedback(self, driver_id: str, feedback: Feedback):
        current = self.preferences(driver_id, "adaptive")
        if not isinstance(feedback, Feedback):
            raise ValueError("feedback must be Feedback")
        values = [max(0, min(1, weight + delta)) for weight, delta in zip(
            (current.cost, current.readiness, current.delay),
            (feedback.cost_delta, feedback.readiness_delta, feedback.delay_delta))]
        # A fully cancelled vector contains no usable preference signal.
        if sum(values) == 0:
            raise ValueError("feedback cannot cancel all preference weights")
        self._adaptive[driver_id] = Preferences(*values)

    def recommend(self, driver_id: str, mode: str, site: Site, request: Request) -> Recommendation:
        weights = self.preferences(driver_id, mode)
        options = feasible_options(site, request)
        def score(option):
            return preference_score(option, options, request, weights)
        chosen = min(options, key=lambda o: (score(o), o.start_slot))
        explanation = (
            f"{mode}: start slot {chosen.start_slot}, finish {chosen.completion_slot:.3f} "
            f"by deadline {request.ready_by_slot}; deliver {request.energy_kwh:g} kWh; "
            f"cost {chosen.cost:.3f}. Minimum weighted cost/readiness/delay score "
            f"using weights {weights.cost:.3f}/{weights.readiness:.3f}/{weights.delay:.3f}; "
            f"{len(options)} feasible starts; ties choose earliest start. Forecast feasibility only."
        )
        return Recommendation(mode, chosen, score(chosen), explanation)
