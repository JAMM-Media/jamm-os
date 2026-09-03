# app/services/portal_preview_service.py

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import message as crud_message
from app.crud import portal_notification as crud_portal_notification
from app.core.enums import InvoiceStatus
from app.models.client import Client
from app.models.document import Document
from app.models.document_request import DocumentRequest
from app.models.invoice import Invoice
from app.models.message import ClientMessage
from app.models.portal_notification import PortalNotification
from app.models.tax_organizer import TaxOrganizer
from app.schemas.portal_preview import (
    PortalPreviewBillingSummary,
    PortalPreviewDocumentItem,
    PortalPreviewDocumentRequestItem,
    PortalPreviewInvoiceItem,
    PortalPreviewMessageSummary,
    PortalPreviewNotificationItem,
    PortalPreviewNotificationSummary,
    PortalPreviewOrganizerSummary,
    PortalPreviewOut,
)


def get_portal_preview(
    db: Session,
    firm_id: UUID,
    client_id: UUID,
) -> PortalPreviewOut:
    """
    Assemble a read-only snapshot of everything a client would see in their
    portal. Used by staff to preview the client portal view without logging
    in as the client.
    """

    # 1. Verify the client exists and belongs to this firm
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    # 2. Document requests — DocumentRequest has no is_deleted column
    doc_request_rows = db.execute(
        select(DocumentRequest).where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.client_id == client_id,
        )
    ).scalars().all()

    document_requests = []
    for dr in doc_request_rows:
        checklist = dr.checklist_items or []
        items_total = len(checklist)
        items_completed = sum(
            1 for item in checklist if item.get("status") == "approved"
        )
        document_requests.append(
            PortalPreviewDocumentRequestItem(
                id=dr.id,
                title=dr.title,
                status=dr.status,
                due_date=dr.due_date,
                items_total=items_total,
                items_completed=items_completed,
            )
        )

    # 3. Documents — Document model has no visibility or is_deleted column;
    #    map filename → name, created_at → uploaded_at
    doc_rows = db.execute(
        select(Document)
        .where(
            Document.firm_id == firm_id,
            Document.client_id == client_id,
        )
        .order_by(Document.created_at.desc())
        .limit(20)
    ).scalars().all()

    documents = [
        PortalPreviewDocumentItem(
            id=doc.id,
            name=doc.filename,
            uploaded_at=doc.created_at,
            visibility="client_visible",
        )
        for doc in doc_rows
    ]

    # 4. Invoices — exclude draft status and soft-deleted rows
    invoice_rows = db.execute(
        select(Invoice)
        .where(
            Invoice.firm_id == firm_id,
            Invoice.client_id == client_id,
            Invoice.status != InvoiceStatus.draft,
            Invoice.is_deleted.is_(False),
        )
        .order_by(Invoice.due_date.desc())
        .limit(20)
    ).scalars().all()

    invoices = [
        PortalPreviewInvoiceItem(
            id=inv.id,
            invoice_number=inv.invoice_number,
            amount_due=float(inv.total_amount),
            status=inv.status.value if hasattr(inv.status, "value") else str(inv.status),
            due_date=inv.due_date,
        )
        for inv in invoice_rows
    ]

    # 5. Messages — unread count (staff-sent messages unread by the client)
    #    and the most recent message timestamp
    unread_count = crud_message.get_unread_count_for_client(
        db, firm_id=firm_id, client_id=client_id
    )

    latest_msg = db.execute(
        select(ClientMessage)
        .where(
            ClientMessage.firm_id == firm_id,
            ClientMessage.client_id == client_id,
            ClientMessage.is_deleted.is_(False),
        )
        .order_by(ClientMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    messages = PortalPreviewMessageSummary(
        unread_count=unread_count,
        last_message_at=latest_msg.created_at if latest_msg else None,
    )

    # 6. Notifications -- unread count and 5 most recent
    notif_unread = crud_portal_notification.get_unread_count(
        db, client_id=client_id, firm_id=firm_id
    )
    notif_rows = crud_portal_notification.get_notifications_for_client(
        db, client_id=client_id, firm_id=firm_id, limit=5
    )
    notifications = PortalPreviewNotificationSummary(
        unread_count=notif_unread,
        recent=[
            PortalPreviewNotificationItem(
                id=n.id,
                title=n.title,
                body=n.body,
                notification_type=n.notification_type,
                is_read=n.is_read,
                created_at=n.created_at,
            )
            for n in notif_rows
        ],
    )

    # 7. Billing summary -- aggregated from non-draft invoices
    from app.core.enums import InvoiceStatus as IS
    total_invoiced = sum(
        float(inv.total_amount) for inv in invoice_rows
    )
    total_outstanding = sum(
        float(inv.total_amount) for inv in invoice_rows
        if str(inv.status.value if hasattr(inv.status, "value") else inv.status)
        not in ("paid", "void")
    )
    billing = PortalPreviewBillingSummary(
        total_invoiced=total_invoiced,
        total_outstanding=total_outstanding,
        invoice_count=len(invoice_rows),
    )

    # 8. Tax organizer -- count and status breakdown
    organizer_rows = db.execute(
        select(TaxOrganizer).where(
            TaxOrganizer.firm_id == firm_id,
            TaxOrganizer.client_id == client_id,
        )
    ).scalars().all()
    organizer = PortalPreviewOrganizerSummary(
        organizer_count=len(organizer_rows),
        sent_count=sum(1 for o in organizer_rows if o.status == "sent"),
        in_progress_count=sum(1 for o in organizer_rows if o.status == "in_progress"),
        submitted_count=sum(1 for o in organizer_rows if o.status == "submitted"),
    )

    # 9. Assemble and return
    return PortalPreviewOut(
        client_id=client.id,
        client_name=client.name,
        document_requests=document_requests,
        documents=documents,
        invoices=invoices,
        messages=messages,
        notifications=notifications,
        billing=billing,
        organizer=organizer,
        generated_at=datetime.now(timezone.utc),
    )
