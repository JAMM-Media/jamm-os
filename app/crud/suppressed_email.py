# app/crud/suppressed_email.py

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.suppressed_email import SuppressedEmail


def is_suppressed(db: Session, firm_id: UUID, email: str) -> bool:
    """Return True if this email is on the suppression list for this firm.

    Normalizes to lowercase before comparing -- the CRUD layer owns normalization,
    not the DB or the caller.
    """
    normalized = email.lower().strip()
    return (
        db.query(SuppressedEmail)
        .filter(
            SuppressedEmail.firm_id == firm_id,
            SuppressedEmail.email == normalized,
        )
        .limit(1)
        .count()
        > 0
    )


def add_suppression(
    db: Session,
    firm_id: UUID,
    email: str,
    reason: str | None = None,
) -> SuppressedEmail:
    """Add an email to the firm's suppression list.

    Upsert-safe: if the (firm_id, email) pair already exists, the existing row
    is returned without error. This handles double-clicks on unsubscribe links
    or multiple enrollments for the same email without raising IntegrityError.
    """
    normalized = email.lower().strip()

    existing = (
        db.query(SuppressedEmail)
        .filter(
            SuppressedEmail.firm_id == firm_id,
            SuppressedEmail.email == normalized,
        )
        .first()
    )
    if existing:
        return existing

    row = SuppressedEmail(
        firm_id=firm_id,
        email=normalized,
        reason=reason,
        suppressed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        # Race condition: another request inserted the same row between our
        # SELECT and our INSERT. Re-fetch the winner.
        existing = (
            db.query(SuppressedEmail)
            .filter(
                SuppressedEmail.firm_id == firm_id,
                SuppressedEmail.email == normalized,
            )
            .first()
        )
        return existing
    return row
