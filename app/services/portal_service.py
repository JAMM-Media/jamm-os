# app/services/portal_service.py

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.crud import portal_session as crud_portal_session
from app.crud import tax_organizer as crud_organizer
from app.crud.invoice import set_payment_intent
from app.crud.stripe_connection import get_connection_by_firm
from app.core.enums import InvoiceStatus
from app.services import document_request_service as dr_service
from app.services import document_service
from app.services import stripe_service
from app.models.client import Client
from app.services.behavioral_log import build_changed_fields, log_event
from app.services.portal_auth import hash_portal_password_bcrypt, verify_portal_password

log = logging.getLogger(__name__)


def end_session(*, db: Session, session, client):
    try:
        duration_minutes = None
        if session:
            created = getattr(session, "created_at", None)
            last_active = getattr(session, "last_active_at", None)
            if created and last_active:
                duration_minutes = int((last_active - created).total_seconds() / 60)
        log_event(
            firm_id=client.firm_id,
            event_type="portal.session_ended",
            entity_type="client",
            entity_id=client.id,
            actor_type="client",
            actor_id=None,
            metadata={
                "session_duration_minutes": duration_minutes,
                "time_of_day": datetime.now(timezone.utc).hour,
            },
        )
    except Exception as _exc:
        log.warning("portal.session_ended log_event failed: %s", _exc)

    if session and not session.is_revoked:
        crud_portal_session.revoke_session(db, session, revoked_by="client")


def upload_document(*, db: Session, file: UploadFile, engagement_id, client, client_note=None):
    try:
        doc = document_service.upload_document(
            db=db,
            file=file,
            client_id=client.id,
            engagement_id=engagement_id,
            firm_id=client.firm_id,
            current_user_id=None,
            source="client",
            source_client_id=client.id,
            client_note=client_note,
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("portal upload_document failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload failed",
        )

    try:
        log_event(
            firm_id=client.firm_id,
            event_type="portal.document_uploaded",
            entity_type="document",
            entity_id=doc.id,
            actor_type="client",
            actor_id=None,
            metadata={
                "file_size": doc.size_bytes,
                "content_type": file.content_type,
                "engagement_id": str(engagement_id),
                "time_of_day": datetime.now(timezone.utc).hour,
                "associated_request": False,
            },
        )
    except Exception as _exc:
        log.warning("portal.document_uploaded log_event failed: %s", _exc)

    return doc


def complete_checklist_item(*, db: Session, doc_request, request_id, item_id, client):
    updated_request, error = dr_service.update_checklist_item_status(
        db=db,
        request_id=request_id,
        item_id=item_id,
        new_status="uploaded",
        firm_id=client.firm_id,
        current_user_id=client.id,
    )

    if error == "item_not_found":
        return None, error

    try:
        days_since_created = None
        if doc_request.created_at:
            days_since_created = (datetime.now(timezone.utc) - doc_request.created_at).days
        log_event(
            firm_id=client.firm_id,
            event_type="portal.todo_completed",
            entity_type="document_request",
            entity_id=request_id,
            actor_type="client",
            actor_id=None,
            metadata={
                "item_id": str(item_id),
                "time_of_day": datetime.now(timezone.utc).hour,
                "days_since_request_created": days_since_created,
            },
        )
    except Exception as _exc:
        log.warning("portal.todo_completed log_event failed: %s", _exc)

    return updated_request, None


def log_invoice_viewed(*, db: Session, invoice, client):
    log_event(
        firm_id=client.firm_id,
        event_type="portal.invoice_viewed",
        entity_type="invoice",
        entity_id=invoice.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "invoice_amount": float(invoice.total_amount) if hasattr(invoice, 'total_amount') else None,
            "invoice_status": str(invoice.status) if hasattr(invoice, 'status') else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at
                else None
            ),
        }
    )


def pay_invoice(*, db: Session, invoice, invoice_id, client):
    if invoice.status not in {InvoiceStatus.sent, InvoiceStatus.overdue}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invoice is not available for payment",
        )

    if invoice.stripe_payment_intent_id is not None:
        connection = get_connection_by_firm(db, client.firm_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment not available for this invoice",
            )
        return stripe_service.retrieve_payment_intent(
            invoice.stripe_payment_intent_id,
            connection.stripe_account_id,
        )

    connection = get_connection_by_firm(db, client.firm_id)
    if not connection or not connection.charges_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment not available for this invoice",
        )

    amount_cents = int(invoice.total_amount * 100)
    idempotency_key = f"portal-invoice-{invoice_id}-payment-intent"

    result = stripe_service.create_payment_intent(
        amount_cents=amount_cents,
        currency=connection.default_currency or "usd",
        stripe_account_id=connection.stripe_account_id,
        invoice_id=str(invoice_id),
        idempotency_key=idempotency_key,
    )
    set_payment_intent(db, invoice, result["payment_intent_id"])
    # Fires when the client starts a Stripe payment, at payment intent
    # creation, not when money arrives. The payment itself is invoice.paid,
    # written from the Stripe webhook. Renamed Sep 22, 2026: the old name
    # claimed a settlement this call site never observes, and Invoice Payment
    # Time now computes from invoice.paid alone.
    log_event(
        firm_id=client.firm_id,
        event_type="portal.payment_initiated",
        entity_type="invoice",
        entity_id=invoice_id,
        actor_type="client",
        actor_id=None,
        metadata={
            "payment_method": "stripe",
            "time_of_day": datetime.now(timezone.utc).hour,
        }
    )
    return result


