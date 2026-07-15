# app/services/document_request_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import document_request as crud
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
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

    try:
        from app.services.email_service import EmailService
        from app.core.config import get_settings as _get_settings
        _settings = _get_settings()
        firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()
        client = db.execute(select(Client).where(Client.id == doc_request.client_id)).scalar_one_or_none()
        engagement = db.execute(select(Engagement).where(Engagement.id == doc_request.engagement_id)).scalar_one_or_none()
        if firm and client and client.email:
            email_settings = EmailService.get_firm_email_settings(firm)
            items = [item.get("label", "") for item in (doc_request.checklist_items or [])]
            EmailService.send_document_request_email(
                to_email=client.email,
                firm_name=firm.name,
                recipient_name=client.name,
                engagement_name=engagement.name if engagement else "",
                document_request_title=doc_request.title,
                items=items,
                portal_url=f"{_settings.FRONTEND_URL}/portal",
                reply_to=email_settings["reply_to"],
                display_name=email_settings["display_name"],
                sending_domain=email_settings.get("sending_domain"),
            )
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).error("Document request email failed: %s", str(_e))

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
    old_due_date = old_request.due_date if hasattr(old_request, 'due_date') else None

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

    new_due_date = updated.due_date if hasattr(updated, 'due_date') else None
    if old_due_date != new_due_date:
        log_event(
            firm_id=updated.firm_id,
            event_type="document_request.due_date_changed",
            entity_type="document_request",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_due_date": old_due_date.isoformat() if old_due_date else None,
                "to_due_date": new_due_date.isoformat() if new_due_date else None,
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


def send_document_request_reminder(
    *,
    db: Session,
    request_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    doc_request = crud.get_document_request(db, request_id, firm_id=firm_id)
    if not doc_request:
        return None, "request_not_found"

    if str(doc_request.status) in {"completed", "complete"}:
        return None, "already_completed"

    client = db.execute(select(Client).where(Client.id == doc_request.client_id)).scalar_one_or_none()
    firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()

    if not client or not client.email:
        return None, "no_client_email"

    prev_last_reminder = doc_request.last_reminder_sent_at

    doc_request.reminder_count = (doc_request.reminder_count or 0) + 1
    doc_request.last_reminder_sent_at = datetime.now(timezone.utc)
    db.commit()

    try:
        from app.services.email_service import EmailService
        from app.core.config import get_settings as _get_settings
        _settings = _get_settings()
        engagement = db.execute(
            select(Engagement).where(Engagement.id == doc_request.engagement_id)
        ).scalar_one_or_none()
        if firm:
            email_settings = EmailService.get_firm_email_settings(firm)
            items = [item.get("label", "") for item in (doc_request.checklist_items or [])]
            EmailService.send_document_request_email(
                to_email=client.email,
                firm_name=firm.name,
                recipient_name=client.name,
                engagement_name=engagement.name if engagement else "",
                document_request_title=doc_request.title,
                items=items,
                portal_url=f"{_settings.FRONTEND_URL}/portal",
                reply_to=email_settings["reply_to"],
                display_name=email_settings["display_name"],
                sending_domain=email_settings.get("sending_domain"),
            )
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).error("Document request reminder email failed: %s", str(_e))

    days_since_last_reminder = (
        (datetime.now(timezone.utc) - prev_last_reminder).days
        if prev_last_reminder else None
    )

    item_count = len(doc_request.checklist_items) if doc_request.checklist_items else 0

    log_event(
        firm_id=firm_id,
        event_type="document_request.reminder_sent",
        entity_type="document_request",
        entity_id=request_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "reminder_number": doc_request.reminder_count,
            "days_since_created": (datetime.now(timezone.utc) - doc_request.created_at).days
                if doc_request.created_at else None,
            "days_since_last_reminder": days_since_last_reminder,
            "item_count": item_count,
            "client_id": str(doc_request.client_id),
        }
    )

    return doc_request, None


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

    if new_status == "waived":
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

    if new_status == "rejected":
        log_event(
            firm_id=doc_request.firm_id,
            event_type="document_request.item_rejected",
            entity_type="document_request",
            entity_id=request_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "item_id": item_id,
            }
        )

    if new_status == "approved":
        log_event(
            firm_id=doc_request.firm_id,
            event_type="document_request.item_approved",
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

    return updated, None
