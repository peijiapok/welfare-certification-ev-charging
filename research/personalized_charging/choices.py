"""One-dimensional preference inference from explicitly displayed choices.

This finite-grid Bayesian choice model is not RL. Posterior-mean alpha gives
the minimum expected linear score because E[alpha*C+(1-alpha)*T] is linear in
E[alpha]. It cannot recover separate readiness and start-delay preferences.
"""

from dataclasses import asdict, dataclass
import json
from math import exp, fsum, log, log1p

from .core import Request, Site, feasible_options, integer, number
from .profiles import _keys, _text, atomic_json


GRID = tuple(i / 20 for i in range(21))
MODEL = {"grid": list(GRID), "temperature": .10, "prior_sd": .15,
         "features": "max_feasible_cost_and_completion_since_arrival_v1"}


@dataclass(frozen=True)
class ChoiceExposure:
    exposure_id: str
    site: Site
    request: Request
    pair_indices: tuple[int, int]
    source: str
    instrumentation_control: bool = False

    def __post_init__(self):
        _text(self.exposure_id, "exposure_id")
        if not isinstance(self.site, Site) or not isinstance(self.request, Request):
            raise ValueError("exposure needs typed site and request")
        object.__setattr__(self, "pair_indices", tuple(self.pair_indices))
        if len(self.pair_indices) != 2:
            raise ValueError("exactly two displayed alternatives required")
        options = self.options
        for index in self.pair_indices:
            integer(index, "option index")
            if index >= len(options):
                raise ValueError("displayed option index outside feasible set")
        if self.source not in ("declared", "synthetic"):
            raise ValueError("source must be declared or synthetic")
        if type(self.instrumentation_control) is not bool:
            raise ValueError("instrumentation_control must be boolean")
        identical = self.pair_indices[0] == self.pair_indices[1]
        if self.instrumentation_control:
            if self.source != "synthetic" or not identical:
                raise ValueError("instrumentation controls must be synthetic identical-option pairs")
        elif identical:
            raise ValueError("displayed alternatives must be distinct")

    @property
    def options(self):
        return feasible_options(self.site, self.request)

    @property
    def features(self):
        options = self.options
        cost_scale = max(max(o.cost for o in options), 1e-12)
        duration = self.request.ready_by_slot - self.request.arrival_slot
        return tuple((o.cost / cost_scale,
                      (o.completion_slot - self.request.arrival_slot) / duration)
                     for o in options)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        _keys(value, {"exposure_id", "site", "request", "pair_indices", "source", "instrumentation_control"})
        return cls(value["exposure_id"], Site(**value["site"]), Request(**value["request"]),
                   value["pair_indices"], value["source"], value["instrumentation_control"])


def linear_score(alpha, features):
    return alpha * features[0] + (1 - alpha) * features[1]


class ChoiceProfile:
    """One driver's replayable posterior; only explicit menu selections update it."""

    def __init__(self, driver_id: str, onboarding_alpha: float):
        _text(driver_id, "driver_id")
        number(onboarding_alpha, "onboarding_alpha")
        if onboarding_alpha > 1:
            raise ValueError("onboarding_alpha must be <= 1")
        self.driver_id = driver_id
        self.onboarding_alpha = onboarding_alpha
        logits = tuple(-.5 * ((a - onboarding_alpha) / MODEL["prior_sd"]) ** 2 for a in GRID)
        self._prior = self._normalize(logits)
        self._log_weights = self._prior
        self._events = []

    @staticmethod
    def _normalize(logits):
        maximum = max(logits)
        normalizer = maximum + log(fsum(exp(x - maximum) for x in logits))
        return tuple(x - normalizer for x in logits)

    @property
    def probabilities(self):
        return tuple(exp(x) for x in self._log_weights)

    @property
    def log_probabilities(self):
        return self._log_weights

    @property
    def prior_log_probabilities(self):
        return self._prior

    def alpha(self, mode="adaptive"):
        if mode == "generic":
            return .5
        if mode == "static":
            weights = self._prior
        elif mode == "adaptive":
            weights = self._log_weights
        else:
            raise ValueError("mode must be generic, static or adaptive")
        return fsum(a * exp(p) for a, p in zip(GRID, weights))

    def recommend(self, exposure: ChoiceExposure, mode="adaptive", *, displayed_only=False):
        if not isinstance(exposure, ChoiceExposure):
            raise ValueError("exposure must be ChoiceExposure")
        alpha = self.alpha(mode)
        indices = exposure.pair_indices if displayed_only else range(len(exposure.options))
        features = exposure.features
        index = min(indices, key=lambda i: (linear_score(alpha, features[i]), exposure.options[i].start_slot))
        return index

    def observe(self, event_id: str, exposure: ChoiceExposure, selected_index: int):
        _text(event_id, "event_id")
        if not isinstance(exposure, ChoiceExposure):
            raise ValueError("exposure must be ChoiceExposure")
        integer(selected_index, "selected_index")
        if selected_index not in (0, 1):
            raise ValueError("selected_index identifies one of the two displayed alternatives")
        if any(e["event_id"] == event_id or e["exposure"]["exposure_id"] == exposure.exposure_id
               for e in self._events):
            raise ValueError("duplicate feedback event or already answered exposure")
        features = exposure.features
        selected = features[exposure.pair_indices[selected_index]]
        other = features[exposure.pair_indices[1 - selected_index]]
        candidate = self._log_weights
        if selected != other:
            likelihoods = []
            for alpha in GRID:
                margin = (linear_score(alpha, other) - linear_score(alpha, selected)) / MODEL["temperature"]
                likelihoods.append(-log1p(exp(-margin)) if margin >= 0 else margin - log1p(exp(margin)))
            candidate = self._normalize(tuple(p + ll for p, ll in zip(self._log_weights, likelihoods)))
        event = {"sequence": len(self._events) + 1, "event_id": event_id,
                 "exposure": exposure.to_dict(), "selected_index": selected_index}
        self._events = self._events + [event]
        self._log_weights = candidate

    def to_dict(self):
        # JSON copying prevents callers from mutating stored event/context payloads.
        return json.loads(json.dumps({"schema_version": 1, "model": MODEL,
                                      "driver_id": self.driver_id,
                                      "onboarding_alpha": self.onboarding_alpha,
                                      "events": self._events}))

    @classmethod
    def from_dict(cls, value):
        _keys(value, {"schema_version", "model", "driver_id", "onboarding_alpha", "events"})
        if type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["model"] != MODEL:
            raise ValueError("unsupported choice schema or model specification")
        profile = cls(value["driver_id"], value["onboarding_alpha"])
        if not isinstance(value["events"], list):
            raise ValueError("events must be a list")
        for seq, event in enumerate(value["events"], 1):
            _keys(event, {"sequence", "event_id", "exposure", "selected_index"})
            if type(event["sequence"]) is not int or event["sequence"] != seq:
                raise ValueError("choice events must be contiguous and ordered")
            profile.observe(event["event_id"], ChoiceExposure.from_dict(event["exposure"]), event["selected_index"])
        return profile

    def save(self, path):
        atomic_json(path, self.to_dict())

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as handle:
            return cls.from_dict(json.load(handle))
