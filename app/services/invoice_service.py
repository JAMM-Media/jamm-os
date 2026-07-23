# app/services/invoice_service.py

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.crud import invoice as crud_invoice
from app.crud import time_entry as crud_time_entry
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus, TriggerEvent
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate
from app.services.event_bus import emit_event
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)


async def create_invoice(
    *,
    db: Session,
    payload,  # InvoiceCreate
    firm_id: UUID,
    current_user_id: UUID,
    background_tasks: BackgroundTasks,
):
    invoice = crud_invoice.create_invoice(
        db,
        invoice_in=payload,
        firm_id=firm_id,
        created_by=current_user_id,
    )

    await emit_event(
        event=TriggerEvent.invoice_created,
        payload={
            "firm_id": str(invoice.firm_id),
            "invoice_id": str(invoice.id),
            "client_id": str(invoice.client_id),
            "engagement_id": str(invoice.engagement_id) if invoice.engagement_id else None,
        },
        background_tasks=background_tasks,
    )

    log_event(
        firm_id=invoice.firm_id,
        event_type="invoice.created",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "amount": str(invoice.total_amount) if invoice.total_amount else None,
            "engagement_linked": invoice.engagement_id is not None,
            "client_id": str(invoice.client_id),
            "engagement_id": str(invoice.engagement_id) if invoice.engagement_id else None,
        }
    )

    return invoice


async def send_invoice(
    *,
    db: Session,
    invoice_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
    background_tasks: BackgroundTasks,
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=firm_id)
    if not invoice:
        return None, "not_found"
    if invoice.status in (InvoiceStatus.paid, InvoiceStatus.void):
        return None, "paid_or_void"
    if invoice.status == InvoiceStatus.sent:
        return None, "already_sent"
    if invoice.due_date is None:
        return None, "missing_due_date"

    result = crud_invoice.mark_invoice_sent(db, invoice)

    await emit_event(
        event=TriggerEvent.invoice_sent,
        payload={
            "firm_id": str(result.firm_id),
            "invoice_id": str(result.id),
            "client_id": str(result.client_id),
        },
        background_tasks=background_tasks,
    )

    log_event(
        firm_id=result.firm_id,
        event_type="invoice.sent",
        entity_type="invoice",
        entity_id=result.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "amount": str(result.total_amount) if result.total_amount else None,
            "days_since_creation": (datetime.now(timezone.utc) - result.created_at).days
                if result.created_at else None,
            "client_id": str(result.client_id),
            "delivery_method": "email",
        }
    )

    # sent_at is set once and never cleared by later status transitions
    # (paid/overdue/etc.), unlike status itself - counting on status=='sent'
    # would undercount every time an earlier invoice moved on to another
    # status, causing this to refire on every single send.
    sent_count = db.execute(
        select(func.count()).where(
            Invoice.firm_id == firm_id,
            Invoice.sent_at.isnot(None),
        )
    ).scalar()
    if sent_count == 1:
        log_event(
            firm_id=result.firm_id,
            event_type="firm.first_invoice_sent",
            entity_type="firm",
            entity_id=result.firm_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={}
        )

    try:
        from app.services.email_service import EmailService
        from app.core.config import get_settings as _get_settings
        _settings = _get_settings()
        firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()
        client = db.execute(select(Client).where(Client.id == result.client_id)).scalar_one_or_none()
        if firm and client and client.email:
            email_settings = EmailService.get_firm_email_settings(firm)
            amount_due = f"${float(result.total_amount):,.2f}" if result.total_amount else "N/A"
            due_date_str = result.due_date.strftime("%B %d, %Y") if result.due_date else "N/A"
            EmailService.send_invoice_email(
                to_email=client.email,
                firm_name=firm.name,
                recipient_name=client.name,
                invoice_number=result.invoice_number,
                amount_due=amount_due,
                due_date=due_date_str,
                payment_url=f"{_settings.FRONTEND_URL}/portal",
                reply_to=email_settings["reply_to"],
                display_name=email_settings["display_name"],
                sending_domain=email_settings.get("sending_domain"),
            )
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).error("Invoice email failed: %s", str(_e))

    return result, None


