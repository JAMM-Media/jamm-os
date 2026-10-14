# app/services/integration_service.py

from sqlalchemy.orm import Session

from app.crud import integration as crud_integration
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event


def record_qbo_deep_link_opened(*, firm_id, client_id, quickbooks_customer_id) -> None:
    log_event(
        event_type="integration.qbo_deep_link_opened",
        firm_id=firm_id,
        entity_type="client",
        entity_id=client_id,
        metadata={"quickbooks_customer_id": quickbooks_customer_id},
    )


def _wipe_and_disconnect(db: Session, integration) -> None:
    integration.encrypted_access_token = None
    integration.encrypted_refresh_token = None
    integration.token_expires_at = None
    integration.connected_at = None
    integration.scopes = None
    integration.external_account_id = None
    crud_integration.update_integration_status(db, integration, status="disconnected")


def disconnect_firm_integration(*, db: Session, integration, firm_id, provider: str, current_user_id) -> None:
    """Firm-level disconnect, moved out of DELETE /integrations/{provider} (Phase 7)."""
    _wipe_and_disconnect(db, integration)
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="integration.disconnected",
        actor_type="staff",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider},
    )
    log_event(
        event_type="integration.disconnected",
        firm_id=firm_id,
        entity_type="integration",
        entity_id=integration.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"provider": provider},
    )


def disconnect_staff_integration(*, db: Session, integration, firm_id, provider: str, current_user_id) -> None:
    """Per-staff disconnect, moved out of DELETE /integrations/staff/{provider} (Phase 7)."""
    _wipe_and_disconnect(db, integration)
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="integration.disconnected",
        actor_type="staff",
        entity_type="integration",
        entity_id=integration.id,
        metadata={"provider": provider, "user_id": str(current_user_id)},
    )
    log_event(
        event_type="integration.disconnected",
        firm_id=firm_id,
        entity_type="integration",
        entity_id=integration.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"provider": provider, "user_id": str(current_user_id)},
    )
