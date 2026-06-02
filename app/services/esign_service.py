# app/services/esign_service.py

import io
import uuid as _uuid
from datetime import date, datetime, timezone

import requests
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.crud import document as crud_document
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

    context: dict = {
        "client_name": getattr(client, "full_name", None) or client.name,
        "client_email": client.email or "",
        "firm_name": firm.name,
        "firm_owner_name": current_user.full_name or current_user.email,
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

    pdf_bytes = letter_renderer.render_to_pdf(template.body_html, context)

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

    return updated