def mark_invoice_paid(
    *,
    db: Session,
    invoice: Invoice,  # already-fetched invoice ORM object
    firm_id: UUID,
    payment_method: str = "stripe",
):
    log_event(
        firm_id=firm_id,
        event_type="invoice.paid",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "amount": str(invoice.total_amount) if invoice.total_amount else None,
            "payment_method": payment_method,
            "days_since_sent": (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at else None,
            "client_id": str(invoice.client_id) if invoice.client_id else None,
        }
    )


def mark_invoice_overdue(
    *,
    db: Session,
    invoice: Invoice,
):
    log_event(
        firm_id=invoice.firm_id,
        event_type="invoice.overdue",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "amount": str(invoice.total_amount) if hasattr(invoice, 'total_amount') else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at
                else None
            ),
            "client_id": str(invoice.client_id),
        }
    )


def run_invoice_overdue_sweep() -> None:
    """
    Daily sweep: transitions sent/partial invoices past their due_date to
    overdue and fires invoice.overdue for each. The status transition is the
    idempotency guard -- once an invoice is overdue it no longer matches the
    sent/partial filter, so it is never selected (and never events-fired)
    again.
    """
    try:
        db = SessionLocal()
        try:
            today = datetime.now(timezone.utc).date()
            stmt = select(Invoice).where(
                Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.partial]),
                Invoice.due_date.isnot(None),
                Invoice.due_date < today,
                Invoice.is_deleted == False,  # noqa: E712
            )
            invoices = db.execute(stmt).scalars().all()

            for invoice in invoices:
                try:
                    invoice.status = InvoiceStatus.overdue
                    db.commit()
                    mark_invoice_overdue(db=db, invoice=invoice)
                except Exception as exc:
                    db.rollback()
                    logger.error(
                        "run_invoice_overdue_sweep: failed for invoice %s: %s",
                        invoice.id, exc, exc_info=True,
                    )
        finally:
            db.close()
    except Exception as exc:
        logger.error("run_invoice_overdue_sweep failed: %s", exc, exc_info=True)


def delete_invoice(
    *,
    db: Session,
    invoice_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=firm_id)
    if not invoice:
        return None, "not_found"
    if invoice.status == InvoiceStatus.paid:
        return None, "paid"

    amount = str(invoice.total_amount) if invoice.total_amount else None
    days_since_creation = (datetime.now(timezone.utc) - invoice.created_at).days \
        if invoice.created_at else None
    inv_firm_id = invoice.firm_id

    crud_invoice.soft_delete_invoice(db, invoice)

    log_event(
        firm_id=inv_firm_id,
        event_type="invoice.voided",
        entity_type="invoice",
        entity_id=invoice_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "amount": amount,
            "days_since_creation": days_since_creation,
        }
    )

    return True, None


async def create_invoice_from_time_entries(
    *,
    db: Session,
    engagement_id: UUID,
    tax_rate: Decimal,
    due_date,
    notes_client_visible: Optional[str],
    firm_id: UUID,
    current_user_id: UUID,
):
    from app.schemas.invoice import InvoiceCreate as InvoiceCreateSchema

    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if not engagement:
        return None, "engagement_not_found"

    entries = crud_time_entry.get_unbilled_entries_for_engagement(
        db,
        engagement_id=engagement_id,
        firm_id=firm_id,
    )
    if not entries:
        return None, "no_unbilled_entries"

    line_items = []
    subtotal = Decimal("0.0")
    for entry in entries:
        hours = Decimal(str(entry.hours))
        rate = Decimal(str(entry.hourly_rate))
        total = hours * rate
        subtotal += total
        line_items.append({
            "description": entry.description,
            "quantity": hours,
            "unit_price": rate,
            "total": total,
        })

    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount

    invoice_in = InvoiceCreateSchema(
        invoice_number="",
        line_items=line_items,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        client_id=engagement.client_id,
        engagement_id=engagement_id,
        due_date=due_date,
        notes_client_visible=notes_client_visible,
    )

    invoice = crud_invoice.create_invoice(
        db,
        invoice_in=invoice_in,
        firm_id=firm_id,
        created_by=current_user_id,
    )

    crud_time_entry.mark_entries_as_billed(
        db,
        entry_ids=[e.id for e in entries],
        invoice_id=invoice.id,
    )

    log_event(
        firm_id=invoice.firm_id,
        event_type="invoice.created",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "amount": str(invoice.total_amount) if invoice.total_amount else None,
            "engagement_linked": True,
            "client_id": str(invoice.client_id),
            "engagement_id": str(engagement_id),
            "created_from_time_entries": True,
            "time_entry_count": len(entries),
        }
    )

    return invoice, None


