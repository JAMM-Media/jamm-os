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
