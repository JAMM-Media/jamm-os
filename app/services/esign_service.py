# app/services/esign_service.py

import io
import logging
import threading
import uuid
import uuid as _uuid
from datetime import date, datetime, timezone

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.crud import document as crud_document
from app.crud import engagement_letter_template as crud_template
from app.crud import signature_envelope as crud_envelope
from app.models.client import Client
from app.models.firm import Firm
from app.models.signature_envelope import SignatureEnvelope
from app.models.user import User
from app.schemas.signature_envelope import SignatureEnvelopeCreate, SignatureEnvelopeUpdate
from app.services import dropbox_sign
from app.services import letter_renderer
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.automation_dispatcher import dispatch
from app.core.enums import TriggerEvent

log = logging.getLogger(__name__)


class MissingContextFieldsError(Exception):
    def __init__(self, missing):
        self.missing = missing
        super().__init__(f"Missing template fields: {missing}")


def prepare_and_create_envelope(
    db: Session,
    firm: Firm,
    engagement,
    template,
    current_user: User,
    fee_amount: str = "",
    extra_context: dict = None,
) -> SignatureEnvelope:
    if extra_context is None:
        extra_context = {}

    client = db.execute(
        select(Client).where(
            Client.id == engagement.client_id,
            Client.firm_id == firm.id,
        )
    ).scalars().first()
    if not client:
        raise ValueError(f"Client not found for engagement {engagement.id}")

    firm_settings = firm.settings or {}
    context: dict = {
        "client_name": getattr(client, "full_name", None) or client.name,
        "client_email": client.email or "",
        "firm_name": firm.name,
        "firm_owner_name": current_user.full_name or current_user.email,
        "firm_address": firm_settings.get("firm_address", ""),
        "firm_phone": firm_settings.get("firm_phone", ""),
        "firm_contact_email": firm_settings.get("firm_contact_email", ""),
        "firm_website": firm_settings.get("firm_website", ""),
        "engagement_name": engagement.name,
        "engagement_type": getattr(engagement, "engagement_type", None) or "",
        "engagement_date": date.today().strftime("%B %d, %Y"),
        "due_date": "",
        "fee_amount": "",
    }
    if fee_amount:
        context["fee_amount"] = fee_amount
    if extra_context:
        context.update(extra_context)

    filing_deadline = getattr(engagement, "filing_deadline", None)
    end_date = getattr(engagement, "end_date", None)
    raw_date = filing_deadline or end_date
    if raw_date:
        try:
            from datetime import datetime as dt
            if hasattr(raw_date, "strftime"):
                context["due_date"] = raw_date.strftime("%B %d, %Y")
            else:
                context["due_date"] = str(raw_date)
        except Exception:
            context["due_date"] = str(raw_date)

    missing = letter_renderer.validate_context(template.variable_fields, context)
    if missing:
        raise MissingContextFieldsError(missing)

    pdf_bytes = letter_renderer.render_to_pdf(
        template.body_html,
        context,
        firm_settings=firm.settings or {},
    )

    s3_key = (
        f"{firm.id}/letters/{engagement.id}"
        f"/{template.name}_{date.today()}_{_uuid.uuid4().hex[:8]}.pdf"
    )
    s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

    doc = crud_document.create_document(
        db=db,
        firm_id=firm.id,
        client_id=client.id,
        engagement_id=engagement.id,
        uploaded_by=current_user.id,
        filename=f"{template.name}.pdf",
        s3_key=s3_key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )

    envelope_schema = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=engagement.id,
        document_id=doc.id,
        subject=template.name,
        signers=[{
            "name": getattr(client, "full_name", None) or client.name,
            "email": client.email or "",
            "status": "pending",
            "signed_at": None,
        }],
    )
    envelope = crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=firm.id)

    log_event(
        firm_id=firm.id,
        event_type="engagement_letter.prepared",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "client_id": str(client.id),
            "engagement_id": str(engagement.id),
            "template_id": str(template.id),
            "template_name": template.name,
            "template_engagement_type": template.engagement_type,
            "fee_amount": fee_amount or None,
            "engagement_type": getattr(engagement, "engagement_type", None),
        }
    )

    return envelope


