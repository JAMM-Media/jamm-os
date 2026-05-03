# app/api/extensions.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import extension as crud_extension
from app.crud import engagement as crud_engagement
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.user import User
from app.schemas.extension import ExtensionCreate, ExtensionOut, ExtensionUpdate
from app.schemas.engagement import EngagementUpdate
from app.services.audit_service import write_audit_log
from app.services.event_bus import emit_event
from app.core.enums import TriggerEvent

router = APIRouter(prefix="/extensions", tags=["Extensions"])


# ─── FILE EXTENSION ───────────────────────────────────────────────────────────

@router.post("/file", response_model=ExtensionOut, status_code=status.HTTP_201_CREATED)
async def file_extension(
    payload: ExtensionCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """
    File an IRS extension for an engagement.

    On success:
    1. Creates the Extension record
    2. Updates Engagement.extended_deadline with the new deadline
    3. Emits extension.filed event to the automation engine
    4. Writes an audit log entry

    The extended_deadline on the Engagement is what the deadline scheduler
    and all deadline watch queries use from this point forward.

    Manager and firm_owner only. firm_id injected from JWT.
    """
    # Verify engagement belongs to this firm
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Verify client belongs to this firm (client_id must match engagement)
    if engagement.client_id != payload.client_id:
        raise HTTPException(
            status_code=400,
            detail="client_id does not match the engagement's client",
        )

    # Create the Extension record (auto-populates filed_at and extended_deadline)
    extension = crud_extension.create_extension(
        db=db,
        ext_in=payload,
        firm_id=current_firm.id,
    )

    # Update Engagement.extended_deadline — this is the critical write.
    # The deadline scheduler checks extended_deadline first, so this
    # immediately changes what deadline the system tracks for this engagement.
    for key, value in {"extended_deadline": extension.extended_deadline}.items():
        setattr(engagement, key, value)
    db.commit()
    db.refresh(engagement)

    # Audit log
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        action="extension.filed",
        entity_type="extension",
        entity_id=extension.id,
    )

    # Emit event for automation engine
    await emit_event(
        event=TriggerEvent.extension_filed,
        payload={
            "firm_id": str(current_firm.id),
            "engagement_id": str(engagement.id),
            "client_id": str(engagement.client_id),
            "extension_id": str(extension.id),
            "form_type": extension.form_type,
            "extended_deadline": extension.extended_deadline.isoformat(),
        },
        background_tasks=background_tasks,
    )

    return extension


# ─── LIST ────────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[ExtensionOut])
def list_extensions(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
    engagement_id: Optional[UUID] = None,
    client_id: Optional[UUID] = None,
    status: Optional[str] = None,
):
    """
    List extensions for this firm.
    Filter by engagement_id, client_id, or status.
    All staff can view. Only managers and firm_owner can create.
    """
    return crud_extension.list_extensions(
        db=db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        client_id=client_id,
        status=status,
    )


# ─── GET SINGLE ──────────────────────────────────────────────────────────────

@router.get("/{ext_id}", response_model=ExtensionOut)
def get_extension(
    ext_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    ext = crud_extension.get_extension(db, ext_id, current_firm.id)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")
    return ext


# ─── UPDATE ──────────────────────────────────────────────────────────────────

@router.patch("/{ext_id}", response_model=ExtensionOut)
def update_extension(
    ext_id: UUID,
    payload: ExtensionUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Update an extension record. Manager and firm_owner only.
    If extended_deadline is updated, also updates Engagement.extended_deadline.
    """
    ext = crud_extension.get_extension(db, ext_id, current_firm.id)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")

    updated = crud_extension.update_extension(db, ext, payload)

    # If the deadline was updated, sync it to the engagement
    if payload.extended_deadline is not None:
        engagement = db.execute(
            select(Engagement).where(
                Engagement.id == ext.engagement_id,
                Engagement.firm_id == current_firm.id,
            )
        ).scalars().first()
        if engagement:
            engagement.extended_deadline = payload.extended_deadline
            db.commit()

    return updated
