# app/crud/invoice.py

import uuid
from datetime import datetime, timezone, date
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate


def get_invoice(db: Session, invoice_id: uuid.UUID, firm_id: uuid.UUID) -> Optional[Invoice]:
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.firm_id == firm_id,
        Invoice.is_deleted == False,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_invoices(
    db: Session,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    status: Optional[InvoiceStatus] = None,
) -> list[Invoice]:
    stmt = select(Invoice).where(
        Invoice.firm_id == firm_id,
        Invoice.is_deleted == False,
    )
    if client_id is not None:
        stmt = stmt.where(Invoice.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(Invoice.engagement_id == engagement_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_invoices_count(
    db: Session,
    firm_id: uuid.UUID,
    client_id: Optional[uuid.UUID] = None,
    engagement_id: Optional[uuid.UUID] = None,
    status: Optional[InvoiceStatus] = None,
) -> int:
    stmt = select(func.count()).select_from(Invoice).where(
        Invoice.firm_id == firm_id,
        Invoice.is_deleted == False,
    )
    if client_id is not None:
        stmt = stmt.where(Invoice.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(Invoice.engagement_id == engagement_id)
    if status is not None:
        stmt = stmt.where(Invoice.status == status)
    return db.execute(stmt).scalar_one()


def create_invoice(
    db: Session,
    invoice_in: InvoiceCreate,
    firm_id: uuid.UUID,
    created_by: uuid.UUID,
) -> Invoice:
    count_stmt = select(func.count()).select_from(Invoice).where(Invoice.firm_id == firm_id)
    existing_count = db.execute(count_stmt).scalar_one()
    invoice_number = f"INV-{(existing_count + 1):04d}"

    data = invoice_in.model_dump(exclude={"invoice_number"})
    line_items = data.get("line_items")
    if line_items:
        data["line_items"] = [
            {k: str(v) for k, v in item.items()} for item in line_items
        ]

    invoice = Invoice(
        **data,
        firm_id=firm_id,
        created_by=created_by,
        invoice_number=invoice_number,
    )
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return invoice


def update_invoice(db: Session, invoice: Invoice, invoice_in: InvoiceUpdate) -> Invoice:
    updates = invoice_in.model_dump(exclude_unset=True)
    if "line_items" in updates and updates["line_items"] is not None:
        updates["line_items"] = [
            {k: str(v) for k, v in item.items()} for item in updates["line_items"]
        ]
    for field, value in updates.items():
        setattr(invoice, field, value)
    db.commit()
    db.refresh(invoice)
    return invoice


def soft_delete_invoice(db: Session, invoice: Invoice) -> Invoice:
    invoice.is_deleted = True
    invoice.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    return invoice


def mark_invoice_sent(db: Session, invoice: Invoice) -> Invoice:
    invoice.status = InvoiceStatus.sent
    invoice.sent_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)
    return invoice


def mark_invoice_paid(
    db: Session,
    invoice: Invoice,
    stripe_charge_id: Optional[str] = None,
) -> Invoice:
    invoice.status = InvoiceStatus.paid
    invoice.paid_at = datetime.now(timezone.utc)
    if stripe_charge_id is not None:
        invoice.stripe_charge_id = stripe_charge_id
    db.commit()
    db.refresh(invoice)
    return invoice


def set_payment_intent(
    db: Session,
    invoice: Invoice,
    payment_intent_id: str,
) -> Invoice:
    invoice.stripe_payment_intent_id = payment_intent_id
    db.commit()
    db.refresh(invoice)
    return invoice


def get_overdue_invoices(db: Session, firm_id: uuid.UUID) -> list[Invoice]:
    today = date.today()
    stmt = select(Invoice).where(
        Invoice.firm_id == firm_id,
        Invoice.status == InvoiceStatus.sent,
        Invoice.due_date < today,
        Invoice.is_deleted == False,
    )
    return list(db.execute(stmt).scalars().all())


_PORTAL_VISIBLE_STATUSES = (
    InvoiceStatus.sent,
    InvoiceStatus.paid,
    InvoiceStatus.overdue,
)


def get_portal_invoices(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[Invoice]:
    stmt = (
        select(Invoice)
        .where(
            Invoice.client_id == client_id,
            Invoice.firm_id == firm_id,
            Invoice.status.in_(_PORTAL_VISIBLE_STATUSES),
            Invoice.is_deleted == False,
        )
        .order_by(Invoice.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_portal_invoices_count(
    db: Session,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> int:
    stmt = select(func.count()).select_from(Invoice).where(
        Invoice.client_id == client_id,
        Invoice.firm_id == firm_id,
        Invoice.status.in_(_PORTAL_VISIBLE_STATUSES),
        Invoice.is_deleted == False,
    )
    return db.execute(stmt).scalar_one()


def get_portal_invoice(
    db: Session,
    invoice_id: uuid.UUID,
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[Invoice]:
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.client_id == client_id,
        Invoice.firm_id == firm_id,
        Invoice.status.in_(_PORTAL_VISIBLE_STATUSES),
        Invoice.is_deleted == False,
    )
    return db.execute(stmt).scalar_one_or_none()
