# app/services/unsubscribe_service.py

import hashlib
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.enums import EnrollmentStatus
from app.crud.suppressed_email import add_suppression
from app.models.enrollment import Enrollment
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)


def verify_and_process_unsubscribe(db: Session, raw_token: str) -> bool:
    """Verify an unsubscribe token and process the unsubscribe if valid.

    Follows the exact hash/verify/clear pattern from portal_magic_link.py:
    - Only the SHA-256 hash is stored; the raw token lives transiently in the
      email link and is hashed on arrival before any DB lookup.
    - Token is single-use: hash is cleared after a successful unsubscribe.

    Returns True on success, False if token is not found or expired.
    Callers should show a plain 'link no longer valid' state on False, not crash.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    enrollment = (
        db.query(Enrollment)
        .filter(
            Enrollment.unsubscribe_token_hash == token_hash,
            Enrollment.unsubscribe_token_expires_at > datetime.now(timezone.utc),
        )
        .first()
    )

    if enrollment is None:
        logger.info("unsubscribe: token not found or expired")
        return False

    lead = enrollment.lead
    if lead is None or not lead.email:
        logger.warning(
            "unsubscribe: enrollment %s has no lead or lead has no email, aborting",
            enrollment.id,
        )
        return False

    # Add to suppression list before mutating enrollment status, so that a
    # partial failure (crash after add_suppression but before commit) can be
    # retried safely -- add_suppression is idempotent.
    add_suppression(
        db=db,
        firm_id=enrollment.firm_id,
        email=lead.email,
        reason="unsubscribed",
    )

    enrollment.status = EnrollmentStatus.unsubscribed.value
    enrollment.stopped_at = datetime.now(timezone.utc)
    # Clear token -- single-use, matching the magic-link precedent.
    enrollment.unsubscribe_token_hash = None
    enrollment.unsubscribe_token_expires_at = None

    db.commit()

    # NOTE: "lead.unsubscribed" is a task-introduced event name consistent with
    # the contract's Section 9.1 naming convention but not verbatim in that list.
    # This name should be reviewed before deploy.
    log_event(
        event_type="lead.unsubscribed",
        firm_id=enrollment.firm_id,
        entity_type="lead",
        entity_id=lead.id,
        actor_type="lead",
        metadata={
            "enrollment_id": str(enrollment.id),
            "sequence_id": str(enrollment.sequence_id),
            "email": lead.email,
        },
    )

    logger.info(
        "unsubscribe: processed enrollment=%s lead=%s email=%s",
        enrollment.id, lead.id, lead.email,
    )
    return True
