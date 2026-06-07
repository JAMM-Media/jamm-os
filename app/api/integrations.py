# app/api/integrations.py

import threading
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.schemas.integration import IntegrationOut, QuickBooksConnectResponse
from app.crud import integration as crud_integration
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner, require_manager_or_above
from app.services.quickbooks_service import QuickBooksService
from app.services.gmail_service import GmailService
from app.services.outlook_service import OutlookService
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event

router = APIRouter(prefix="/integrations", tags=["integrations"])

_qb_service = QuickBooksService()
_gmail_service = GmailService()
_outlook_service = OutlookService()


# -------------------------------------------------------------------
# GET /integrations/quickbooks/connect — Start QB OAuth2 flow
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.get("/quickbooks/connect", response_model=QuickBooksConnectResponse)
def quickbooks_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    # Get-or-create the integration record
    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="quickbooks"
    )
    if not integration:
        crud_integration.create_integration(db, firm_id=current_firm.id, provider="quickbooks")

    authorization_url = _qb_service.get_authorization_url(current_firm.id)
    return QuickBooksConnectResponse(authorization_url=authorization_url)


# -------------------------------------------------------------------
# GET /integrations/quickbooks/callback — Intuit redirects here after auth
# No JWT required — Intuit calls this endpoint directly.
# -------------------------------------------------------------------
@router.get("/quickbooks/callback")
def quickbooks_callback(
    code: str = Query(...),
    realmId: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        integration = _qb_service.handle_callback(code=code, realm_id=realmId, state=state, db=db)
        try:
            firm_id = _uuid.UUID(state)
            write_audit_log(
                db=db,
                firm_id=firm_id,
                action="integration.connected",
                actor_type="system",
                entity_type="integration",
                entity_id=integration.id,
                metadata={"provider": "quickbooks"},
            )
        except Exception:
            pass
        return {"status": "connected", "message": "QuickBooks connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------
# POST /integrations/quickbooks/sync/clients — Bi-directional client sync
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.post("/quickbooks/sync/clients")
def quickbooks_sync_clients(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="quickbooks"
    )
    if not integration or integration.status != "connected":
        raise HTTPException(status_code=400, detail="QuickBooks not connected")

    result = _qb_service.sync_clients(integration, db, firm_id=current_firm.id)
    return result


# -------------------------------------------------------------------
# GET /integrations/quickbooks/import-preview
# Returns QB customers not yet imported as JAMM PX clients.
# Used by onboarding import wizard step 2 (QB path).
# -------------------------------------------------------------------
@router.get("/quickbooks/import-preview")
def quickbooks_import_preview(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="quickbooks"
    )
    if not integration or integration.status != "connected":
        raise HTTPException(status_code=400, detail="QuickBooks not connected")

    try:
        preview = _qb_service.get_import_preview(
            integration=integration,
            db=db,
            firm_id=current_firm.id,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Could not fetch QuickBooks customers: {str(e)}",
        )

    return {"customers": preview, "total": len(preview)}


# -------------------------------------------------------------------
# POST /integrations/quickbooks/import-clients
# Imports a selected subset of QB customers as JAMM PX clients.
# Used by onboarding import wizard step 3 (QB path confirm).
# -------------------------------------------------------------------
class QBImportRequest(BaseModel):
    quickbooks_customer_ids: list[str]


@router.post("/quickbooks/import-clients")
def quickbooks_import_selected_clients(
    payload: QBImportRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    if not payload.quickbooks_customer_ids:
        raise HTTPException(
            status_code=400,
            detail="No customer IDs provided.",
        )
    if len(payload.quickbooks_customer_ids) > 500:
        raise HTTPException(
            status_code=400,
            detail="Maximum 500 customers per import.",
        )

    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="quickbooks"
    )
    if not integration or integration.status != "connected":
        raise HTTPException(status_code=400, detail="QuickBooks not connected")

    try:
        result = _qb_service.import_selected_clients(
            integration=integration,
            db=db,
            firm_id=current_firm.id,
            quickbooks_customer_ids=payload.quickbooks_customer_ids,
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Import failed: {str(e)}",
        )

    return result


# -------------------------------------------------------------------
# GET /integrations/quickbooks/deep-link/client/{client_id}
# Returns the QBO customer detail URL for the given client.
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.get("/quickbooks/deep-link/client/{client_id}")
def quickbooks_client_deep_link(
    client_id: _uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found.")

    if client.quickbooks_customer_id is None:
        raise HTTPException(
            status_code=404,
            detail="This client is not linked to a QuickBooks customer.",
        )

    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="quickbooks"
    )
    if not integration or integration.status != "connected":
        raise HTTPException(status_code=400, detail="QuickBooks is not connected.")

    qb_customer_id = client.quickbooks_customer_id
    deep_link_url = f"https://app.qbo.intuit.com/app/customerdetail?nameId={qb_customer_id}"

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "integration.qbo_deep_link_opened",
            "firm_id": current_firm.id,
            "entity_type": "client",
            "entity_id": client_id,
            "metadata": {"quickbooks_customer_id": qb_customer_id},
        },
        daemon=True,
    ).start()

    return {"url": deep_link_url, "quickbooks_customer_id": qb_customer_id}


