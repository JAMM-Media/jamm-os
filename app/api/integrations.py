# app/api/integrations.py

import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.integration import IntegrationOut, QuickBooksConnectResponse
from app.crud import integration as crud_integration
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner
from app.services.quickbooks_service import QuickBooksService
from app.services.gmail_service import GmailService
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/integrations", tags=["integrations"])

_qb_service = QuickBooksService()
_gmail_service = GmailService()


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
# GET /integrations/gmail/connect — Start Gmail OAuth2 flow
# Must be defined BEFORE /{provider} to avoid route shadowing.
# -------------------------------------------------------------------
@router.get("/gmail/connect")
def gmail_connect(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    integration = crud_integration.get_integration(
        db, firm_id=current_firm.id, provider="gmail"
    )
    if not integration:
        crud_integration.create_integration(db, firm_id=current_firm.id, provider="gmail")

    authorization_url = _gmail_service.get_authorization_url(current_firm.id)
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
