"""Offline choice-to-reservation integration, with explicit offer-consent expiry.

Owns a static-horizon Book; no execution clock, persistence or cross-store
transaction. Clock rollback before issue is caught; rollback within the offer
window can resurrect an expired unaccepted offer and is not detected. A digest
identifies content, never freshness: every first acceptance revalidates Book.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from threading import RLock
from uuid import uuid4

from .choices import ChoiceProfile
from .core import Assistant, Option, Preferences, Recommendation, Request, Site, feasible_options, number
from .profiles import _text
from .reservations import OfferUnavailable, ReservationBook


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _aware(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("horizon and injected clock must be timezone-aware datetimes")
    return value.astimezone(timezone.utc)


def _request_key(request):
    # Request has no optional/collection fields. Canonicalize the two numeric
    # energy/power fields so 4 and 4.0 denote identical requirements.
    value = asdict(request)
    for field in ("energy_kwh", "vehicle_max_kw"):
        value[field] = float(value[field])
    return _digest(value)


@dataclass(frozen=True)
class ChoiceOffer:
    offer_id: str
    driver_id: str
    request_revision_id: str
    horizon_id: str
    horizon_start_utc: str
    issued_at_utc: str
    expires_at_utc: str
    request: Request
    recommendation: Recommendation | None
    alpha: float | None
    weights: tuple[float, float, float] | None
    profile_sha256: str
    reservation_digest: str
    content_sha256: str
    selected_option: Option | None = None
    selection_source: str = "model_recommendation"
    menu_content_sha256: str = ""
    menu_offer_id: str | None = None
    selected_menu_index: int | None = None

    @property
    def option(self):
        return self.selected_option if self.selected_option is not None else self.recommendation.option


def _menu_digest(options, remaining, revision):
    return _digest({"options": [asdict(o) for o in options], "remaining": asdict(remaining),
                    "forecast_revision": revision})


class ChoiceReservationBridge:
    """Per-process request revisions and expiring consent; profiles are caller-owned.

    Call accept on this bridge, using its opaque offer ID. Underlying Book IDs
    are private. Accepted offers stay allocated/idempotent after offer expiry.
    Same driver/revision may have alternative proposals for identical Request;
    changed requirements need a new revision. Restart forgets this in-memory map.
    """

    def __init__(self, site: Site, *, horizon_id, horizon_start, clock,
                 offer_ttl_seconds=300):
        _text(horizon_id, "horizon_id")
        number(offer_ttl_seconds, "offer_ttl_seconds")
        if offer_ttl_seconds <= 0 or not callable(clock):
            raise ValueError("positive offer TTL and injected clock required")
        self._book = ReservationBook(site)
        self._horizon_id = horizon_id
        self._horizon_start = _aware(horizon_start)
        self._clock = clock
        self._ttl = timedelta(seconds=offer_ttl_seconds)
        self._offers, self._accepted, self._request_versions = {}, {}, {}
        self._menus = {}
        self._cancelled = set()
        self._lock = RLock()

    @property
    def horizon_id(self):
        return self._horizon_id

    @property
    def horizon_start(self):
        return self._horizon_start

    @property
    def forecast_revision(self):
        return self._book.forecast_revision

    @property
    def reservations(self):
        with self._lock:
            return tuple(self._accepted.values())

    def remaining_site(self):
        return self._book.remaining_site()

    def replace_forecast(self, site):
        with self._lock:
            self._book.replace_forecast(site)

    def propose(self, profile: ChoiceProfile, request_revision_id, mode, request: Request):
        if not isinstance(profile, ChoiceProfile) or not isinstance(request, Request):
            raise ValueError("typed ChoiceProfile and Request required")
        _text(request_revision_id, "request_revision_id")
        with self._lock:
            key = (profile.driver_id, request_revision_id)
            request_key = _request_key(request)
            if key in self._request_versions and self._request_versions[key] != request_key:
                raise OfferUnavailable("changed requirements need a new request revision ID")
            # A standalone replay snapshot binds alpha and profile provenance to
            # this immutable offer. Later feedback cannot silently change it.
            profile_payload = profile.to_dict()
            snapshot = ChoiceProfile.from_dict(profile_payload)
            alpha = snapshot.alpha(mode)
            weights = Preferences(alpha, 1 - alpha, 0)
            assistant = Assistant(weights)
            assistant.register(snapshot.driver_id, weights)
            issued = _aware(self._clock())
            remaining = self._book.remaining_site()
            options = feasible_options(remaining, request)
            offer = self._book.propose(assistant, snapshot.driver_id, request_revision_id, mode, request)
            menu_hash = _menu_digest(options, remaining, offer.forecast_revision)
            wrapped = self._wrap(offer, issued, alpha, (weights.cost, weights.readiness, weights.delay),
                                 _digest(profile_payload), menu_hash)
            self._menus[wrapped.offer_id] = (options, remaining, offer.forecast_revision)
            self._request_versions[key] = request_key
            return wrapped

    def _wrap(self, offer, issued, alpha, weights, profile_hash, menu_hash, *, menu=None, index=None):
        scheduled_start = self.horizon_start + timedelta(
            hours=self._book.remaining_site().slot_hours * offer.option.start_slot)
        expires = min(issued + self._ttl, scheduled_start)
        if menu is not None:
            expires = min(expires, datetime.fromisoformat(menu.expires_at_utc))
        if expires <= issued:
            self._book.cancel(offer.offer_id)
            raise OfferUnavailable("chosen scheduled start is not in the future")
        payload = {"offer_id": uuid4().hex, "driver_id": offer.driver_id,
                   "request_revision_id": offer.request_id, "horizon_id": self.horizon_id,
                   "horizon_start_utc": self.horizon_start.isoformat(), "issued_at_utc": issued.isoformat(),
                   "expires_at_utc": expires.isoformat(), "request": offer.request,
                   "recommendation": offer.recommendation, "alpha": alpha, "weights": weights,
                   "profile_sha256": profile_hash, "reservation_digest": offer.content_sha256,
                   "selected_option": offer.selected_option, "selection_source": offer.selection_source,
                   "menu_content_sha256": menu_hash,
                   "menu_offer_id": menu.offer_id if menu is not None else None,
                   "selected_menu_index": index}
        # Hash the same dataclass-normalized representation checked by accept.
        wrapped = ChoiceOffer(**payload, content_sha256="")
        canonical = asdict(wrapped)
        canonical.pop("content_sha256")
        wrapped = ChoiceOffer(**payload, content_sha256=_digest(canonical))
        self._offers[wrapped.offer_id] = (wrapped, offer.offer_id)
        return wrapped

    def _pending(self, offer_id):
        if offer_id not in self._offers or offer_id in self._cancelled:
            raise OfferUnavailable("unknown or cancelled bridge offer")
        wrapped, underlying_id = self._offers[offer_id]
        if wrapped.menu_offer_id in self._cancelled:
            raise OfferUnavailable("displayed menu was cancelled")
        now = _aware(self._clock())
        if now < datetime.fromisoformat(wrapped.issued_at_utc):
            raise OfferUnavailable("clock precedes issue time")
        if now >= datetime.fromisoformat(wrapped.expires_at_utc):
            raise OfferUnavailable("offer expired; obtain explicit fresh consent")
        payload = asdict(wrapped)
        content_hash = payload.pop("content_sha256")
        if content_hash != _digest(payload):
            raise OfferUnavailable("bridge offer content changed")
        return wrapped, underlying_id

    def menu_options(self, menu_offer_id):
        """Canonical immutable menu; UI must display these exact indexed entries."""
        with self._lock:
            menu, _ = self._pending(menu_offer_id)
            if menu_offer_id not in self._menus or menu_offer_id in self._accepted:
                raise OfferUnavailable("not an unaccepted displayed menu")
            options, remaining, revision = self._menus[menu_offer_id]
            if menu.menu_content_sha256 != _menu_digest(options, remaining, revision):
                raise OfferUnavailable("displayed menu content changed")
            return options

    def propose_selected(self, menu_offer_id, selected_index):
        """Bind an exact displayed option; booking is separate from learning.

        Menu expiry is conservative even if the selected option starts later.
        No capacity is held until accept; first successful commit wins.
        """
        with self._lock:
            options = self.menu_options(menu_offer_id)
            if type(selected_index) is not int or not 0 <= selected_index < len(options):
                raise OfferUnavailable("selected schedule is outside the displayed menu")
            menu, _ = self._pending(menu_offer_id)
            _, remaining, revision = self._menus[menu_offer_id]
            offer = self._book.propose_selected(menu.driver_id, menu.request_revision_id,
                                               menu.request, options[selected_index],
                                               expected_site=remaining, expected_revision=revision)
            return self._wrap(offer, _aware(self._clock()), None, None, menu.profile_sha256,
                              menu.menu_content_sha256, menu=menu, index=selected_index)

    def accept(self, offer_id):
        with self._lock:
            if offer_id in self._accepted:
                return self._accepted[offer_id]  # No clock gate or second Book call.
            wrapped, underlying_id = self._pending(offer_id)
            self._book.accept(underlying_id)  # Digest never replaces feasibility revalidation.
            self._accepted[offer_id] = wrapped
            return wrapped

    def cancel(self, offer_id):
        with self._lock:
            if offer_id not in self._offers or offer_id in self._cancelled:
                return False
            _, underlying_id = self._offers[offer_id]
            self._book.cancel(underlying_id)
            self._cancelled.add(offer_id)
            self._accepted.pop(offer_id, None)
            return True
