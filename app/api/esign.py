# app/api/esign.py

import io
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import document as crud_document
from app.crud import signature_envelope as crud_envelope
from app.crud import engagement_letter_template as crud_template
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.signature_envelope import SignatureEnvelope
from app.models.user import User
from app.schemas.pagination import PaginatedResponse
from app.schemas.engagement_letter_template import (
    EngagementLetterTemplateCreate,
    EngagementLetterTemplateOut,
    EngagementLetterTemplateUpdate,
)
from app.schemas.signature_envelope import (
    SignatureEnvelopeCreate,
    SignatureEnvelopeOut,
    SignatureEnvelopeUpdate,
)
from app.core.config import get_settings as _get_settings
from app.services import dropbox_sign
from app.services import letter_renderer
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/esign", tags=["E-Signatures"])

# Maps Dropbox Sign event_type strings to our internal envelope status values.
EVENT_STATUS_MAP: dict[str, str] = {
    "signature_request_signed": "signed",
    "signature_request_declined": "declined",
    "signature_request_canceled": "voided",
    "signature_request_expired": "expired",
    "signature_request_viewed": "viewed",
}


class PrepareLetterBody(BaseModel):
    template_id: UUID
    engagement_id: UUID
    fee_amount: str = ""
    extra_context: dict = {}


