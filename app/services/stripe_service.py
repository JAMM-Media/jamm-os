# app/services/stripe_service.py

from uuid import UUID

import stripe
from fastapi import HTTPException

from app.core.config import get_settings


def _get_stripe():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured")
    stripe.api_key = settings.stripe_secret_key
    return stripe


def get_connect_url(firm_id: UUID, state: str) -> str:
    settings = get_settings()
    if not settings.stripe_connect_client_id or settings.stripe_connect_client_id == "ca_placeholder":
        raise HTTPException(status_code=503, detail="Stripe Connect is not configured")
    return (
        "https://connect.stripe.com/oauth/authorize"
        "?response_type=code"
        f"&client_id={settings.stripe_connect_client_id}"
        "&scope=read_write"
        f"&state={state}"
        "&redirect_uri=https://app.jammos.com/stripe/callback"
    )


def exchange_connect_code(code: str) -> dict:
    _get_stripe()
    try:
        response = stripe.OAuth.token(
            grant_type="authorization_code",
            code=code,
        )
        return {
            "stripe_account_id": response.stripe_user_id,
            "stripe_publishable_key": response.stripe_publishable_key,
        }
    except stripe.oauth_error.OAuthError as e:
        raise HTTPException(status_code=400, detail=str(e))


def get_account_details(stripe_account_id: str) -> dict:
    _get_stripe()
    try:
        account = stripe.Account.retrieve(stripe_account_id)
        return {
            "charges_enabled": account.charges_enabled,
            "payouts_enabled": account.payouts_enabled,
            "details_submitted": account.details_submitted,
            "country": account.country,
            "default_currency": account.default_currency,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def disconnect_account(stripe_account_id: str) -> bool:
    _get_stripe()
    settings = get_settings()
    try:
        stripe.OAuth.deauthorize(
            client_id=settings.stripe_connect_client_id,
            stripe_user_id=stripe_account_id,
        )
        return True
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def create_payment_intent(
    amount_cents: int,
    currency: str,
    stripe_account_id: str,
    invoice_id: str,
    idempotency_key: str,
) -> dict:
    _get_stripe()
    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency.lower(),
            metadata={"invoice_id": str(invoice_id)},
            stripe_account=stripe_account_id,
            idempotency_key=idempotency_key,
        )
        return {
            "payment_intent_id": intent.id,
            "client_secret": intent.client_secret,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def retrieve_payment_intent(
    payment_intent_id: str,
    stripe_account_id: str,
) -> dict:
    _get_stripe()
    try:
        intent = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            stripe_account=stripe_account_id,
        )
        return {
            "payment_intent_id": intent.id,
            "amount": intent.amount,
            "currency": intent.currency,
            "status": intent.status,
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


def construct_webhook_event(
    payload: bytes,
    sig_header: str,
    webhook_secret: str,
) -> object:
    _get_stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook payload")
