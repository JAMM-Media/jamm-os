# app/api/esign.py

import io
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, status, UploadFile
from fastapi.responses import StreamingResponse
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
from app.services.behavioral_log import log_event
from app.services import esign_service

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
    current_user: User = Depends(get_current_user),
):
    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")

    try:
        updated = esign_service.send_envelope_to_dropbox(
            db=db,
            firm=current_firm,
            envelope=envelope,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as _send_exc:
        import logging as _logging
        _logging.getLogger(__name__).error(
            "send_envelope_to_dropbox failed: %s", str(_send_exc), exc_info=True
        )
        raise
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

    if (envelope.reminder_count or 0) >= 2:
        raise HTTPException(
            status_code=400,
            detail="Maximum reminders sent. Use the escalation path for unresponsive clients."
        )
    if envelope.escalated_at is not None:
        raise HTTPException(status_code=400, detail="Envelope is already escalated")

    if (envelope.reminder_count or 0) == 1 and envelope.last_reminder_sent_at is not None:
        firm_settings = current_firm.settings or {}
        second_days = int(firm_settings.get('esign_second_reminder_days', 4))
        last = envelope.last_reminder_sent_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        days_since_last = (datetime.now(timezone.utc) - last).days
        if days_since_last < second_days:
            raise HTTPException(
                status_code=400,
                detail=f"Second reminder not available yet. Wait {second_days - days_since_last} more day(s)."
            )

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
# POST /esign/envelopes/{envelope_id}/create-followup-task
# -----------------------------------------------------------------------
class EsignFollowupTaskOut(BaseModel):
    task_id: UUID
    task_title: str


@router.post("/envelopes/{envelope_id}/create-followup-task", response_model=EsignFollowupTaskOut)
def create_followup_task(
    envelope_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    from datetime import timedelta as _timedelta
    from uuid import uuid4
    from app.models.task import Task

    envelope = crud_envelope.get_signature_envelope(db, envelope_id, current_firm.id)
    if not envelope:
        raise HTTPException(status_code=404, detail="Signature envelope not found")
    if envelope.status != "sent":
        raise HTTPException(status_code=400, detail="Envelope is not in sent status")
    if envelope.escalated_at is None:
        raise HTTPException(status_code=400, detail="Envelope has not been escalated")
    if envelope.followup_task_id is not None:
        raise HTTPException(status_code=400, detail="Follow-up task already exists for this envelope")
    if envelope.engagement_id is None:
        raise HTTPException(status_code=400, detail="Cannot create follow-up task: envelope has no linked engagement")

    now = datetime.now(timezone.utc)
    sent_at = envelope.sent_at
    if sent_at is not None and sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    days_since_sent = (now - sent_at).days if sent_at else 0

    task = Task(
        id=uuid4(),
        firm_id=current_firm.id,
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
        firm_id=current_firm.id,
        action="esign.followup_task_created",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope_id,
    )
    log_event(
        firm_id=current_firm.id,
        event_type="esign.followup_task_created",
        entity_type="signature_envelope",
        entity_id=envelope_id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "task_id": str(task.id),
            "client_id": str(envelope.client_id),
            "days_since_sent": days_since_sent,
        },
    )

    return EsignFollowupTaskOut(task_id=task.id, task_title=task.title)


# -----------------------------------------------------------------------
# 5. POST /esign/webhook — Dropbox Sign event callback (no auth)
# -----------------------------------------------------------------------
@router.post("/webhook")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    import logging as _logging
    import hashlib
    import hmac as _hmac

    # Dropbox Sign sends multipart/form-data with event JSON in a field called "json"
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        json_str = form.get("json")
        if not json_str:
            raise HTTPException(status_code=400, detail="Missing json field in form data")
        try:
            data = json.loads(json_str)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON in form data")
    else:
        # Fallback: try reading as raw JSON body
        payload_bytes = await request.body()
        try:
            data = json.loads(payload_bytes)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid request body")

    # DEBUG: write payload to file
    try:
        import json as _json
        with open("/tmp/webhook_debug.json", "w") as _f:
            _json.dump(data, _f, indent=2, default=str)
    except Exception:
        pass

    # Validate event_hash from within the payload
    event = data.get("event", {})
    event_hash = event.get("event_hash")

    if event_hash:
        # Validate: HMAC-SHA256 of (event_time + event_type) using API key as secret
        event_time = str(event.get("event_time", ""))
        event_type = str(event.get("event_type", ""))
        settings = _get_settings()
        secret = settings.DROPBOX_SIGN_API_KEY.encode()
        computed = _hmac.new(
            secret,
            (event_time + event_type).encode(),
            hashlib.sha256,
        ).hexdigest()
        if not _hmac.compare_digest(computed, event_hash):
            _logging.getLogger(__name__).warning(
                "Webhook signature mismatch: computed=%s received=%s",
                computed, event_hash
            )
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    event_type = event.get("event_type")
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "Webhook received: event_type=%s signature_request_id=%s",
        event_type,
        data.get("signature_request", {}).get("signature_request_id", "none"),
    )

    # Dropbox Sign requires responding with {"status": "ok"} for the test event
    if event_type == "callback_test":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Hello API Event Received")

    signature_request = data.get("signature_request", {})
    signature_request_id = signature_request.get("signature_request_id")

    if not signature_request_id:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Hello API Event Received")

    # Silently ack if our record doesn't exist yet
    envelope = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.provider_envelope_id == signature_request_id
        )
    ).scalars().first()
    if envelope is None:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("Hello API Event Received")

    _logging.getLogger(__name__).warning(
        "Webhook envelope lookup: provider_id=%s found=%s status=%s signed_doc_id=%s",
        signature_request_id,
        envelope is not None,
        envelope.status if envelope else "n/a",
        envelope.signed_document_id if envelope else "n/a",
    )

    if event_type == "signature_request_signed":
        # Skip if already processed — envelope already has a signed document
        if envelope.signed_document_id:
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse("Hello API Event Received")
        try:
            pdf_bytes = dropbox_sign.download_signed_document(signature_request_id)
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
                import logging as _log
                _log.getLogger(__name__).error(
                    "Failed to store signed document: %s", _hex, exc_info=True
                )
        except Exception as _exc:
            import logging as _log
            _log.getLogger(__name__).error(
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

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("Hello API Event Received")


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

    try:
        envelope = esign_service.prepare_and_create_envelope(
            db=db,
            firm=current_firm,
            engagement=engagement,
            template=template,
            current_user=current_user,
            fee_amount=payload.fee_amount,
            extra_context=payload.extra_context,
        )
    except esign_service.MissingContextFieldsError as exc:
        raise HTTPException(status_code=422, detail={"missing_fields": exc.missing})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return envelope


# -----------------------------------------------------------------------
# POST /esign/upload-and-prepare — Upload a PDF and create a draft envelope
# -----------------------------------------------------------------------
@router.post(
    "/upload-and-prepare",
    response_model=SignatureEnvelopeOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_and_prepare(
    engagement_id: uuid.UUID = Query(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: User = Depends(require_staff_or_above),
):
    """
    Accepts a PDF upload, stores it in S3, creates a document record,
    then creates a draft signature envelope linked to that document.
    The envelope has the client pre-populated as the signer.
    The caller then calls POST /esign/envelopes/{id}/send to send it.
    """
    # Validate file type
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Get the engagement and client
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == engagement_id,
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

    # Read file bytes and upload to S3
    import uuid as _uuid
    pdf_bytes = file.file.read()
    s3_key = (
        f"{current_firm.id}/letters/{engagement_id}"
        f"/{file.filename or 'engagement_letter'}_{date.today()}_{_uuid.uuid4().hex[:8]}.pdf"
    )
    s3_service.upload_fileobj(
        io.BytesIO(pdf_bytes),
        s3_key,
        file.content_type or "application/pdf",
    )

    # Create document record
    doc = crud_document.create_document(
        db=db,
        firm_id=current_firm.id,
        client_id=client.id,
        engagement_id=engagement_id,
        uploaded_by=current_user.id,
        filename=file.filename or "engagement_letter.pdf",
        s3_key=s3_key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )

    # Create draft envelope with client as signer
    envelope_schema = SignatureEnvelopeCreate(
        client_id=client.id,
        engagement_id=engagement_id,
        document_id=doc.id,
        subject=file.filename or "Engagement Letter",
        signers=[{
            "name": getattr(client, "full_name", None) or client.name,
            "email": client.email or "",
            "status": "pending",
            "signed_at": None,
        }],
    )
    envelope = crud_envelope.create_signature_envelope(db, envelope_schema, firm_id=current_firm.id)

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="esign.document_uploaded",
        actor_type="staff",
        entity_type="signature_envelope",
        entity_id=envelope.id,
    )
    log_event(
        firm_id=current_firm.id,
        event_type="engagement_letter.uploaded",
        entity_type="signature_envelope",
        entity_id=envelope.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={
            "client_id": str(client.id),
            "engagement_id": str(engagement_id),
            "filename": file.filename or "engagement_letter.pdf",
            "size_bytes": len(pdf_bytes),
        }
    )

    return envelope


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
    template = crud_template.create_template(db, payload, firm_id=current_firm.id)

    log_event(
        firm_id=current_firm.id,
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


@router.get("/templates/{template_id}/preview")
def preview_letter_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Render a letter template to PDF using sample placeholder values.
    Returns the PDF inline so browsers display it in a new tab.
    Auth: manager or above.
    """
    template = crud_template.get_template(db, template_id, current_firm.id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    sample_context = {
        "client_name": "Alex Johnson",
        "firm_name": current_firm.name,
        "firm_owner_name": current_user.full_name or "Your Name",
        "firm_address": (current_firm.settings or {}).get(
            "firm_address", "123 Main Street, Suite 100, Boston, MA 02101"),
        "firm_phone": (current_firm.settings or {}).get(
            "firm_phone", "(617) 555-0100"),
        "firm_contact_email": (current_firm.settings or {}).get(
            "firm_contact_email", "hello@yourfirm.com"),
        "firm_website": (current_firm.settings or {}).get(
            "firm_website", "https://www.yourfirm.com"),
        "engagement_name": "2024 Individual Tax Return",
        "engagement_type": "Individual Tax Return (1040)",
        "fee_amount": "$850",
        "engagement_date": datetime.now().strftime("%B %d, %Y"),
        "due_date": "April 15, 2025",
    }

    pdf_bytes = letter_renderer.render_to_pdf(
        template.body_html,
        sample_context,
        firm_settings=current_firm.settings or {},
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "inline; filename=preview.pdf"
        },
    )


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
    updated = crud_template.update_template(db, template, payload)

    log_event(
        firm_id=current_firm.id,
        event_type="letter_template.updated",
        entity_type="letter_template",
        entity_id=template_id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "engagement_type": payload.engagement_type,
        }
    )

    return updated


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
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("store_signed_document failed: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()
