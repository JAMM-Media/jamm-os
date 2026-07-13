# app/services/integration_service.py

from app.services.behavioral_log import log_event


def record_qbo_deep_link_opened(*, firm_id, client_id, quickbooks_customer_id) -> None:
    log_event(
        event_type="integration.qbo_deep_link_opened",
        firm_id=firm_id,
        entity_type="client",
        entity_id=client_id,
        metadata={"quickbooks_customer_id": quickbooks_customer_id},
    )