# -------------------------------------------------------------------
# GET /integrations/gmail/connect — Start Gmail OAuth2 flow
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.get("/gmail/connect")
def gmail_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider="gmail"
    )
    if not integration:
        crud_integration.create_user_integration(db, firm_id=current_firm.id, user_id=current_user.id, provider="gmail")

    authorization_url = _gmail_service.get_authorization_url(current_firm.id, current_user.id)
    return {"authorization_url": authorization_url}


# -------------------------------------------------------------------
# GET /integrations/gmail/callback — Google redirects here after auth
# No JWT required — Google calls this endpoint directly.
# -------------------------------------------------------------------
@router.get("/gmail/callback")
def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        _gmail_service.handle_callback(code=code, state=state, db=db)
        return {"status": "connected", "message": "Gmail connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------
# GET /integrations/outlook/connect — Start Outlook OAuth2 flow
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.get("/outlook/connect")
def outlook_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_firm_owner),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider="outlook"
    )
    if not integration:
        crud_integration.create_user_integration(db, firm_id=current_firm.id, user_id=current_user.id, provider="outlook")

    authorization_url = _outlook_service.get_authorization_url(current_firm.id, current_user.id)
    return {"authorization_url": authorization_url}


# -------------------------------------------------------------------
# GET /integrations/outlook/callback — Microsoft redirects here after auth
# No JWT required — Microsoft calls this endpoint directly.
# -------------------------------------------------------------------
@router.get("/outlook/callback")
def outlook_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    try:
        _outlook_service.handle_callback(code=code, state=state, db=db)
        return {"status": "connected", "message": "Outlook connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------
# GET /integrations/staff/gmail/connect — Staff: start Gmail OAuth2 flow
# -------------------------------------------------------------------
@router.get("/staff/gmail/connect")
def staff_gmail_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider="gmail"
    )
    if not integration:
        crud_integration.create_user_integration(
            db, firm_id=current_firm.id, user_id=current_user.id, provider="gmail"
        )
    authorization_url = _gmail_service.get_authorization_url(current_firm.id, current_user.id)
    return {"authorization_url": authorization_url}


# -------------------------------------------------------------------
# GET /integrations/staff/gmail/callback — Google redirects here after staff auth
# No JWT required — Google calls this endpoint directly.
# -------------------------------------------------------------------
@router.get("/staff/gmail/callback")
def staff_gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    try:
        _gmail_service.handle_callback(code=code, state=state, db=db)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/my-integrations?connected=gmail")
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/my-integrations?error=gmail_failed")


# -------------------------------------------------------------------
# GET /integrations/staff/outlook/connect — Staff: start Outlook OAuth2 flow
# -------------------------------------------------------------------
@router.get("/staff/outlook/connect")
def staff_outlook_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider="outlook"
    )
    if not integration:
        crud_integration.create_user_integration(
            db, firm_id=current_firm.id, user_id=current_user.id, provider="outlook"
        )
    authorization_url = _outlook_service.get_authorization_url(current_firm.id, current_user.id)
    return {"authorization_url": authorization_url}


# -------------------------------------------------------------------
# GET /integrations/staff/outlook/callback — Microsoft redirects here after staff auth
# No JWT required — Microsoft calls this endpoint directly.
# -------------------------------------------------------------------
@router.get("/staff/outlook/callback")
def staff_outlook_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    try:
        _outlook_service.handle_callback(code=code, state=state, db=db)
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/my-integrations?connected=outlook")
    except Exception:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/settings/my-integrations?error=outlook_failed")


# -------------------------------------------------------------------
# GET /integrations/staff/me — Return current user's integrations
# -------------------------------------------------------------------
@router.get("/staff/me", response_model=list[IntegrationOut])
def staff_list_my_integrations(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    return crud_integration.get_integrations_for_user(
        db, firm_id=current_firm.id, user_id=current_user.id
    )


# -------------------------------------------------------------------
# DELETE /integrations/staff/{provider} — Disconnect current user's integration
# -------------------------------------------------------------------
@router.delete("/staff/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def staff_disconnect_integration(
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider=provider
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.encrypted_access_token = None
    integration.encrypted_refresh_token = None
    integration.token_expires_at = None
    integration.connected_at = None
    integration.scopes = None
    integration.external_account_id = None
    crud_integration.update_integration_status(db, integration, status="disconnected")
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="integration.disconnected",
        actor_type="staff",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider, "user_id": str(current_user.id)},
    )


