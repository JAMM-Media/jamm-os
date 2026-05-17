# app/services/behavioral_log.py

import logging
import uuid
from typing import Optional

from app.db.session import SessionLocal
from app.models.behavioral_event import BehavioralEvent

log = logging.getLogger(__name__)


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
) -> None:
    db = None
    try:
        db = SessionLocal()

        # Honour the firm's index consent choice.
        # Firms that opted out produce zero behavioral event rows.
        from app.models.firm import Firm
        firm = db.get(Firm, firm_id)
        if firm is None or not firm.index_consent:
            return

        event = BehavioralEvent(
            firm_id=firm_id,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            extra_metadata=metadata,
            session_id=session_id,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        log.warning("behavioral_log.log_event failed: %s", exc)
    finally:
        if db is not None:
            db.close()
