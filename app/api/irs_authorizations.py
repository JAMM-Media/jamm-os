# app/api/irs_authorizations.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import irs_authorization as crud_auth
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.schemas.irs_authorization import (
    IrsAuthorizationOut,
    IrsAuthorizationSendRequest,
    IrsAuthorizationUpdate,
)
from app.services.irs_auth_service import send_irs_authorization, check_expiring_authorizations
from app.services.event_bus import emit_event
from app.core.enums import TriggerEvent

router = APIRouter(prefix="/irs-authorizations", tags=["IRS Authorizations"])


@router.get("/", response_model=list[IrsAuthorizationOut])
def list_irs_authorizations(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
    client_id: Optional[UUID] = None,
    form_type: Optional[str] = None,
    status: Optional[str] = None,
):
    return crud_auth.list_irs_authorizations(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
        form_type=form_type,
        status=status,
    )


@router.post("/send", response_model=IrsAuthorizationOut, status_code=status.HTTP_201_CREATED)
async def send_authorization(
    request: IrsAuthorizationSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Create and send an IRS authorization form (8821 or 2848) for a client.
    Manager and firm_owner only. firm_id injected from JWT.
    """
    client = db.execute(
        select(Client).where(
            Client.id == request.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    result = send_irs_authorization(
        db=db,
        request=request,
        firm=current_firm,
        client=client,
        sent_by_user_id=current_user.id,
    )

    authorization = result["authorization"]

    from app.services.audit_service import write_audit_log
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action='irs_auth.sent',
        actor_id=current_user.id,
        actor_type='staff',
        entity_type='irs_authorization',
        entity_id=authorization.id,
    )

    await emit_event(
        event=TriggerEvent.irs_authorization_signed,
        payload={
            "firm_id": str(current_firm.id),
            "client_id": str(client.id),
            "authorization_id": str(authorization.id),
            "form_type": request.form_type,
        },
        background_tasks=background_tasks,
    )

    return authorization


@router.get("/check/{client_id}", response_model=dict)
def check_client_authorization_status(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Quick check: does this client have active 8821 and/or 2848 on file?
    Returns has_active_8821 and has_active_2848 booleans plus the records.
    Used by the frontend IRS auth status card on Client detail.
    """
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    auth_8821 = crud_auth.get_active_authorization_for_client(
        db, current_firm.id, client_id, "8821"
    )
    auth_2848 = crud_auth.get_active_authorization_for_client(
        db, current_firm.id, client_id, "2848"
    )

    return {
        "client_id": str(client_id),
        "8821": IrsAuthorizationOut.model_validate(auth_8821).model_dump() if auth_8821 else None,
        "2848": IrsAuthorizationOut.model_validate(auth_2848).model_dump() if auth_2848 else None,
        "has_active_8821": auth_8821 is not None,
        "has_active_2848": auth_2848 is not None,
    }


@router.get("/{auth_id}", response_model=IrsAuthorizationOut)
def get_irs_authorization(
    auth_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    auth = crud_auth.get_irs_authorization(db, auth_id, current_firm.id)
    if not auth:
        raise HTTPException(status_code=404, detail="IRS authorization not found")
    return auth


@router.patch("/{auth_id}", response_model=IrsAuthorizationOut)
def update_irs_authorization(
    auth_id: UUID,
    payload: IrsAuthorizationUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Update an IRS authorization record.
    Used by the webhook handler to mark as active.
    """
    auth = crud_auth.get_irs_authorization(db, auth_id, current_firm.id)
    if not auth:
        raise HTTPException(status_code=404, detail="IRS authorization not found")
    return crud_auth.update_irs_authorization(db, auth, payload)


@router.post("/run-expiry-check", status_code=200)
def run_expiry_check(
    background_tasks: BackgroundTasks,
    _: User = Depends(require_manager_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """Manually trigger the IRS authorization expiry check. Runs as background task."""
    background_tasks.add_task(check_expiring_authorizations)
    return {"message": "IRS authorization expiry check queued"}