# -------------------------------------------------------------------
# POST /integrations/staff/{provider}/disable — Staff: opt out of inbox sync
# -------------------------------------------------------------------
@router.post("/staff/{provider}/disable", status_code=status.HTTP_200_OK)
def staff_disable_integration(
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider=provider
    )
    if not integration:
        crud_integration.create_user_integration(
            db, firm_id=current_firm.id, user_id=current_user.id, provider=provider
        )
        integration = crud_integration.get_user_integration(
            db, firm_id=current_firm.id, user_id=current_user.id, provider=provider
        )
    crud_integration.update_integration_status(db, integration, status="opted_out")
    return {"status": "opted_out"}


# -------------------------------------------------------------------
# POST /integrations/staff/{provider}/enable — Staff: opt back into inbox sync
# -------------------------------------------------------------------
@router.post("/staff/{provider}/enable", status_code=status.HTTP_200_OK)
def staff_enable_integration(
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=current_user.id, provider=provider
    )
    if not integration:
        raise HTTPException(
            status_code=400,
            detail="No integration connected. Connect first.",
        )
    if integration.status != "opted_out":
        return {"status": integration.status}
    crud_integration.update_integration_status(db, integration, status="connected")
    return {"status": "connected"}


# -------------------------------------------------------------------
# POST /integrations/firm/{user_id}/{provider}/disable — Firm owner disables a staff member's integration
# -------------------------------------------------------------------
@router.post("/firm/{user_id}/{provider}/disable", response_model=IntegrationOut)
def firm_disable_staff_integration(
    user_id: _uuid.UUID,
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=user_id, provider=provider
    )
    if not integration:
        raise HTTPException(status_code=404, detail="No integration found for this staff member.")
    result = crud_integration.firm_disable_user_integration(db, integration)
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="integration.firm_disabled",
        actor_type="firm_owner",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider, "target_user_id": str(user_id)},
    )
    return result


# -------------------------------------------------------------------
# POST /integrations/firm/{user_id}/{provider}/enable — Firm owner re-enables a staff member's integration
# -------------------------------------------------------------------
@router.post("/firm/{user_id}/{provider}/enable", response_model=IntegrationOut)
def firm_enable_staff_integration(
    user_id: _uuid.UUID,
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_user_integration(
        db, firm_id=current_firm.id, user_id=user_id, provider=provider
    )
    if not integration:
        raise HTTPException(status_code=404, detail="No integration found for this staff member.")
    result = crud_integration.firm_enable_user_integration(db, integration)
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="integration.firm_enabled",
        actor_type="firm_owner",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider, "target_user_id": str(user_id)},
    )
    return result


# -------------------------------------------------------------------
# GET /integrations/firm/staff — List all per-staff integrations for this firm
# -------------------------------------------------------------------
@router.get("/firm/staff", response_model=list[IntegrationOut])
def firm_list_staff_integrations(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    return db.execute(
        select(Integration).where(
            Integration.firm_id == current_firm.id,
            Integration.user_id != None,
        )
    ).scalars().all()


# -------------------------------------------------------------------
# GET /integrations/ — List all integrations for this firm
# -------------------------------------------------------------------
@router.get("/", response_model=list[IntegrationOut])
def list_integrations(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    return crud_integration.get_integrations_for_firm(db, firm_id=current_firm.id)


# -------------------------------------------------------------------
# GET /integrations/{provider} — Get a single integration by provider
# -------------------------------------------------------------------
@router.get("/{provider}", response_model=IntegrationOut)
def get_integration(
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_integration(db, firm_id=current_firm.id, provider=provider)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


# -------------------------------------------------------------------
# DELETE /integrations/{provider} — Disconnect an integration
# Wipes tokens and sets status to disconnected.
# -------------------------------------------------------------------
@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_integration(
    provider: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_integration(db, firm_id=current_firm.id, provider=provider)
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.encrypted_access_token = None
    integration.encrypted_refresh_token = None
    integration.token_expires_at = None
    integration.connected_at = None
    integration.scopes = None
    integration.external_account_id = None
    crud_integration.update_integration_status(db, integration, status="disconnected")
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="integration.disconnected",
        actor_type="staff",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider},
    )
