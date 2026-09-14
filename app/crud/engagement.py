# app/crud/engagement.py

from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import select
from uuid import UUID

from app.models.engagement import Engagement
from app.schemas.engagement import EngagementCreate, EngagementUpdate
from app.core.tax_deadlines import get_filing_deadline


def get_engagement_for_firm(db: Session, engagement_id: UUID, firm_id: UUID) -> Engagement | None:
    stmt = select(Engagement).where(
        Engagement.id == engagement_id,
        Engagement.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def create_engagement(db: Session, engagement_in: EngagementCreate, firm_id: UUID) -> Engagement:
    data = engagement_in.model_dump()

    # Auto-set filing_deadline from engagement_type if not explicitly provided
    if data.get("engagement_type") and not data.get("filing_deadline"):
        deadline_tuple = get_filing_deadline(data["engagement_type"])
        if deadline_tuple:
            # Use the current calendar year for the deadline
            # Firms can override via PATCH if needed for a different tax year
            today = date.today()
            month, day = deadline_tuple
            try:
                data["filing_deadline"] = date(today.year, month, day)
            except ValueError:
                # Safety net for invalid dates (shouldn't occur with our fixed deadlines)
                data["filing_deadline"] = None

    engagement = Engagement(**data, firm_id=firm_id)
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    # Create the "Provided by Client (PBC)" starter folder required by filesystem
    # spec Section 5. Wrapped in try/except so a folder-creation failure never
    # rolls back or prevents the engagement itself from being returned. An
    # engagement without a PBC folder is a recoverable state: the approval
    # fallback in document_service.py already handles it gracefully.
    try:
        from app.services.document_folder_service import create_folder
        create_folder(
            db=db,
            firm_id=firm_id,
            scope="engagement",
            name="Provided by Client (PBC)",
            client_id=engagement.client_id,
            engagement_id=engagement.id,
        )
    except Exception as _exc:
        import logging as _log
        _log.getLogger(__name__).warning(
            "PBC folder creation failed for engagement %s: %s -- engagement creation succeeds",
            engagement.id,
            _exc,
        )
    return engagement


def update_engagement(db: Session, engagement: Engagement, engagement_in: EngagementUpdate) -> Engagement:
    for key, value in engagement_in.model_dump(exclude_unset=True).items():
        setattr(engagement, key, value)
    db.commit()
    db.refresh(engagement)
    return engagement


def delete_engagement(db: Session, engagement: Engagement):
    db.delete(engagement)
    db.commit()