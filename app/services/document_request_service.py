# app/services/document_request_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session

from app.crud import document_request as crud
from app.services.behavioral_log import log_event


def create_document_request(
    *,
    db: Session,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
):
    doc_request = crud.create_document_request(db, payload, firm_id=firm_id)

    item_count = len(doc_request.checklist_items) \
        if hasattr(doc_request, 'checklist_items') and doc_request.checklist_items else None

    log_event(
        firm_id=doc_request.firm_id,
        event_type="document_request.created",
        entity_type="document_request",
        entity_id=doc_request.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "item_count": item_count,
            "engagement_id": str(doc_request.engagement_id)
                if hasattr(doc_request, 'engagement_id') and doc_request.engagement_id else None,
            "client_id": str(doc_request.client_id)
                if hasattr(doc_request, 'client_id') else None,
        }
    )

    log_event(
        firm_id=doc_request.firm_id,
        event_type="document_request.sent",
        entity_type="document_request",
        entity_id=doc_request.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "item_count": item_count,
            "client_id": str(doc_request.client_id)
                if hasattr(doc_request, 'client_id') else None,
        }
    )

    return doc_request


def update_document_request(
    *,
    db: Session,
    request_id: UUID,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
):
    old_request = crud.get_document_request(db, request_id, firm_id=firm_id)
    if not old_request:
        return None

    old_status = str(old_request.status) if hasattr(old_request, 'status') and old_request.status else None

    updated = crud.update_document_request(
        db, request_id, firm_id=firm_id, data=payload
    )
    if not updated:
        return None

    new_status = str(updated.status) if hasattr(updated, 'status') and updated.status else None

    if old_status != new_status and new_status in {"completed", "complete"}:
        log_event(
            firm_id=updated.firm_id,
            event_type="document_request.completed",
            entity_type="document_request",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "item_count": len(updated.checklist_items)
                    if hasattr(updated, 'checklist_items') and updated.checklist_items else None,
                "total_days": (datetime.now(timezone.utc) - updated.created_at).days
                    if updated.created_at else None,
            }
        )

    return updated


def delete_document_request(
    *,
    db: Session,
    request_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    deleted = crud.delete_document_request(db, request_id, firm_id=firm_id)
    return deleted


def update_checklist_item_status(
    *,
    db: Session,
    request_id: UUID,
    item_id: str,
    new_status: str,
    firm_id: UUID,
    current_user_id: UUID,
):
    doc_request = crud.get_document_request(db, request_id, firm_id=firm_id)
    if not doc_request:
        return None, "request_not_found"

    item_ids = [item.get("id") for item in (doc_request.checklist_items or [])]
    if item_id not in item_ids:
        return None, "item_not_found"

    updated = crud.update_checklist_item_status(
        db, request_id, firm_id=firm_id, item_id=item_id, new_status=new_status
    )

    if new_status == "uploaded":
        log_event(
            firm_id=doc_request.firm_id,
            event_type="document_request.item_uploaded",
            entity_type="document_request",
            entity_id=request_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "item_id": item_id,
                "days_since_request_created": (datetime.now(timezone.utc) - doc_request.created_at).days
                    if doc_request.created_at else None,
            }
        )

    if new_status in {"rejected", "waived"}:
        log_event(
            firm_id=doc_request.firm_id,
            event_type="document_request.item_waived",
            entity_type="document_request",
            entity_id=request_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "item_id": item_id,
            }
        )

    return updated, None
