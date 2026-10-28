"""Single-process, fixed-horizon conservative forecast reservations.

Power is constant within each slot. Every occupied slot, including the partial
final slot, reserves its full charging power and one port for the entire slot.
This can reject physically possible sub-slot sharing. No physical control.
"""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import fsum
from threading import RLock
from uuid import uuid4

from .core import Assistant, Option, Recommendation, Request, Site, feasible_options


class OfferUnavailable(ValueError):
    """Offer is stale, cancelled, or conflicts; request a fresh proposal."""


def _digest(revision, site, request, recommendation, reserved_kw,
            selected_option=None, selection_source="model_recommendation"):
    payload = [revision, asdict(site), asdict(request),
               asdict(recommendation) if recommendation is not None else None,
               reserved_kw, asdict(selected_option) if selected_option is not None else None,
               selection_source]
    return sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Offer:
    offer_id: str
    driver_id: str
    request_id: str
    forecast_revision: int
    request: Request
    recommendation: Recommendation | None
    reserved_kw: tuple[float, ...]
    content_sha256: str
    selected_option: Option | None = None
    selection_source: str = "model_recommendation"

    @property
    def option(self):
        return self.selected_option if self.selected_option is not None else self.recommendation.option


class ReservationBook:
    def __init__(self, site: Site):
        if not isinstance(site, Site):
            raise ValueError("site must be Site")
        self._site = site
        self._revision = 0
        self._offers = {}
        self._active = {}
        self._cancelled = set()
        self._lock = RLock()

    @property
    def forecast_revision(self):
        with self._lock:
            return self._revision

    @property
    def reservations(self):
        with self._lock:
            return tuple(self._active.values())

    def _remaining(self, site, active):
        power, ports = [], []
        for slot, limit in enumerate(site.residual_kw):
            used = fsum(o.reserved_kw[slot] for o in active.values())
            occupied = sum(o.reserved_kw[slot] > 0 for o in active.values())
            # No capacity tolerance: conservatively reject even tiny overbooking.
            if used > limit or occupied > site.available_ports[slot]:
                raise OfferUnavailable("accepted reservations exceed forecast power or ports")
            power.append(limit - used)
            ports.append(site.available_ports[slot] - occupied)
        return Site(site.slot_hours, tuple(power), tuple(ports), site.price_per_kwh, site.charger_kw)

    def remaining_site(self):
        with self._lock:
            return self._remaining(self._site, self._active)

    def propose(self, assistant: Assistant, driver_id: str, request_id: str,
                mode: str, request: Request) -> Offer:
        if not isinstance(request_id, str) or not request_id.strip():
            raise ValueError("request_id must be a nonempty string")
        with self._lock:
            remaining = self._remaining(self._site, self._active)
            recommendation = assistant.recommend(driver_id, mode, remaining, request)
            return self._issue(driver_id, request_id, request, remaining, recommendation)

    def propose_selected(self, driver_id, request_id, request, option, *,
                         expected_site, expected_revision):
        """Issue the exact menu member; no ranking or synthetic model score."""
        if (not isinstance(driver_id, str) or not driver_id.strip()
                or not isinstance(request_id, str) or not request_id.strip()
                or not isinstance(request, Request)):
            raise ValueError("driver/request identity and typed Request required")
        with self._lock:
            remaining = self._remaining(self._site, self._active)
            if self._revision != expected_revision or remaining != expected_site:
                raise OfferUnavailable("displayed physical context changed; request a new menu")
            options = feasible_options(remaining, request)
            if option not in options:
                raise OfferUnavailable("selected schedule is not feasible in the displayed menu")
            # Store the internally computed immutable canonical value, never caller data.
            selected = options[options.index(option)]
            return self._issue(driver_id, request_id, request, remaining, None, selected)

    def _issue(self, driver_id, request_id, request, remaining, recommendation,
               selected_option=None):
        option = selected_option if selected_option is not None else recommendation.option
        source = "driver_selected" if selected_option is not None else "model_recommendation"
        power = tuple(min(remaining.charger_kw, request.vehicle_max_kw, remaining.residual_kw[s])
                      if energy > 0 else 0.0
                      for s, energy in enumerate(option.energy_by_slot))
        offer_id = uuid4().hex
        offer = Offer(offer_id, driver_id, request_id, self._revision, request,
                      recommendation, power,
                      _digest(self._revision, self._site, request, recommendation, power,
                              selected_option, source), selected_option, source)
        self._offers[offer_id] = offer
        return offer

    def accept(self, offer_id: str) -> Offer:
        with self._lock:
            if offer_id in self._active:
                return self._active[offer_id]
            if offer_id not in self._offers or offer_id in self._cancelled:
                raise OfferUnavailable("unknown or cancelled offer")
            offer = self._offers[offer_id]
            if offer.forecast_revision != self._revision:
                raise OfferUnavailable("forecast changed; obtain a new offer")
            if offer.content_sha256 != _digest(offer.forecast_revision, self._site, offer.request,
                                               offer.recommendation, offer.reserved_kw,
                                               offer.selected_option, offer.selection_source):
                raise OfferUnavailable("offer content changed")
            if any((o.driver_id, o.request_id) == (offer.driver_id, offer.request_id)
                   for o in self._active.values()):
                raise OfferUnavailable("request already has an accepted offer")
            candidate = dict(self._active)
            candidate[offer_id] = offer
            self._remaining(self._site, candidate)
            self._active = candidate
            return offer

    def cancel(self, offer_id: str) -> bool:
        with self._lock:
            if offer_id not in self._offers or offer_id in self._cancelled:
                return False
            candidate = dict(self._active)
            candidate.pop(offer_id, None)
            self._active = candidate
            self._cancelled = self._cancelled | {offer_id}
            return True

    def replace_forecast(self, site: Site):
        if not isinstance(site, Site):
            raise ValueError("site must be Site")
        with self._lock:
            if (site.slot_hours != self._site.slot_hours
                    or len(site.residual_kw) != len(self._site.residual_kw)):
                raise OfferUnavailable("fixed horizon and slot duration cannot change")
            if self._active and (site.price_per_kwh != self._site.price_per_kwh
                                 or site.charger_kw != self._site.charger_kw):
                raise OfferUnavailable("cannot change committed tariffs or charger rating")
            self._remaining(site, self._active)
            self._site = site
            self._revision += 1
