# app/crud/tax_organizer.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tax_organizer import TaxOrganizer, TaxOrganizerTemplate
from app.schemas.tax_organizer import (
    TaxOrganizerTemplateCreate,
    TaxOrganizerTemplateUpdate,
    TaxOrganizerSendRequest,
)


# ── Template CRUD ─────────────────────────────────────────────────────────────

def create_template(
    db: Session,
    template_in: TaxOrganizerTemplateCreate,
    firm_id: UUID,
) -> TaxOrganizerTemplate:
    template = TaxOrganizerTemplate(**template_in.model_dump(), firm_id=firm_id)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(
    db: Session,
    template_id: UUID,
    firm_id: UUID,
) -> TaxOrganizerTemplate | None:
    return db.execute(
        select(TaxOrganizerTemplate).where(
            TaxOrganizerTemplate.id == template_id,
            TaxOrganizerTemplate.firm_id == firm_id,
        )
    ).scalars().first()


def list_templates(
    db: Session,
    firm_id: UUID,
) -> list[TaxOrganizerTemplate]:
    return db.execute(
        select(TaxOrganizerTemplate)
        .where(TaxOrganizerTemplate.firm_id == firm_id)
        .order_by(TaxOrganizerTemplate.is_default.desc(), TaxOrganizerTemplate.name)
    ).scalars().all()


def update_template(
    db: Session,
    template: TaxOrganizerTemplate,
    template_in: TaxOrganizerTemplateUpdate,
) -> TaxOrganizerTemplate:
    for key, value in template_in.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
    db.commit()
    db.refresh(template)
    return template


# ── Organizer CRUD ────────────────────────────────────────────────────────────

def create_organizer(
    db: Session,
    request: TaxOrganizerSendRequest,
    firm_id: UUID,
) -> TaxOrganizer:
    organizer = TaxOrganizer(
        firm_id=firm_id,
        client_id=request.client_id,
        engagement_id=request.engagement_id,
        template_id=request.template_id,
        tax_year=request.tax_year,
        client_message=request.client_message,
        status="sent",
        responses={},
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)
    return organizer


def get_organizer(
    db: Session,
    organizer_id: UUID,
    firm_id: UUID,
) -> TaxOrganizer | None:
    return db.execute(
        select(TaxOrganizer).where(
            TaxOrganizer.id == organizer_id,
            TaxOrganizer.firm_id == firm_id,
        )
    ).scalars().first()


def list_organizers(
    db: Session,
    firm_id: UUID,
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    status: Optional[str] = None,
) -> list[TaxOrganizer]:
    stmt = select(TaxOrganizer).where(TaxOrganizer.firm_id == firm_id)
    if client_id:
        stmt = stmt.where(TaxOrganizer.client_id == client_id)
    if engagement_id:
        stmt = stmt.where(TaxOrganizer.engagement_id == engagement_id)
    if status:
        stmt = stmt.where(TaxOrganizer.status == status)
    stmt = stmt.order_by(TaxOrganizer.created_at.desc())
    return db.execute(stmt).scalars().all()


def save_organizer_responses(
    db: Session,
    organizer: TaxOrganizer,
    responses: dict,
    submit: bool = False,
) -> TaxOrganizer:
    """
    Save client responses to an organizer.
    Merges new responses into existing ones (partial save supported).
    If submit=True, marks status as 'submitted' and records submitted_at.
    """
    # Merge responses — allows partial saves without wiping earlier answers
    merged = dict(organizer.responses or {})
    for section_id, answers in responses.items():
        if section_id not in merged:
            merged[section_id] = {}
        merged[section_id].update(answers)

    organizer.responses = merged

    if submit:
        organizer.status = "submitted"
        organizer.submitted_at = datetime.now(timezone.utc)
    elif organizer.status == "sent":
        # First save transitions from sent → in_progress
        organizer.status = "in_progress"

    db.commit()
    db.refresh(organizer)
    return organizer


def get_organizer_for_client(
    db: Session,
    organizer_id: UUID,
    client_id: UUID,
    firm_id: UUID,
) -> TaxOrganizer | None:
    """Portal-scoped lookup: client can only access their own organizers."""
    return db.execute(
        select(TaxOrganizer).where(
            TaxOrganizer.id == organizer_id,
            TaxOrganizer.client_id == client_id,
            TaxOrganizer.firm_id == firm_id,
        )
    ).scalars().first()


def list_organizers_for_client(
    db: Session,
    client_id: UUID,
    firm_id: UUID,
) -> list[TaxOrganizer]:
    """Portal-scoped list: returns all organizers for a specific client."""
    return db.execute(
        select(TaxOrganizer).where(
            TaxOrganizer.client_id == client_id,
            TaxOrganizer.firm_id == firm_id,
        ).order_by(TaxOrganizer.created_at.desc())
    ).scalars().all()