def save_organizer(*, db: Session, organizer, payload, client):
    updated = crud_organizer.save_organizer_responses(
        db=db,
        organizer=organizer,
        responses=payload.responses,
        submit=payload.submit,
    )

    if payload.submit and updated.status == "submitted":
        log_event(
            firm_id=client.firm_id,
            event_type="portal.organizer_submitted",
            entity_type="tax_organizer",
            entity_id=updated.id,
            actor_type="client",
            actor_id=client.id,
            metadata={
                "tax_year": updated.tax_year,
                "engagement_id": str(updated.engagement_id) if updated.engagement_id else None,
            }
        )

    return updated


# ---------------------------------------------------------------------------
# Portal access and account writes moved out of app/api/portal.py (Phase 7).
# client.portal_access_changed and client.updated are reused here with the
# extra keys ruled Oct 12, 2026: via and sessions_revoked on the former,
# actor_type "client" on the latter. No password or hash reaches any event.
# ---------------------------------------------------------------------------

def revoke_client_access(*, db: Session, client, firm_id, current_user_id) -> int:
    """Staff revoke: every active session ends and portal access turns off.

    Fires on every call, even when access was already off, because sessions
    are revoked either way; from_enabled and to_enabled carry the truth."""
    old_enabled = client.portal_access_enabled
    count = crud_portal_session.revoke_all_client_sessions(db, client.id, firm_id)
    client.portal_access_enabled = False
    db.commit()

    log_event(
        firm_id=firm_id,
        event_type="client.portal_access_changed",
        entity_type="client",
        entity_id=client.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "from_enabled": old_enabled,
            "to_enabled": False,
            "via": "admin_revoke",
            "sessions_revoked": count,
        },
    )
    return count


def enable_access_for_staff_preview(*, db: Session, client, current_user_id) -> None:
    """Staff preview turns portal access on if it was off. Fires only when the
    flag actually flips."""
    if not client.portal_access_enabled:
        client.portal_access_enabled = True
        db.commit()

        log_event(
            firm_id=client.firm_id,
            event_type="client.portal_access_changed",
            entity_type="client",
            entity_id=client.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_enabled": False,
                "to_enabled": True,
                "via": "staff_preview",
            },
        )


def set_portal_password(
    *, db: Session, client, new_password: str, confirm_password: str, current_password
) -> None:
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    if new_password != confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords don't match.",
        )

    first_set = not client.portal_password_hash
    if client.portal_password_hash:
        if not current_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Current password is required to change your password.",
            )
        if not verify_portal_password(current_password, client.portal_password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

    client.portal_password_hash = hash_portal_password_bcrypt(new_password)
    db.commit()

    log_event(
        firm_id=client.firm_id,
        event_type="portal.password_changed",
        entity_type="client",
        entity_id=client.id,
        actor_type="client",
        actor_id=client.id,
        metadata={"first_set": first_set},
    )


def update_portal_profile(*, db: Session, client, name, email, phone) -> dict:
    old_values = {"name": client.name, "email": client.email, "phone": client.phone}

    if name is not None:
        n = name.strip()
        if not n:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Name cannot be blank.",
            )
        client.name = n

    if email is not None:
        e = email.strip()
        if "@" not in e or "." not in e.rsplit("@", 1)[-1]:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid email address.",
            )
        existing = db.query(Client).filter(
            Client.email == e,
            Client.id != client.id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email is already in use.",
            )
        client.email = e

    if phone is not None:
        client.phone = phone.strip() or None

    db.commit()

    new_values = {"name": client.name, "email": client.email, "phone": client.phone}
    changed_fields = build_changed_fields(old_values, new_values)
    if changed_fields:
        log_event(
            firm_id=client.firm_id,
            event_type="client.updated",
            entity_type="client",
            entity_id=client.id,
            actor_type="client",
            actor_id=client.id,
            metadata={"changed_fields": changed_fields},
        )

    return new_values


def revoke_own_session(*, db: Session, session, client) -> None:
    session_id = session.id
    crud_portal_session.revoke_session(db, session, revoked_by="client")

    log_event(
        firm_id=client.firm_id,
        event_type="portal.session_revoked",
        entity_type="portal_session",
        entity_id=session_id,
        actor_type="client",
        actor_id=client.id,
        metadata={"session_id": str(session_id)},
    )
