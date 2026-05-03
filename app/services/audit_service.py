# app/services/audit_service.py

import sys
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def write_audit_log(
    db: Session,
    firm_id: uuid.UUID,
    action: str,
    actor_id: Optional[uuid.UUID] = None,
    actor_type: str = "system",
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """
    Append an immutable audit log record.

    Fire-and-forget safe: never raises. Errors are logged to stderr only
    so the caller is never disrupted by audit failures.
    """
    try:
        entry = AuditLog(
            firm_id=firm_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_metadata=metadata,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        print(f"[audit_service] Failed to write audit log: {exc}", file=sys.stderr)
        db.rollback()
