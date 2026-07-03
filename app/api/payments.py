# app/api/payments.py

from decimal import Decimal
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

        amount_received_cents = event_data.get("amount_received", event_data.get("amount"))
        payment_amount = (
            Decimal(amount_received_cents) / 100
            if amount_received_cents is not None
            else invoice.total_amount
        )
        existing_paid = Decimal(str(invoice.amount_paid)) if invoice.amount_paid else Decimal("0")
        cumulative_paid = existing_paid + payment_amount

        if cumulative_paid < invoice.total_amount:
            remaining_balance = invoice.total_amount - cumulative_paid
            crud_invoice.mark_invoice_partial_payment(db, invoice, amount_paid=cumulative_paid)
            from app.services.invoice_service import mark_invoice_partial_payment
            mark_invoice_partial_payment(
                db=db,
                invoice=invoice,
                firm_id=invoice.firm_id,
                amount_paid=float(cumulative_paid),
                remaining_balance=float(remaining_balance),
            )
        else:
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
        invoice_id = event_data.get("metadata", {}).get("invoice_id")
        if invoice_id is not None:
            stmt = select(Invoice).where(
                Invoice.id == UUID(invoice_id),
                Invoice.is_deleted == False,
            )
            invoice = db.execute(stmt).scalar_one_or_none()
            if invoice:
                last_error = event_data.get("last_payment_error") or {}
                from app.services.invoice_service import mark_invoice_payment_failed
                mark_invoice_payment_failed(
                    db=db,
                    invoice=invoice,
                    firm_id=invoice.firm_id,
                    failure_code=last_error.get("code"),
                    failure_message=last_error.get("message"),
                )

    elif event_type == "charge.refunded":
        invoice_id = event_data.get("metadata", {}).get("invoice_id")
        if invoice_id is not None:
            stmt = select(Invoice).where(
                Invoice.id == UUID(invoice_id),
                Invoice.is_deleted == False,
            )
            invoice = db.execute(stmt).scalar_one_or_none()
            if invoice:
                amount_refunded_cents = event_data.get("amount_refunded")
                amount_refunded = (
                    Decimal(amount_refunded_cents) / 100
                    if amount_refunded_cents is not None
                    else Decimal("0")
                )
                refunds_data = (event_data.get("refunds") or {}).get("data") or []
                reason = refunds_data[0].get("reason") if refunds_data else None

                crud_invoice.mark_invoice_refunded(
                    db, invoice, amount_refunded=amount_refunded, reason=reason
                )
                from app.services.invoice_service import mark_invoice_refunded
                mark_invoice_refunded(
                    db=db,
                    invoice=invoice,
                    firm_id=invoice.firm_id,
                    amount_refunded=float(amount_refunded),
                    reason=reason,
                )

    elif event_type == "account.updated":
        stripe_account_id = event_data["id"]
        stmt = select(StripeConnection).where(
            StripeConnection.stripe_account_id == stripe_account_id
        )
        connection = db.execute(stmt).scalar_one_or_none()
        if connection:
            prior_charges_enabled = connection.charges_enabled
            prior_payouts_enabled = connection.payouts_enabled
            prior_details_submitted = connection.details_submitted

            new_charges_enabled = event_data["charges_enabled"]
            new_payouts_enabled = event_data["payouts_enabled"]
            new_details_submitted = event_data["details_submitted"]

            crud_stripe.update_connection_status(
                db,
                connection,
                charges_enabled=new_charges_enabled,
                payouts_enabled=new_payouts_enabled,
                details_submitted=new_details_submitted,
            )

            changed = []
            if prior_charges_enabled != new_charges_enabled:
                changed.append("charges_enabled")
            if prior_payouts_enabled != new_payouts_enabled:
                changed.append("payouts_enabled")
            if prior_details_submitted != new_details_submitted:
                changed.append("details_submitted")

            stripe_service.log_account_status_changed(
                firm_id=connection.firm_id,
                charges_enabled=new_charges_enabled,
                payouts_enabled=new_payouts_enabled,
                details_submitted=new_details_submitted,
                changed=changed,
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
