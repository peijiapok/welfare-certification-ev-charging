"""As-of driver-declared requirement snapshots, never factual charging replay.

Caller supplies normalized input versions. No database is opened, no future
outcome fields accepted, and absent site/vehicle integration stays missing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from .core import integer, number
from .profiles import _text


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be an ISO string with explicit timezone")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("invalid ISO timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("ambiguous timestamp: explicit timezone required")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class RequirementVersion:
    row_id: int
    modified_at_utc: str
    requested_kwh: float
    requested_departure_utc: str
    is_valid: bool
    session_pseudonym: str

    def __post_init__(self):
        integer(self.row_id, "row_id")
        _text(self.session_pseudonym, "session_pseudonym")
        number(self.requested_kwh, "requested_kwh")
        if self.requested_kwh <= 0 or type(self.is_valid) is not bool:
            raise ValueError("positive requested energy and boolean is_valid required")
        timestamp(self.modified_at_utc)
        timestamp(self.requested_departure_utc)


def observed_snapshot(driver_pseudonym, source_name, connection_at, decision_at,
                      versions, *, decision_policy, session_pseudonym):
    """Latest valid known version, ties by row_id. Caller owns pseudonymization.

    at_connection means decision exactly at connection; after_input allows a
    later declared decision time, but does not invent prior charging or remaining
    energy. A declared total session request is never silently remaining energy.
    """
    for field, value in (("driver_pseudonym", driver_pseudonym), ("source_name", source_name),
                         ("session_pseudonym", session_pseudonym)):
        _text(value, field)
    connection, decision = timestamp(connection_at), timestamp(decision_at)
    if decision_policy not in ("at_connection", "after_input"):
        raise ValueError("explicit at_connection or after_input decision policy required")
    if decision < connection or (decision_policy == "at_connection" and decision != connection):
        raise ValueError("decision time violates declared decision policy")
    versions = tuple(versions)
    if not all(isinstance(row, RequirementVersion) for row in versions):
        raise ValueError("only normalized RequirementVersion records accepted")
    if any(row.session_pseudonym != session_pseudonym for row in versions):
        raise ValueError("input versions belong to a different session")
    keys = [(timestamp(row.modified_at_utc), row.row_id) for row in versions]
    if len(set(keys)) != len(keys):
        raise ValueError("ambiguous duplicate version timestamp/row_id")
    eligible = [row for row in versions if row.is_valid
                and timestamp(row.modified_at_utc) <= decision]
    selected = max(eligible, key=lambda row: (timestamp(row.modified_at_utc), row.row_id)) if eligible else None
    known = {}
    if selected:
        known = {"requested_total_session_kwh": selected.requested_kwh,
                 "requested_departure_utc": timestamp(selected.requested_departure_utc).isoformat()}
    missing = ["site_residual_kw_forecast", "available_ports_forecast", "tariff_forecast",
               "charger_kw", "vehicle_max_kw", "max_start_delay", "charging_permission"]
    if not selected:
        missing += ["requested_total_session_kwh", "requested_departure_utc"]
    if decision > connection:
        missing += ["delivered_before_decision_kwh", "remaining_requested_kwh"]
    conflicts = ["declared_deadline_not_after_decision"] if selected and timestamp(selected.requested_departure_utc) <= decision else []
    return {"schema_version": 2, "evidence_class": "observed_driver_declaration_snapshot",
            "driver_pseudonym": driver_pseudonym, "source_name": source_name,
            "session_pseudonym": session_pseudonym,
            "connection_at_utc": connection.isoformat(), "decision_at_utc": decision.isoformat(),
            "decision_policy": decision_policy, "selected_row_id": selected.row_id if selected else None,
            "requirement_modified_at_utc": timestamp(selected.modified_at_utc).isoformat() if selected else None,
            "known_fields": known, "missing_fields": missing, "scheduling_ready": False,
            "conflicts": conflicts,
            "limitation": "No site integration or execution history; not a factual counterfactual replay."}