def send_envelope_to_dropbox(
    db: Session,
    firm: Firm,
    envelope: SignatureEnvelope,
    current_user: User,
) -> SignatureEnvelope:
    if envelope.status != "draft":
        raise ValueError("Only draft envelopes can be sent")
    if not envelope.signers or len(envelope.signers) == 0:
        raise ValueError("Envelope has no signers")
    if envelope.document_id is None:
        raise ValueError("Envelope has no document to sign")

    document = crud_document.get_document(db, envelope.document_id, firm.id)
    if not document:
        raise ValueError("Source document not found")

    presigned_url = s3_service.generate_presigned_url(document.s3_key)
    pdf_bytes = requests.get(presigned_url, timeout=30).content

    signer = envelope.signers[0]
    response = dropbox_sign.send_envelope(
        client_name=signer["name"],
        client_email=signer["email"],
        subject=envelope.subject or "Please sign this document",
        message=envelope.message or "",
        pdf_bytes=pdf_bytes,
        expires_at=envelope.expires_at,
    )

    provider_envelope_id = response["signature_request"]["signature_request_id"]

    updated = crud_envelope.update_signature_envelope(
        db,
        envelope,
        SignatureEnvelopeUpdate(
            status="sent",
            provider_envelope_id=provider_envelope_id,
            sent_at=datetime.now(timezone.utc),
        ),
    )

    write_audit_log(
        db=db,
        firm_id=firm.id,
        action="esign.sent",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=firm.id,
        event_type="engagement_letter.sent",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="staff",
        actor_id=current_user.id if hasattr(current_user, "id") else None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "provider": envelope.provider,
        }
    )

    def _fire_esign_sent(firm_id, envelope_id, client_id, engagement_id):
        try:
            dispatch(
                event=TriggerEvent.esign_sent,
                payload={
                    "firm_id": str(firm_id),
                    "envelope_id": str(envelope_id),
                    "client_id": str(client_id),
                    "engagement_id": str(engagement_id) if engagement_id else None,
                },
            )
        except Exception:
            pass

    threading.Thread(
        target=_fire_esign_sent,
        args=(firm.id, envelope.id, envelope.client_id, envelope.engagement_id),
        daemon=True,
    ).start()

    return updated


def create_followup_task(
    *,
    db: Session,
    envelope: SignatureEnvelope,
    firm_id,
):
    from datetime import timedelta as _timedelta
    from uuid import uuid4
    from app.models.task import Task

    now = datetime.now(timezone.utc)
    sent_at = envelope.sent_at
    if sent_at is not None and sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    days_since_sent = (now - sent_at).days if sent_at else 0

    task = Task(
        id=uuid4(),
        firm_id=firm_id,
        client_id=envelope.client_id,
        engagement_id=envelope.engagement_id,
        title=f"Follow up with client - engagement letter unsigned ({days_since_sent} days)",
        notes=(
            f"Engagement letter '{envelope.subject or 'Untitled'}' was sent {days_since_sent} days ago "
            f"and has received {envelope.reminder_count} reminder(s) with no response. "
            f"Direct client contact required."
        ),
        status="todo",
        due_date=(now + _timedelta(days=3)).date(),
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.flush()

    crud_envelope.update_signature_envelope(
        db,
        envelope,
        SignatureEnvelopeUpdate(followup_task_id=task.id),
    )

    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="esign.followup_task_created",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=firm_id,
        event_type="esign.followup_task_created",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "task_id": str(task.id),
            "client_id": str(envelope.client_id),
            "days_since_sent": days_since_sent,
        },
    )

    return task


def upload_and_prepare_envelope(
    *,
    db: Session,
    firm_id,
    engagement_id,
    client: Client,
    current_user_id,
    pdf_bytes: bytes,
    filename,
    content_type,
):
    s3_key = (
        f"{firm_id}/letters/{engagement_id}"
        f"/{filename or 'engagement_letter'}_{date.today()}_{_uuid.uuid4().hex[:8]}.pdf"
    )
    s3_service.upload_fileobj(
        io.BytesIO(pdf_bytes),
        s3_key,
        content_type or "application/pdf",
    )

    doc = crud_document.create_document(
        db=db,
        firm_id=firm_id,
        client_id=client.id,
        engagement_id=engagement_id,
        uploaded_by=current_user_id,
        filename=filename or "engagement_letter.pdf",
        s3_key=s3_key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )

    envelope_schema = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=engagement_id,
        document_id=doc.id,
        subject=filename or "Engagement Letter",
        signers=[{
            "name": getattr(client, "full_name", None) or client.name,
            "email": client.email or "",
            "status": "pending",
            "signed_at": None,
        }],
    )
    envelope = crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=firm_id)

    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="esign.document_uploaded",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=firm_id,
        event_type="engagement_letter.uploaded",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "client_id": str(client.id),
            "engagement_id": str(engagement_id),
            "filename": filename or "engagement_letter.pdf",
            "size_bytes": len(pdf_bytes),
        }
    )

    return envelope


def create_letter_template(
    *,
    db: Session,
    payload,  # EngagementLetterTemplateCreate
    firm_id,
):
    template = crud_template.create_template(db, payload, firm_id=firm_id)

    log_event(
        firm_id=firm_id,
        event_type="letter_template.created",
        entity_type="letter_template",
        entity_id=template.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "engagement_type": payload.engagement_type,
            "variable_count": len(payload.variable_fields),
        }
    )

    return template


