# app/api/payments.py

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above
from app.models.user import User
from app.models.invoice import Invoice
from app.models.stripe_connection import StripeConnection
from app.core.config import get_settings
from app.core.enums import InvoiceStatus, TriggerEvent
from app.crud import invoice as crud_invoice
from app.crud import stripe_connection as crud_stripe
from app.services import stripe_service
from app.services.event_bus import emit_event

router = APIRouter()


# ---------------------------------------------------------
# POST /payments/create-intent/{invoice_id}
# ---------------------------------------------------------
@router.post("/create-intent/{invoice_id}")
async def create_payment_intent(
    invoice_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=current_user.firm_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.status != InvoiceStatus.sent:
        raise HTTPException(
            status_code=400,
            detail="Invoice must be in sent status to accept payment",
        )

    if invoice.stripe_payment_intent_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Payment intent already exists for this invoice",
        )

    connection = crud_stripe.get_connection_by_firm(db, firm_id=current_user.firm_id)
    if connection is None:
        raise HTTPException(status_code=400, detail="No Stripe account connected")
    if not connection.charges_enabled:
        raise HTTPException(status_code=400, detail="Stripe account cannot accept charges yet")

    amount_cents = int(invoice.total_amount * 100)
    idempotency_key = f"invoice-{invoice_id}-payment-intent"

    result = stripe_service.create_payment_intent(
        amount_cents=amount_cents,
        currency=connection.default_currency or "usd",
        stripe_account_id=connection.stripe_account_id,
        invoice_id=str(invoice_id),
        idempotency_key=idempotency_key,
    )

    crud_invoice.set_payment_intent(db, invoice, result["payment_intent_id"])
    await emit_event(
        event=TriggerEvent.invoice_sent,
        payload={
            "firm_id": str(invoice.firm_id),
            "invoice_id": str(invoice.id),
            "client_id": str(invoice.client_id),
        },
        background_tasks=background_tasks,
    )
    return result


# ---------------------------------------------------------
# POST /payments/webhook — Stripe HMAC-validated webhook
# ---------------------------------------------------------
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook secret not configured")

    event = stripe_service.construct_webhook_event(
        payload, sig_header, settings.stripe_webhook_secret
    )

    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        invoice_id = event_data.get("metadata", {}).get("invoice_id")
        if invoice_id is None:
            return {"status": "ok"}

        stmt = select(Invoice).where(
            Invoice.id == UUID(invoice_id),
            Invoice.is_deleted == False,
        )
        invoice = db.execute(stmt).scalar_one_or_none()
        if not invoice:
            return {"status": "ok"}

        stripe_charge_id = event_data.get("latest_charge", None)
        crud_invoice.mark_invoice_paid(db, invoice, stripe_charge_id)
        from app.services.invoice_service import mark_invoice_paid
        mark_invoice_paid(db=db, invoice=invoice, firm_id=invoice.firm_id)
        await emit_event(
            event=TriggerEvent.invoice_paid,
            payload={
                "firm_id": str(invoice.firm_id),
                "invoice_id": str(invoice.id),
                "client_id": str(invoice.client_id),
                "engagement_id": str(invoice.engagement_id) if invoice.engagement_id else None,
                "amount": str(invoice.total_amount),
            },
            background_tasks=background_tasks,
        )

    elif event_type == "payment_intent.payment_failed":
        invoice_id = event_data.get("metadata", {}).get("invoice_id")  # noqa: F841
        # TODO: emit invoice.payment_failed — Phase 8

    elif event_type == "account.updated":
        stripe_account_id = event_data["id"]
        stmt = select(StripeConnection).where(
            StripeConnection.stripe_account_id == stripe_account_id
        )
        connection = db.execute(stmt).scalar_one_or_none()
        if connection:
            crud_stripe.update_connection_status(
                db,
                connection,
                charges_enabled=event_data["charges_enabled"],
                payouts_enabled=event_data["payouts_enabled"],
                details_submitted=event_data["details_submitted"],
            )

    return {"status": "ok"}


# ---------------------------------------------------------
# GET /payments/intent/{invoice_id}
# ---------------------------------------------------------
@router.get("/intent/{invoice_id}")
def get_payment_intent(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    invoice = crud_invoice.get_invoice(db, invoice_id, firm_id=current_user.firm_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if invoice.stripe_payment_intent_id is None:
        raise HTTPException(status_code=404, detail="No payment intent found for this invoice")

    connection = crud_stripe.get_connection_by_firm(db, firm_id=current_user.firm_id)
    if connection is None:
        raise HTTPException(status_code=400, detail="No Stripe account connected")

    return stripe_service.retrieve_payment_intent(
        invoice.stripe_payment_intent_id,
        connection.stripe_account_id,
    )
