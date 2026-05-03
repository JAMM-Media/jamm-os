# app/services/automation_actions.py

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4, UUID

import httpx
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.engagement import Engagement
from app.models.task import Task
from app.models.invoice import Invoice
from app.models.client import Client
from app.core.enums import (
    AutomationActionType,
    EngagementStatus,
    InvoiceStatus,
)

logger = logging.getLogger(__name__)


def execute(
    action_type: str,
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    logger.info(f"Executing action: {action_type}")

    if action_type == AutomationActionType.create_task:
        return _handle_create_task(config, payload, db)
    elif action_type == AutomationActionType.assign_task:
        return _handle_assign_task(config, payload, db)
    elif action_type == AutomationActionType.update_engagement_status:
        return _handle_update_engagement_status(config, payload, db)
    elif action_type == AutomationActionType.create_invoice:
        return _handle_create_invoice(config, payload, db)
    elif action_type == AutomationActionType.add_internal_note:
        return _handle_add_internal_note(config, payload, db)
    elif action_type == AutomationActionType.webhook_post:
        return _handle_webhook_post(config, payload, db)
    elif action_type == AutomationActionType.send_email:
        return _handle_send_email(config, payload, db)
    elif action_type == AutomationActionType.send_notification:
        return _handle_send_notification(config, payload, db)
    elif action_type == AutomationActionType.create_document_request:
        return _handle_create_document_request(config, payload, db)
    elif action_type == AutomationActionType.send_document_request_reminder:
        return _handle_send_document_request_reminder(config, payload, db)
    else:
        logger.warning(f"Unknown action type: {action_type!r}")
        return f"Unknown action type: {action_type}"


def _handle_create_task(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    title = config.get("title")
    if not title:
        logger.warning("create_task skipped: no title in config")
        return "create_task skipped: no title in config"

    description = config.get("description", "")
    due_days_from_now = config.get("due_days_from_now")

    firm_id = payload.get("firm_id")
    engagement_id = payload.get("engagement_id")
    client_id = payload.get("client_id")

    due_date = None
    if due_days_from_now is not None:
        due_date = (datetime.now(timezone.utc) + timedelta(days=int(due_days_from_now))).date()

    now = datetime.now(timezone.utc)
    task = Task(
        id=uuid4(),
        firm_id=UUID(str(firm_id)) if firm_id and not isinstance(firm_id, UUID) else firm_id,
        title=title,
        notes=description if description else None,
        engagement_id=UUID(str(engagement_id)) if engagement_id and not isinstance(engagement_id, UUID) else engagement_id,
        client_id=UUID(str(client_id)) if client_id and not isinstance(client_id, UUID) else client_id,
        due_date=due_date,
        status="todo",
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    return f"Task created: {title}"


def _handle_assign_task(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    task_id = config.get("task_id")
    assign_to_user_id = config.get("assign_to_user_id")

    if not task_id or not assign_to_user_id:
        return "assign_task skipped: missing task_id or assign_to_user_id"

    firm_id_raw = payload.get("firm_id")
    firm_id = UUID(str(firm_id_raw)) if firm_id_raw and not isinstance(firm_id_raw, UUID) else firm_id_raw

    stmt = select(Task).where(
        Task.id == UUID(str(task_id)),
        Task.firm_id == firm_id,
    )
    task = db.execute(stmt).scalar_one_or_none()
    if not task:
        return "assign_task skipped: task not found"

    task.assigned_to = UUID(str(assign_to_user_id))
    db.commit()
    return f"Task {task_id} assigned to {assign_to_user_id}"


def _handle_update_engagement_status(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    new_status = config.get("new_status")
    engagement_id_raw = payload.get("engagement_id")
    firm_id_raw = payload.get("firm_id")

    if not engagement_id_raw or not new_status:
        return "update_engagement_status skipped: missing engagement_id or new_status"

    valid_statuses = {e.value for e in EngagementStatus}
    if new_status not in valid_statuses:
        return f"update_engagement_status skipped: invalid status {new_status}"

    firm_id = UUID(str(firm_id_raw)) if firm_id_raw and not isinstance(firm_id_raw, UUID) else firm_id_raw
    engagement_id = UUID(str(engagement_id_raw)) if not isinstance(engagement_id_raw, UUID) else engagement_id_raw

    stmt = select(Engagement).where(
        Engagement.id == engagement_id,
        Engagement.firm_id == firm_id,
    )
    engagement = db.execute(stmt).scalar_one_or_none()
    if not engagement:
        return "update_engagement_status skipped: engagement not found"

    engagement.status = new_status
    engagement.updated_at = datetime.now(timezone.utc)
    db.commit()
    return f"Engagement {engagement_id} status updated to {new_status}"


def _handle_create_invoice(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    line_items = config.get("line_items")
    if not line_items:
        return "create_invoice skipped: no line_items in config"

    client_id_raw = payload.get("client_id")
    if not client_id_raw:
        return "create_invoice skipped: no client_id in payload"

    due_days_from_now = config.get("due_days_from_now", 30)
    firm_id_raw = payload.get("firm_id")
    engagement_id_raw = payload.get("engagement_id")

    firm_id = UUID(str(firm_id_raw)) if firm_id_raw and not isinstance(firm_id_raw, UUID) else firm_id_raw
    client_id = UUID(str(client_id_raw)) if not isinstance(client_id_raw, UUID) else client_id_raw
    engagement_id = UUID(str(engagement_id_raw)) if engagement_id_raw and not isinstance(engagement_id_raw, UUID) else engagement_id_raw

    subtotal = Decimal("0")
    for item in line_items:
        qty = Decimal(str(item.get("quantity", 1)))
        price = Decimal(str(item.get("unit_price", 0)))
        subtotal += qty * price

    count_stmt = select(func.count()).select_from(Invoice).where(Invoice.firm_id == firm_id)
    existing_count = db.execute(count_stmt).scalar_one()
    invoice_number = f"INV-{(existing_count + 1):04d}"

    now = datetime.now(timezone.utc)
    due_date = (now + timedelta(days=int(due_days_from_now))).date()

    invoice = Invoice(
        id=uuid4(),
        firm_id=firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        invoice_number=invoice_number,
        line_items=line_items,
        subtotal=subtotal,
        tax_rate=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=subtotal,
        status=InvoiceStatus.draft,
        due_date=due_date,
        created_at=now,
        updated_at=now,
    )
    db.add(invoice)
    db.commit()
    return f"Invoice {invoice_number} created"


def _handle_add_internal_note(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    note_text = config.get("note_text")
    if not note_text:
        return "add_internal_note skipped: no note_text in config"

    entity_type = config.get("entity_type")
    firm_id_raw = payload.get("firm_id")
    firm_id = UUID(str(firm_id_raw)) if firm_id_raw and not isinstance(firm_id_raw, UUID) else firm_id_raw
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    timestamped_note = f"[{timestamp}] {note_text}"

    if entity_type == "engagement" and payload.get("engagement_id"):
        engagement_id_raw = payload.get("engagement_id")
        engagement_id = UUID(str(engagement_id_raw)) if not isinstance(engagement_id_raw, UUID) else engagement_id_raw
        stmt = select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.firm_id == firm_id,
        )
        engagement = db.execute(stmt).scalar_one_or_none()
        if engagement:
            if engagement.notes is None:
                engagement.notes = timestamped_note
            else:
                engagement.notes = engagement.notes + "\n" + timestamped_note
            db.commit()
            return f"Note added to engagement {engagement_id}"

    if (entity_type == "client" or not entity_type) and payload.get("client_id"):
        client_id_raw = payload.get("client_id")
        client_id = UUID(str(client_id_raw)) if not isinstance(client_id_raw, UUID) else client_id_raw
        stmt = select(Client).where(
            Client.id == client_id,
            Client.firm_id == firm_id,
        )
        client = db.execute(stmt).scalar_one_or_none()
        if client:
            if client.notes is None:
                client.notes = timestamped_note
            else:
                client.notes = client.notes + "\n" + timestamped_note
            db.commit()
            return f"Note added to client {client_id}"

    return "add_internal_note skipped: no target entity found in payload"


def _handle_webhook_post(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    url = config.get("url")
    if not url:
        return "webhook_post skipped: no url in config"

    headers = config.get("headers", {})
    merged_headers = {
        "Content-Type": "application/json",
        "User-Agent": "JAMM-PX-Automation/1.0",
        **headers,
    }

    try:
        response = httpx.post(url, json=payload, headers=merged_headers, timeout=10)
        if response.is_success:
            return f"Webhook posted to {url}, status {response.status_code}"
        else:
            return f"Webhook to {url} returned {response.status_code}"
    except Exception as e:
        logger.warning(f"Webhook to {url} failed: {e}")
        return f"Webhook to {url} failed: {str(e)}"


def _handle_send_email(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    from app.services.email_service import EmailService

    to_email = payload.get("to_email")
    title = payload.get("title")

    if not to_email or not title:
        logger.warning("send_email skipped: missing to_email or title in payload")
        return "send_email skipped: missing to_email or title"

    firm_name = payload.get("firm_name", "")
    body = payload.get("body", "")

    success = EmailService.send_notification_email(
        to_email=to_email,
        firm_name=firm_name,
        recipient_name=payload.get("recipient_name", ""),
        title=title,
        body=body,
        app_url=payload.get("app_url", ""),
    )
    if success:
        return f"Email sent to {to_email}"
    return f"Email to {to_email} failed — check logs"


def _handle_send_notification(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    from app.db.session import SessionLocal
    from app.services.notification_service import NotificationService
    from app.core.enums import RecipientType, NotificationType

    recipient_id_raw = payload.get("recipient_id")
    title = payload.get("title")

    if not recipient_id_raw or not title:
        logger.warning("send_notification skipped: missing recipient_id or title in payload")
        return "send_notification skipped: missing recipient_id or title"

    recipient_type_raw = payload.get("recipient_type", "staff")
    body = payload.get("body", "")
    notification_type_raw = payload.get("notification_type", "system")
    firm_id_raw = payload.get("firm_id")

    try:
        recipient_id = UUID(str(recipient_id_raw)) if not isinstance(recipient_id_raw, UUID) else recipient_id_raw
        firm_id = UUID(str(firm_id_raw)) if firm_id_raw and not isinstance(firm_id_raw, UUID) else firm_id_raw
        recipient_type = RecipientType(recipient_type_raw)
        notification_type = NotificationType(notification_type_raw)
    except (ValueError, KeyError) as e:
        logger.warning(f"send_notification skipped: invalid enum or UUID value: {e}")
        return f"send_notification skipped: invalid value: {e}"

    notification_db = SessionLocal()
    try:
        NotificationService.create_notification(
            db=notification_db,
            firm_id=firm_id,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            title=title,
            body=body,
            notification_type=notification_type,
        )
        return f"Notification sent to recipient {recipient_id}"
    finally:
        notification_db.close()


def _handle_create_document_request(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    logger.info("create_document_request action triggered")
    return "create_document_request placeholder: will execute when document request module is wired"


def _handle_send_document_request_reminder(
    config: Dict[str, Any],
    payload: Dict[str, Any],
    db: Session,
) -> str:
    logger.info("send_document_request_reminder action triggered")
    return "send_document_request_reminder placeholder: will execute when reminder service is built"
