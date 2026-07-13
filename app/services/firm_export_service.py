# app/services/firm_export_service.py

import csv
import io
import zipfile
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.irs_authorization import IrsAuthorization
from app.models.note import Note
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.services import behavioral_log
from app.services.audit_service import write_audit_log


def _fmt(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _write_csv(writer: "csv.DictWriter", rows: list[dict]) -> None:
    for row in rows:
        writer.writerow({k: _fmt(v) for k, v in row.items()})


def generate_firm_export_zip(firm_id: UUID, db: Session) -> bytes:
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:

        # --- clients.csv ---
        clients = db.execute(
            select(Client).where(Client.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "name", "email", "phone", "company_name", "entity_type",
                "address_line1", "address_line2", "city", "state", "postal_code",
                "country", "tags", "notes", "is_active", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": c.id, "name": c.name, "email": c.email,
                    "phone": c.phone, "company_name": c.company_name,
                    "entity_type": c.entity_type, "address_line1": c.address_line1,
                    "address_line2": c.address_line2, "city": c.city,
                    "state": c.state, "postal_code": c.postal_code,
                    "country": c.country, "tags": c.tags, "notes": c.notes,
                    "is_active": c.is_active, "created_at": c.created_at,
                }
                for c in clients
            ])
            zf.writestr("clients.csv", f.getvalue())

        # --- engagements.csv ---
        engagements = db.execute(
            select(Engagement).where(Engagement.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "client_id", "name", "description", "status",
                "engagement_type", "start_date", "end_date",
                "filing_deadline", "extended_deadline",
                "efiled_at", "irs_confirmation_number",
                "notes", "is_active", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": e.id, "client_id": e.client_id, "name": e.name,
                    "description": e.description, "status": e.status,
                    "engagement_type": e.engagement_type,
                    "start_date": e.start_date, "end_date": e.end_date,
                    "filing_deadline": e.filing_deadline,
                    "extended_deadline": e.extended_deadline,
                    "efiled_at": e.efiled_at,
                    "irs_confirmation_number": e.irs_confirmation_number,
                    "notes": e.notes, "is_active": e.is_active,
                    "created_at": e.created_at,
                }
                for e in engagements
            ])
            zf.writestr("engagements.csv", f.getvalue())

        # --- invoices.csv ---
        invoices = db.execute(
            select(Invoice).where(Invoice.firm_id == firm_id, Invoice.is_deleted == False)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "client_id", "engagement_id", "invoice_number",
                "subtotal", "tax_rate", "tax_amount", "total_amount",
                "status", "due_date", "paid_at", "sent_at", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": inv.id, "client_id": inv.client_id,
                    "engagement_id": inv.engagement_id,
                    "invoice_number": inv.invoice_number,
                    "subtotal": inv.subtotal, "tax_rate": inv.tax_rate,
                    "tax_amount": inv.tax_amount, "total_amount": inv.total_amount,
                    "status": inv.status, "due_date": inv.due_date,
                    "paid_at": inv.paid_at, "sent_at": inv.sent_at,
                    "created_at": inv.created_at,
                }
                for inv in invoices
            ])
            zf.writestr("invoices.csv", f.getvalue())

        # --- tasks.csv ---
        tasks = db.execute(
            select(Task).where(Task.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "client_id", "engagement_id", "title", "description",
                "status", "assigned_to", "due_date", "completed_at", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": t.id, "client_id": t.client_id,
                    "engagement_id": t.engagement_id, "title": t.title,
                    "description": t.notes, "status": t.status,
                    "assigned_to": t.assigned_to, "due_date": t.due_date,
                    "completed_at": None, "created_at": t.created_at,
                }
                for t in tasks
            ])
            zf.writestr("tasks.csv", f.getvalue())

        # --- irs_authorizations.csv ---
        irs_auths = db.execute(
            select(IrsAuthorization).where(IrsAuthorization.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "client_id", "form_type", "status",
                "expiry_date", "granted_at", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": a.id, "client_id": a.client_id,
                    "form_type": a.form_type, "status": a.status,
                    "expiry_date": a.valid_until, "granted_at": None,
                    "created_at": a.created_at,
                }
                for a in irs_auths
            ])
            zf.writestr("irs_authorizations.csv", f.getvalue())

        # --- notes.csv ---
        notes = db.execute(
            select(Note).where(Note.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "entity_type", "entity_id", "author_id",
                "content", "is_private", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": n.id, "entity_type": n.entity_type,
                    "entity_id": n.entity_id, "author_id": n.author_id,
                    "content": n.body, "is_private": n.is_private,
                    "created_at": n.created_at,
                }
                for n in notes
            ])
            zf.writestr("notes.csv", f.getvalue())

        # --- time_entries.csv ---
        time_entries = db.execute(
            select(TimeEntry).where(TimeEntry.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "engagement_id", "client_id", "user_id",
                "date", "hours", "hourly_rate", "is_billable",
                "is_billed", "description", "activity_type", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": te.id, "engagement_id": te.engagement_id,
                    "client_id": None, "user_id": te.user_id,
                    "date": te.date, "hours": te.hours,
                    "hourly_rate": te.hourly_rate, "is_billable": te.is_billable,
                    "is_billed": te.is_billed, "description": te.description,
                    "activity_type": te.activity_type, "created_at": te.created_at,
                }
                for te in time_entries
            ])
            zf.writestr("time_entries.csv", f.getvalue())

        # --- documents_manifest.csv ---
        documents = db.execute(
            select(Document).where(Document.firm_id == firm_id)
        ).scalars().all()
        with io.StringIO() as f:
            fieldnames = [
                "id", "client_id", "engagement_id", "filename",
                "file_type", "file_size", "uploaded_by",
                "is_superseded", "created_at",
            ]
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            _write_csv(w, [
                {
                    "id": d.id, "client_id": d.client_id,
                    "engagement_id": d.engagement_id, "filename": d.filename,
                    "file_type": d.content_type, "file_size": d.size_bytes,
                    "uploaded_by": d.uploaded_by, "is_superseded": d.is_superseded,
                    "created_at": d.created_at,
                }
                for d in documents
            ])
            zf.writestr("documents_manifest.csv", f.getvalue())

    return buf.getvalue()


def record_export(
    *,
    db: Session,
    firm_id: UUID,
    current_user_id: UUID,
) -> None:
    write_audit_log(
        db=db,
        firm_id=firm_id,
        actor_id=current_user_id,
        actor_type="user",
        action="firm.data_exported",
        entity_type="firm",
        entity_id=firm_id,
    )

    behavioral_log.log_event(
        event_type="firm.data_exported",
        firm_id=firm_id,
        actor_id=current_user_id,
        actor_type="user",
    )