def send_invoice_reminder(
    db: Session,
    invoice_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=firm_id)
    if not invoice:
        return None, "not_found"

    if invoice.status == InvoiceStatus.paid:
        return None, "already_paid"
    if invoice.status == InvoiceStatus.void:
        return None, "void"
    if invoice.status == InvoiceStatus.draft:
        return None, "not_sent_yet"

    client = db.execute(select(Client).where(Client.id == invoice.client_id)).scalar_one_or_none()
    firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()

    if not client or not client.email:
        return None, "no_client_email"

    invoice.reminder_count += 1
    invoice.last_reminder_sent_at = datetime.now(timezone.utc)
    db.commit()

    try:
        from app.services.email_service import EmailService
        from app.core.config import get_settings as _get_settings
        _settings = _get_settings()
        email_settings = EmailService.get_firm_email_settings(firm)
        amount_due = f"${float(invoice.total_amount):,.2f}" if invoice.total_amount else "N/A"
        due_date_str = invoice.due_date.strftime("%B %d, %Y") if invoice.due_date else "N/A"
        EmailService.send_invoice_email(
            to_email=client.email,
            firm_name=firm.name,
            recipient_name=client.name,
            invoice_number=invoice.invoice_number,
            amount_due=amount_due,
            due_date=due_date_str,
            payment_url=f"{_settings.FRONTEND_URL}/portal",
            reply_to=email_settings["reply_to"],
            display_name=email_settings["display_name"],
            sending_domain=email_settings.get("sending_domain"),
        )
    except Exception as _e:
        import logging as _logging
        _logging.getLogger(__name__).error("Invoice reminder email failed: %s", str(_e))

    log_event(
        firm_id=firm_id,
        event_type="invoice.reminder_sent",
        entity_type="invoice",
        entity_id=invoice_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "reminder_number": invoice.reminder_count,
            "amount": str(invoice.total_amount) if invoice.total_amount else None,
            "days_since_sent": (datetime.now(timezone.utc) - invoice.sent_at).days
                if invoice.sent_at else None,
            "days_overdue": (datetime.now(timezone.utc).date() - invoice.due_date).days
                if invoice.due_date and invoice.due_date < datetime.now(timezone.utc).date() else None,
            "client_id": str(invoice.client_id),
        }
    )

    return invoice, None


def update_invoice_tracked(
    *,
    db: Session,
    invoice_id: UUID,
    payload: InvoiceUpdate,
    firm_id: UUID,
    current_user_id: UUID,
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=firm_id)
    if not invoice:
        return None, "not_found"
    if invoice.status in (InvoiceStatus.paid, InvoiceStatus.void):
        return None, "locked"

    # Capture before-values for meaningful fields
    old_status = invoice.status
    old_total = float(invoice.total_amount) if invoice.total_amount is not None else None
    old_due_date = invoice.due_date

    # Fields already covered by a dedicated event below -- excluded from the
    # generic no-silent-changes delta so they are not double-logged.
    _EVENTED_FIELDS = {"status", "total_amount", "due_date"}
    _tracked_fields = [
        f for f in payload.model_dump(exclude_unset=True).keys()
        if f not in _EVENTED_FIELDS
    ]
    _old_values = {f: getattr(invoice, f) for f in _tracked_fields}

    updated = crud_invoice.update_invoice(db, invoice, payload)

    # Fire events only for meaningful state changes, with before/after
    new_status = updated.status
    if new_status != old_status:
        log_event(
            firm_id=firm_id,
            event_type="invoice.status_changed",
            entity_type="invoice",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_status": str(old_status),
                "to_status": str(new_status),
                "client_id": str(updated.client_id),
            }
        )
        if new_status == InvoiceStatus.paid:
            # Manual mark-paid: same crud + event mechanics as the Stripe
            # webhook's full-payment branch (api/payments.py), so both
            # paths produce an identical invoice.paid event. A manual
            # mark-paid is always a full payment; partial offline payments
            # are a different flow that doesn't exist yet.
            crud_invoice.mark_invoice_paid(db, updated)
            updated.amount_paid = updated.total_amount
            db.commit()
            db.refresh(updated)
            mark_invoice_paid(db=db, invoice=updated, firm_id=firm_id, payment_method="manual")

    new_total = float(updated.total_amount) if updated.total_amount is not None else None
    if new_total != old_total:
        log_event(
            firm_id=firm_id,
            event_type="invoice.amount_changed",
            entity_type="invoice",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_amount": str(old_total) if old_total is not None else None,
                "to_amount": str(new_total) if new_total is not None else None,
                "client_id": str(updated.client_id),
            }
        )

    if updated.due_date != old_due_date:
        log_event(
            firm_id=firm_id,
            event_type="invoice.due_date_changed",
            entity_type="invoice",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_due_date": old_due_date.isoformat() if old_due_date else None,
                "to_due_date": updated.due_date.isoformat() if updated.due_date else None,
                "client_id": str(updated.client_id),
            }
        )

    from app.services.behavioral_log import build_changed_fields

    _new_values = {f: getattr(updated, f) for f in _tracked_fields}
    _changed_fields = build_changed_fields(_old_values, _new_values)
    if _changed_fields:
        log_event(
            firm_id=firm_id,
            event_type="invoice.updated",
            entity_type="invoice",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": _changed_fields},
        )

    return updated, None


