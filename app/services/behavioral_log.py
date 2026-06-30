# app/services/behavioral_log.py

import logging
import uuid
from typing import Optional

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
