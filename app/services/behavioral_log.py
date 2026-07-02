# app/services/behavioral_log.py

import logging
import threading
import uuid
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from app.db.session import SessionLocal
from app.models.behavioral_event import BehavioralEvent

log = logging.getLogger(__name__)


def _coerce_uuid(value) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def log_event(
    *,
    event_type: str,
    firm_id: uuid.UUID,
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    actor_type: Optional[str] = None,
    actor_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict] = None,
    session_id: Optional[uuid.UUID] = None,
    request_id: Optional[uuid.UUID] = None,
) -> None:
    from app.core.request_context import get_request_id, get_session_id

    if session_id is None:
        session_id = get_session_id()
    if request_id is None:
        request_id = get_request_id()

    session_id = _coerce_uuid(session_id)
    request_id = _coerce_uuid(request_id)

    def _write(
        event_type=event_type,
        firm_id=firm_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata=metadata,
        session_id=session_id,
        request_id=request_id,
    ) -> None:
        db = None
        try:
            db = SessionLocal()

            event = BehavioralEvent(
                firm_id=firm_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                actor_id=actor_id,
                extra_metadata=metadata,
                session_id=session_id,
                request_id=request_id,
            )
            db.add(event)
            db.commit()
        except Exception as exc:
            log.warning("behavioral_log.log_event failed: %s", exc)
        finally:
            if db is not None:
                db.close()

    threading.Thread(target=_write, daemon=True).start()


def log_setting_changes(
    *,
    firm_id,
    actor_id,
    old_values: dict,
    new_values: dict,
) -> None:
    """
    Fire one firm.setting_changed event per key whose value changed.
    Simple scalars are captured directly; complex values (dict/list)
    are recorded as changed-with-type only, never dumped in full.
    """
    def _safe(v):
        if v is None or isinstance(v, (str, int, float, bool)):
            return v
        return {"_type": type(v).__name__, "_changed": True}

    for key in set(old_values) | set(new_values):
        old_v = old_values.get(key)
        new_v = new_values.get(key)
        if old_v == new_v:
            continue
        log_event(
            firm_id=firm_id,
            event_type="firm.setting_changed",
            entity_type="firm",
            entity_id=firm_id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "setting_key": str(key),
                "from_value": _safe(old_v),
                "to_value": _safe(new_v),
            },
        )


# Field name substrings that trigger redaction under the IRS Publication 4557
# no-silent-changes rule: the event records THAT the field changed, never the
# values themselves.
SENSITIVE_FIELD_MARKERS = ("ssn", "ein", "tax_id", "bank", "routing", "account_number")


def _is_sensitive_field(field_name: str) -> bool:
    lowered = field_name.lower()
    return any(marker in lowered for marker in SENSITIVE_FIELD_MARKERS)


def _serialize_for_jsonb(value):
    """Recursively cast UUIDs, enums, dates, and Decimals to strings so JSONB accepts them."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (uuid.UUID, Decimal, date, datetime)):
        return str(value)
    if isinstance(value, Enum):
        return value.value if hasattr(value, "value") else str(value)
    if isinstance(value, dict):
        return {k: _serialize_for_jsonb(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_for_jsonb(v) for v in value]
    return str(value)


def build_changed_fields(old_values: dict, new_values: dict) -> dict:
    """
    Builds the {field_name: {"from": ..., "to": ...}} delta for the
    no-silent-changes generic *.updated events.

    old_values / new_values must share the same keys (the set of fields the
    update payload actually touched). Fields whose value did not change are
    omitted. Sensitive-named fields (ssn, ein, tax_id, bank, routing,
    account_number) are recorded as changed but with both values redacted.
    """
    changed = {}
    for field_name, old_v in old_values.items():
        new_v = new_values.get(field_name)
        if old_v == new_v:
            continue
        if _is_sensitive_field(field_name):
            changed[field_name] = {"from": "redacted", "to": "redacted"}
        else:
            changed[field_name] = {
                "from": _serialize_for_jsonb(old_v),
                "to": _serialize_for_jsonb(new_v),
            }
    return changed