# -----------------------------------------------------------------------
# 1. POST /esign/envelopes — Create a new signature envelope
# -----------------------------------------------------------------------
@router.post(
    "/envelopes",
    response_model=SignatureEnvelopeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_envelope(
    payload: SignatureEnvelopeCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    client = db.execute(
        select(Client).where(
            Client.id == payload.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    if payload.engagement_id is not None:
        engagement = db.execute(
            select(Engagement).where(
                Engagement.id == payload.engagement_id,
                Engagement.firm_id == current_firm.id,
            )
        ).scalars().first()
        if not engagement:
            raise HTTPException(status_code=404, detail="Engagement not found")

    return crud_envelope.create_signature_envelope(db, payload, firm_id=current_firm.id)


# -----------------------------------------------------------------------
# 2. GET /esign/envelopes — List envelopes with optional filters
# -----------------------------------------------------------------------
@router.get("/envelopes", response_model=PaginatedResponse[SignatureEnvelopeOut])
def list_envelopes(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
    client_id: Optional[UUID] = None,
    engagement_id: Optional[UUID] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items = crud_envelope.list_signature_envelopes(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    total_items = crud_envelope.list_signature_envelopes(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        engagement_id=engagement_id,
        status=status,
        skip=0,
        limit=10_000,
    )
    return PaginatedResponse(total=len(total_items), limit=limit, offset=skip, items=items)


# -----------------------------------------------------------------------
# 3. GET /esign/envelopes/{envelope_id} — Fetch a single envelope
# -----------------------------------------------------------------------
@router.get("/envelopes/{envelope_id}", response_model=SignatureEnvelopeOut)
def get_envelope(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    return envelope


# -----------------------------------------------------------------------
# PATCH /esign/envelopes/{envelope_id} — Update envelope fields
# -----------------------------------------------------------------------
@router.patch("/envelopes/{envelope_id}", response_model=SignatureEnvelopeOut)
def update_envelope(
    envelope_id: UUID,
    payload: SignatureEnvelopeUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    return crud_envelope.update_signature_envelope(db, envelope, payload)


# -----------------------------------------------------------------------
# DELETE /esign/envelopes/{envelope_id} — Hard delete
# -----------------------------------------------------------------------
@router.delete("/envelopes/{envelope_id}")
def delete_envelope(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    crud_envelope.delete_signature_envelope(db, envelope)
    return {"deleted": True}


# -----------------------------------------------------------------------
# 4. POST /esign/envelopes/{envelope_id}/send — Send to Dropbox Sign
# -----------------------------------------------------------------------
@router.post("/envelopes/{envelope_id}/send", response_model=SignatureEnvelopeOut)
def send_envelope(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    if envelope.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft envelopes can be sent")
    if not envelope.signers or len(envelope.signers) == 0:
        raise HTTPException(status_code=400, detail="Envelope has no signers")
    if envelope.document_id is None:
        raise HTTPException(status_code=400, detail="Envelope has no document to sign")

    document = crud_document.get_document(db, envelope.document_id, current_firm.id)
    if not document:
        raise HTTPException(status_code=404, detail="Source document not found")

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
        firm_id=current_firm.id,
        action="esign.sent",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope_id,
    )
    return updated


# -----------------------------------------------------------------------
# POST /esign/envelopes/{envelope_id}/remind — Send a reminder
# -----------------------------------------------------------------------
@router.post("/envelopes/{envelope_id}/remind")
def send_envelope_reminder(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    if not _get_settings().DROPBOX_SIGN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Dropbox Sign is not configured. Set DROPBOX_SIGN_API_KEY in the environment."
        )
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    if envelope.status != "sent":
        raise HTTPException(status_code=400, detail="Reminders can only be sent for envelopes with status 'sent'")
    if not envelope.provider_envelope_id:
        raise HTTPException(status_code=400, detail="Envelope has no provider ID")

    dropbox_sign.send_reminder(
        signature_request_id=envelope.provider_envelope_id,
        signer_email=envelope.signers[0]["email"] if envelope.signers else None,
    )

    now = datetime.now(timezone.utc)
    crud_envelope.update_signature_envelope(
        db,
        envelope,
        SignatureEnvelopeUpdate(
            reminder_count=(envelope.reminder_count or 0) + 1,
            last_reminder_sent_at=now,
        ),
    )

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="esign.reminder_sent",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope_id,
    )

    return {"sent": True, "reminder_count": (envelope.reminder_count or 0) + 1}


# -----------------------------------------------------------------------
# 5. POST /esign/webhook — Dropbox Sign event callback (no auth)
# -----------------------------------------------------------------------
@router.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    signature_header = request.headers.get("Hash")
    if not signature_header:
        raise HTTPException(status_code=400, detail="Missing webhook signature")

    payload_bytes = await request.body()

    if not dropbox_sign.validate_webhook_signature(payload_bytes, signature_header):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    data = json.loads(payload_bytes)
    event_type = data["event"]["event_type"]
    signature_request_id = data["signature_request"]["signature_request_id"]

    # Silently ack if our record doesn't exist yet (edge case: webhook races our DB write).
    envelope = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.provider_envelope_id == signature_request_id
        )
    ).scalars().first()
    if envelope is None:
        return {"status": "ok"}

    new_status = EVENT_STATUS_MAP.get(event_type)
    if new_status:
        update_kwargs: dict = {"status": new_status}
        if new_status == "signed":
            update_kwargs["completed_at"] = datetime.now(timezone.utc)

        crud_envelope.update_signature_envelope(
            db, envelope, SignatureEnvelopeUpdate(**update_kwargs)
        )

        if new_status == "signed":
            pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
            background_tasks.add_task(store_signed_document, db, envelope, pdf_bytes)
            write_audit_log(
                db=db,
                firm_id=envelope.firm_id,
                action="esign.signed",
                actor_type="system",
                entity_type="signature_envelope",
                entity_id=envelope.id,
            )

    # Dropbox Sign retries unless it receives exactly {"status": "ok"}.
    return {"status": "ok"}


# -----------------------------------------------------------------------
# 6. POST /esign/prepare — Render a letter template and create envelope
# -----------------------------------------------------------------------
@router.post(
    "/prepare",
    response_model=SignatureEnvelopeOut,
    status_code=status.HTTP_201_CREATED,
)
def prepare_letter(
    payload: PrepareLetterBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_staff_or_above),
):
    template = crud_template.get_template(db, payload.template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == payload.engagement_id,
            Engagement.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    client = db.execute(
        select(Client).where(
            Client.id == engagement.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    context: dict = {
        "client_name": getattr(client, "full_name", None) or client.name,
        "client_email": client.email or "",
        "firm_name": current_firm.name,
        "firm_owner_name": current_user.full_name or current_user.email,
        "engagement_name": engagement.name,
        "engagement_type": getattr(engagement, "engagement_type", None) or "",
        "engagement_date": date.today().strftime("%B %d, %Y"),
        "due_date": "",
        "fee_amount": "",
    }
    if payload.fee_amount:
        context["fee_amount"] = payload.fee_amount
    if payload.extra_context:
        context.update(payload.extra_context)

    # Get due date from engagement filing deadline or end date
    filing_deadline = getattr(engagement, "filing_deadline", None)
    end_date = getattr(engagement, "end_date", None)
    raw_date = filing_deadline or end_date
    if raw_date:
        try:
            from datetime import datetime as dt
            if hasattr(raw_date, 'strftime'):
                context["due_date"] = raw_date.strftime("%B %d, %Y")
            else:
                context["due_date"] = str(raw_date)
        except Exception:
            context["due_date"] = str(raw_date)

    missing = letter_renderer.validate_context(template.variable_fields, context)
    if missing:
        raise HTTPException(status_code=422, detail={"missing_fields": missing})

    pdf_bytes = letter_renderer.render_to_pdf(template.body_html, context)

    s3_key = (
        f"{current_firm.id}/letters/{payload.engagement_id}"
        f"/{template.name}_{date.today()}.pdf"
    )
    s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

    doc = crud_document.create_document(
        db=db,
        firm_id=current_firm.id,
        client_id=client.id,
        engagement_id=payload.engagement_id,
        uploaded_by=current_user.id,
        filename=f"{template.name}.pdf",
        s3_key=s3_key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )

    envelope_schema = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=payload.engagement_id,
        document_id=doc.id,
        subject=template.name,
        signers=[{
            "name": getattr(client, "full_name", None) or client.name,
            "email": client.email or "",
            "status": "pending",
            "signed_at": None,
        }],
    )
    return crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=current_firm.id)


# -----------------------------------------------------------------------
# Engagement Letter Template CRUD routes
# -----------------------------------------------------------------------

@router.post(
    "/templates",
    response_model=EngagementLetterTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
def create_letter_template(
    payload: EngagementLetterTemplateCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    return crud_template.create_template(db, payload, firm_id=current_firm.id)


@router.get("/templates", response_model=PaginatedResponse[EngagementLetterTemplateOut])
def list_letter_templates(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
    engagement_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    items = crud_template.list_templates(
        db,
        firm_id=current_firm.id,
        engagement_type=engagement_type,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    total_items = crud_template.list_templates(
        db,
        firm_id=current_firm.id,
        engagement_type=engagement_type,
        is_active=is_active,
        skip=0,
        limit=10_000,
    )
    return PaginatedResponse(total=len(total_items), limit=limit, offset=skip, items=items)


@router.get("/templates/{template_id}", response_model=EngagementLetterTemplateOut)
def get_letter_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    template = crud_template.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.patch("/templates/{template_id}", response_model=EngagementLetterTemplateOut)
def update_letter_template(
    template_id: UUID,
    payload: EngagementLetterTemplateUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    template = crud_template.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return crud_template.update_template(db, template, payload)


@router.delete("/templates/{template_id}")
def delete_letter_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    template = crud_template.get_template(db, template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    crud_template.delete_template(db, template)
    return {"deleted": True}


# -----------------------------------------------------------------------
# Background task — store the completed signed PDF after webhook confirms
# -----------------------------------------------------------------------
async def store_signed_document(
    db: Session,
    envelope: SignatureEnvelope,
    pdf_bytes: bytes,
) -> None:
    engagement_segment = (
        str(envelope.engagement_id) if envelope.engagement_id else "no_engagement"
    )
    s3_key = (
        f"{envelope.firm_id}/signed/{envelope.client_id}"
        f"/{engagement_segment}/{envelope.provider_envelope_id}.pdf"
    )

    s3_service.upload_fileobj(io.BytesIO(pdf_bytes), s3_key, "application/pdf")

    doc = crud_document.create_document(
        db=db,
        firm_id=envelope.firm_id,
        client_id=envelope.client_id,
        engagement_id=envelope.engagement_id,
        uploaded_by=None,
        filename=f"{envelope.provider_envelope_id}.pdf",
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
