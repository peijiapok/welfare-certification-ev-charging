"""Strict explicit-feedback event replay; one writer, no cross-process locking.

Checkpoint writes fsync the file, atomically replace it, then fsync its directory.
This is a local checkpoint, not a distributed database. Offer IDs are opaque.
"""

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .core import Assistant, Feedback, Preferences


def atomic_json(path, value):
    path = Path(path)
    # Parent creation is caller-owned so misspelled destinations fail visibly.
    encoded = json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary is not None:
            os.unlink(temporary)


def _keys(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"expected fields {sorted(expected)}")


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")


class ProfileStore:
    """Persist onboarding, explicit weight revisions, and uninterpreted responses."""

    def __init__(self, path):
        self.path = Path(path)
        value = json.loads(self.path.read_text()) if self.path.exists() else {"schema_version": 1, "events": []}
        self._assistant, self._events = self._replay(value)

    @staticmethod
    def _replay(value):
        _keys(value, {"schema_version", "events"})
        if type(value["schema_version"]) is not int or value["schema_version"] != 1:
            raise ValueError("unsupported profile schema")
        if not isinstance(value["events"], list):
            raise ValueError("events must be a list")
        assistant, seen = Assistant(), set()
        for seq, event in enumerate(value["events"], 1):
            _keys(event, {"sequence", "event_id", "driver_id", "kind", "source", "recorded_at", "payload"})
            if type(event["sequence"]) is not int or event["sequence"] != seq:
                raise ValueError("event sequence must be contiguous and ordered")
            for field in ("event_id", "driver_id", "recorded_at"):
                _text(event[field], field)
            if event["event_id"] in seen:
                raise ValueError("duplicate event ID")
            seen.add(event["event_id"])
            if event["source"] not in ("declared", "synthetic"):
                raise ValueError("source must be declared or synthetic")
            stamp = datetime.fromisoformat(event["recorded_at"])
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("recorded_at must be timezone aware")
            payload, driver = event["payload"], event["driver_id"]
            if event["kind"] == "onboarding":
                _keys(payload, {"cost", "readiness", "delay"})
                assistant.register(driver, Preferences(**payload))
            elif event["kind"] == "explicit_adjustment":
                _keys(payload, {"cost_delta", "readiness_delta", "delay_delta"})
                assistant.feedback(driver, Feedback(**payload))
            elif event["kind"] == "response":
                _keys(payload, {"offer_id", "response"})
                assistant.preferences(driver, "static")  # Known driver, no update.
                _text(payload["offer_id"], "offer_id")
                if payload["response"] not in ("accept", "reject", "modify", "override"):
                    raise ValueError("unknown response")
            else:
                raise ValueError("unknown event kind")
        return assistant, value["events"]

    @property
    def events(self):
        return tuple(json.loads(json.dumps(self._events)))

    def preferences(self, driver_id, mode):
        return self._assistant.preferences(driver_id, mode)

    def recommend(self, *args, **kwargs):
        return self._assistant.recommend(*args, **kwargs)

    def _append(self, event_id, driver_id, kind, source, payload):
        event = {"sequence": len(self._events) + 1, "event_id": event_id,
                 "driver_id": driver_id, "kind": kind, "source": source,
                 "recorded_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
        candidate = {"schema_version": 1, "events": self._events + [event]}
        assistant, events = self._replay(candidate)
        atomic_json(self.path, candidate)
        self._assistant, self._events = assistant, events

    def register(self, event_id, driver_id, preferences: Preferences, *, source):
        if not isinstance(preferences, Preferences):
            raise ValueError("preferences must be Preferences")
        self._append(event_id, driver_id, "onboarding", source, asdict(preferences))

    def feedback(self, event_id, driver_id, feedback: Feedback, *, source):
        if not isinstance(feedback, Feedback):
            raise ValueError("feedback must be Feedback")
        self._append(event_id, driver_id, "explicit_adjustment", source, asdict(feedback))

    def response(self, event_id, driver_id, offer_id, response, *, source):
        self._append(event_id, driver_id, "response", source,
                     {"offer_id": offer_id, "response": response})
