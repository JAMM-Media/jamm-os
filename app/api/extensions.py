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
import app.services.extension_service as extension_service

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

    The extended_deadline on the Engagement is what the deadline scheduler
    and all deadline watch queries use from this point forward.

    Manager and firm_owner only. firm_id injected from JWT.
    Business logic (Extension row, engagement sync, audit log, automation
    event, engagement.extension_filed) lives in extension_service.file_extension.
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

    return await extension_service.file_extension(
        db=db,
        payload=payload,
        engagement=engagement,
        firm_id=current_firm.id,
        actor_id=current_user.id,
        background_tasks=background_tasks,
    )


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

    return extension_service.update_extension(
        db=db, ext=ext, payload=payload, firm_id=current_firm.id,
    )
