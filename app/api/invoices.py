# app/api/invoices.py

import io
from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import date, datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner, require_manager_or_above, require_staff_or_above
from app.models.user import User
from app.models.firm import Firm
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.schemas.invoice import InvoiceCreate, InvoiceOut, InvoiceUpdate, BulkInvoiceUpdate
from app.schemas.pagination import PaginatedResponse
from app.core.enums import InvoiceStatus, TriggerEvent
from app.api.concierge.functions import get_overdue_invoices
from app.crud import invoice as crud_invoice
from app.crud import time_entry as crud_time_entry
from app.services.invoice_renderer import render_invoice_to_pdf
from app.services.event_bus import emit_event
import app.services.invoice_service as invoice_service

router = APIRouter()


class InvoiceFromTimeEntriesRequest(BaseModel):
    engagement_id: UUID
    tax_rate: Decimal = Decimal("0.0")
    due_date: Optional[date] = None
    notes_client_visible: Optional[str] = None


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------
@router.post("/", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    from app.services.audit_service import write_audit_log
    invoice = await invoice_service.create_invoice(
        db=db, payload=payload, firm_id=current_user.firm_id,
        current_user_id=current_user.id,
        background_tasks=background_tasks,
    )
    write_audit_log(
        db=db,
        firm_id=current_user.firm_id,
        action='invoice.created',
        actor_id=current_user.id,
        actor_type='staff',
        entity_type='invoice',
        entity_id=invoice.id,
    )
    return invoice


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[InvoiceOut])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    status: Optional[InvoiceStatus] = None,
):
    items = crud_invoice.get_invoices(
        db,
        firm_id=current_user.firm_id,
        skip=skip,
        limit=limit,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
    )
    total = crud_invoice.get_invoices_count(
        db,
        firm_id=current_user.firm_id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
    )
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


# ---------------------------------------------------------
# BULK UPDATE INVOICES
# ---------------------------------------------------------
@router.patch("/bulk")
def bulk_update_invoices(
    payload: BulkInvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    count, error = invoice_service.bulk_update_invoices_tracked(
        db=db,
        ids=payload.ids,
        action=payload.action,
        firm_id=current_user.firm_id,
        current_user_id=current_user.id,
    )
    if error == "bad_action":
        raise HTTPException(status_code=400, detail="action must be 'send' or 'void'")
    return {"updated": count}


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/overdue")
def list_overdue_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    return get_overdue_invoices(firm_id=current_user.firm_id, db=db)


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=current_user.firm_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: UUID,
    payload: InvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = invoice_service.update_invoice_tracked(
        db=db,
        invoice_id=invoice_id,
        payload=payload,
        firm_id=current_user.firm_id,
        current_user_id=current_user.id,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Invoice not found")
    if error == "locked":
        raise HTTPException(status_code=400, detail="Cannot modify a paid or void invoice")
    return result


# ---------------------------------------------------------
# DELETE (soft)
# ---------------------------------------------------------
@router.delete("/{invoice_id}")
def delete_invoice(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    result, error = invoice_service.delete_invoice(
        db=db, invoice_id=invoice_id, firm_id=current_user.firm_id,
        current_user_id=current_user.id,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Invoice not found")
    if error == "paid":
        raise HTTPException(status_code=400, detail="Cannot delete a paid invoice")
    return {"message": "Invoice deleted"}


# ---------------------------------------------------------
# SEND
# ---------------------------------------------------------
@router.post("/{invoice_id}/send", response_model=InvoiceOut)
async def send_invoice(
    invoice_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = await invoice_service.send_invoice(
        db=db, invoice_id=invoice_id, firm_id=current_user.firm_id,
        current_user_id=current_user.id,
        background_tasks=background_tasks,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Invoice not found")
    if error == "paid_or_void":
        raise HTTPException(status_code=400, detail="Cannot send a paid or void invoice")
    if error == "already_sent":
        raise HTTPException(status_code=400, detail="Invoice already sent")
    if error == "missing_due_date":
        raise HTTPException(status_code=400, detail="Invoice must have a due date before it can be sent")
    from app.services.audit_service import write_audit_log
    write_audit_log(
        db=db,
        firm_id=current_user.firm_id,
        action='invoice.sent',
        actor_id=current_user.id,
        actor_type='staff',
        entity_type='invoice',
        entity_id=result.id,
    )
    return result


# ---------------------------------------------------------
# PDF
# ---------------------------------------------------------
@router.get("/{invoice_id}/pdf")
def get_invoice_pdf(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=current_user.firm_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    firm = db.execute(select(Firm).where(Firm.id == current_user.firm_id)).scalar_one_or_none()
    client = db.execute(select(Client).where(Client.id == invoice.client_id)).scalar_one_or_none()

    engagement_name: Optional[str] = None
    if invoice.engagement_id is not None:
        engagement = db.execute(
            select(Engagement).where(Engagement.id == invoice.engagement_id)
        ).scalar_one_or_none()
        if engagement:
            engagement_name = engagement.name

    pdf_bytes = render_invoice_to_pdf(invoice, firm, client, engagement_name)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice-{invoice.invoice_number}.pdf"
        },
    )


# ---------------------------------------------------------
# REMIND
# ---------------------------------------------------------
@router.post("/{invoice_id}/remind", response_model=InvoiceOut)
def send_invoice_reminder(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = invoice_service.send_invoice_reminder(
        db=db,
        invoice_id=invoice_id,
        firm_id=current_user.firm_id,
        current_user_id=current_user.id,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Invoice not found")
    if error == "already_paid":
        raise HTTPException(status_code=400, detail="Cannot send a reminder on a paid invoice")
    if error == "void":
        raise HTTPException(status_code=400, detail="Cannot send a reminder on a void invoice")
    if error == "not_sent_yet":
        raise HTTPException(status_code=400, detail="Invoice must be sent before sending a reminder")
    if error == "no_client_email":
        raise HTTPException(status_code=400, detail="Client has no email address on file")
    return result


# ---------------------------------------------------------
# FROM TIME ENTRIES
# ---------------------------------------------------------
@router.post("/from-time-entries", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice_from_time_entries(
    payload: InvoiceFromTimeEntriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = await invoice_service.create_invoice_from_time_entries(
        db=db,
        engagement_id=payload.engagement_id,
        tax_rate=payload.tax_rate,
        due_date=payload.due_date,
        notes_client_visible=payload.notes_client_visible,
        firm_id=current_user.firm_id,
        current_user_id=current_user.id,
    )
    if error == "engagement_not_found":
        raise HTTPException(status_code=404, detail="Engagement not found")
    if error == "no_unbilled_entries":
        raise HTTPException(status_code=400, detail="No unbilled time entries for this engagement")
    return result
