# app/api/tax_organizers.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import tax_organizer as crud_organizer
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.user import User
from app.schemas.tax_organizer import (
    TaxOrganizerOut,
    TaxOrganizerSendRequest,
    TaxOrganizerTemplateCreate,
    TaxOrganizerTemplateOut,
    TaxOrganizerTemplateUpdate,
    TaxOrganizerWithTemplate,
)
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.event_bus import emit_event
from app.core.enums import TriggerEvent

router = APIRouter(prefix="/tax-organizers", tags=["Tax Organizers"])


# ── Templates ─────────────────────────────────────────────────────────────────

@router.get("/templates", response_model=list[TaxOrganizerTemplateOut])
def list_templates(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    """List all organizer templates for this firm. Seeded defaults appear first."""
    return crud_organizer.list_templates(db=db, firm_id=current_firm.id)


@router.post(
    "/templates",
    response_model=TaxOrganizerTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
def create_template(
    payload: TaxOrganizerTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """Create a custom organizer template. Manager and firm_owner only."""
    return crud_organizer.create_template(db=db, template_in=payload, firm_id=current_firm.id)


@router.patch("/templates/{template_id}", response_model=TaxOrganizerTemplateOut)
def update_template(
    template_id: UUID,
    payload: TaxOrganizerTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    template = crud_organizer.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return crud_organizer.update_template(db, template, payload)


# ── Organizers ────────────────────────────────────────────────────────────────

@router.post("/send", response_model=TaxOrganizerOut, status_code=status.HTTP_201_CREATED)
async def send_organizer(
    payload: TaxOrganizerSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Send a tax organizer to a client for their engagement.
    Creates the organizer record (status: sent) and makes it
    available in the client portal immediately.
    Manager and firm_owner only.
    """
    # Verify client belongs to this firm
    client = db.execute(
        select(Client).where(
            Client.id == payload.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Verify engagement belongs to this firm
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Verify engagement belongs to this client
    if engagement.client_id != payload.client_id:
        raise HTTPException(
            status_code=400,
            detail="Engagement does not belong to the specified client",
        )

    # Verify template belongs to this firm
    template = crud_organizer.get_template(db, payload.template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    organizer = crud_organizer.create_organizer(
        db=db,
        request=payload,
        firm_id=current_firm.id,
    )

    log_event(
        firm_id=current_firm.id,
        event_type="tax_organizer.sent",
        entity_type="tax_organizer",
        entity_id=organizer.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "client_id": str(payload.client_id),
            "engagement_id": str(payload.engagement_id),
            "template_id": str(payload.template_id),
            "tax_year": organizer.tax_year,
        }
    )

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        action="tax_organizer.sent",
        entity_type="tax_organizer",
        entity_id=organizer.id,
    )

    await emit_event(
        event=TriggerEvent.doc_request_created,  # reuse closest event
        payload={
            "firm_id": str(current_firm.id),
            "engagement_id": str(engagement.id),
            "client_id": str(client.id),
            "organizer_id": str(organizer.id),
            "tax_year": organizer.tax_year,
        },
        background_tasks=background_tasks,
    )

    return organizer


@router.get("/", response_model=list[TaxOrganizerOut])
def list_organizers(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    status: Optional[str] = None,
):
    return crud_organizer.list_organizers(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
    )


@router.get("/{organizer_id}", response_model=TaxOrganizerWithTemplate)
def get_organizer(
    organizer_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    """
    Get a single organizer with its template included.
    Staff use this to review client responses.
    """
    organizer = crud_organizer.get_organizer(db, organizer_id, current_firm.id)
    if not organizer:
        raise HTTPException(status_code=404, detail="Tax organizer not found")
    return organizer