def update_letter_template(
    *,
    db: Session,
    template,
    payload,  # EngagementLetterTemplateUpdate
    firm_id,
):
    updated = crud_template.update_template(db, template, payload)

    log_event(
        firm_id=firm_id,
        event_type="letter_template.updated",
        entity_type="letter_template",
        entity_id=template.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "engagement_type": payload.engagement_type,
        }
    )

    return updated


def store_signed_document(
    envelope_id: str,
    firm_id: str,
    client_id: str,
    engagement_id,
    provider_envelope_id: str,
    pdf_bytes: bytes,
) -> None:
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        from app.models.signature_envelope import SignatureEnvelope as _SE
        envelope = db.query(_SE).filter(_SE.id == envelope_id).first()
        if not envelope:
            return

        engagement_segment = (
            str(engagement_id) if engagement_id else "no_engagement"
        )
        s3_key = (
            f"{firm_id}/signed/{client_id}"
            f"/{engagement_segment}/{provider_envelope_id}.pdf"
        )

        # Build a readable filename from the engagement name if available
        readable_name = "Engagement Letter"
        if engagement_id:
            from app.models.engagement import Engagement as _Eng
            eng = db.query(_Eng).filter(_Eng.id == engagement_id).first()
            if eng:
                import re
                safe_name = re.sub(r'[^\w\s\-]', '', eng.name).strip()
                readable_name = safe_name if safe_name else "Engagement Letter"

        filename = f"{readable_name} — Signed.pdf"

        s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

        doc = crud_document.create_document(
            db=db,
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(str(engagement_id)) if engagement_id else None,
            uploaded_by=None,
            filename=filename,
            s3_key=s3_key,
            content_type="application/pdf",
            size_bytes=len(pdf_bytes),
        )

        crud_envelope.update_signature_envelope(
            db,
            envelope,
            SignatureEnvelopeUpdate(
                signed_document_id=doc.id,
                status="signed",
            ),
        )
        db.commit()

        try:
            from app.services.irs_auth_service import activate_authorization_for_envelope
            activate_authorization_for_envelope(
                db=db,
                envelope_id=envelope.id,
                firm_id=uuid.UUID(firm_id) if isinstance(firm_id, str) else firm_id,
            )
        except Exception as _auth_exc:
            log.error(
                "IRS auth activation on signing failed: %s", _auth_exc, exc_info=True
            )
    except Exception as exc:
        log.error("store_signed_document failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


def process_webhook_signed(db: Session, envelope: SignatureEnvelope) -> None:
    if envelope.signed_document_id:
        return
    try:
        pdf_bytes = dropbox_sign.download_signed_document(envelope.provider_envelope_id)
        store_signed_document(
            str(envelope.id),
            str(envelope.firm_id),
            str(envelope.client_id),
            envelope.engagement_id,
            envelope.provider_envelope_id,
            pdf_bytes,
        )
    except HTTPException as _hex:
        if _hex.status_code == 409:
            # Already downloaded in a previous webhook attempt — treat as success
            pass
        else:
            log.error(
                "Failed to store signed document: %s", _hex, exc_info=True
            )
    except Exception as _exc:
        log.error(
            "Failed to store signed document: %s", _exc, exc_info=True
        )
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.signed",
        actor_type="client",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.signed",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_to_sign": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )


def process_webhook_viewed(db: Session, envelope: SignatureEnvelope) -> None:
    # SignatureEnvelope does not track a "first viewed" state, so this
    # fires on every viewed webhook, not just the first one.
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.viewed",
        actor_type="client",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.viewed",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )


def process_webhook_declined(db: Session, envelope: SignatureEnvelope) -> None:
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.declined",
        actor_type="client",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.declined",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )


def process_webhook_voided(db: Session, envelope: SignatureEnvelope) -> None:
    # The webhook payload carries no signer/staff identity for who
    # canceled, so this is recorded as a system action.
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.voided",
        actor_type="system",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.voided",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )


def process_webhook_expired(db: Session, envelope: SignatureEnvelope) -> None:
    write_audit_log(
        db=db,
        firm_id=envelope.firm_id,
        action="esign.expired",
        actor_type="system",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=envelope.firm_id,
        event_type="engagement_letter.expired",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="system",
        actor_id=None,
        metadata={
            "client_id": str(envelope.client_id),
            "engagement_id": str(envelope.engagement_id) if envelope.engagement_id else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - envelope.sent_at).days
                if hasattr(envelope, 'sent_at') and envelope.sent_at
                else None
            ),
        }
    )