def bulk_update_invoices_tracked(
    *,
    db: Session,
    ids: list,
    action: str,
    firm_id: UUID,
    current_user_id: UUID,
):
    from app.models.invoice import Invoice
    from datetime import datetime, timezone
    if action not in ("send", "void"):
        return None, "bad_action"

    stmt = select(Invoice).where(
        Invoice.id.in_(ids),
        Invoice.firm_id == firm_id,
        Invoice.is_deleted == False,  # noqa: E712
    )
    invoices = db.execute(stmt).scalars().all()
    now = datetime.now(timezone.utc)

    transitioned = []
    for inv in invoices:
        old_status = inv.status
        if action == "send":
            inv.status = InvoiceStatus.sent
            inv.sent_at = now
        else:
            inv.status = InvoiceStatus.void
        transitioned.append((inv, old_status))

    db.commit()

    for inv, old_status in transitioned:
        log_event(
            firm_id=firm_id,
            event_type="invoice.status_changed",
            entity_type="invoice",
            entity_id=inv.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_status": str(old_status),
                "to_status": str(inv.status),
                "client_id": str(inv.client_id),
                "via": "bulk",
                "bulk_action": action,
            }
        )

    return len(transitioned), None


# ------------------------------------------------------------
# Stripe webhook behavioral events. Called from app/api/payments.py
# after the invoice row itself has already been updated via the
# matching app/crud/invoice.py function.
# ------------------------------------------------------------

def mark_invoice_partial_payment(
    *,
    db: Session,
    invoice: Invoice,
    firm_id: UUID,
    amount_paid: float,
    remaining_balance: float,
    payment_method: str = "stripe",
) -> None:
    log_event(
        firm_id=firm_id,
        event_type="invoice.partial_payment",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "amount_paid": str(amount_paid),
            "remaining_balance": str(remaining_balance),
            "days_since_sent": (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at else None,
        }
    )


def mark_invoice_refunded(
    *,
    db: Session,
    invoice: Invoice,
    firm_id: UUID,
    amount_refunded: float,
    reason: Optional[str] = None,
) -> None:
    log_event(
        firm_id=firm_id,
        event_type="invoice.refunded",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "amount_refunded": str(amount_refunded),
            "reason": reason,
            "days_since_payment": (datetime.now(timezone.utc) - invoice.paid_at).days
                if hasattr(invoice, 'paid_at') and invoice.paid_at else None,
        }
    )


def mark_invoice_payment_failed(
    *,
    db: Session,
    invoice: Invoice,
    firm_id: UUID,
    failure_code: Optional[str] = None,
    failure_message: Optional[str] = None,
) -> None:
    log_event(
        firm_id=firm_id,
        event_type="invoice.payment_failed",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "amount": str(invoice.total_amount) if invoice.total_amount else None,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "days_since_sent": (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at else None,
        }
    )
