# app/api/stripe_connect.py

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner, require_manager_or_above
from app.models.user import User
from app.schemas.stripe_connection import (
    StripeConnectURLOut,
    StripeConnectionOut,
    StripeConnectionStatusOut,
)
from app.crud import stripe_connection as crud_stripe
from app.services import stripe_service

router = APIRouter()


# ---------------------------------------------------------
# GET /connect — generate OAuth URL
# ---------------------------------------------------------
@router.get("/connect", response_model=StripeConnectURLOut)
def get_connect_url(
    current_user: User = Depends(require_firm_owner),
):
    state = secrets.token_urlsafe(32)
    url = stripe_service.get_connect_url(current_user.firm_id, state)
    return StripeConnectURLOut(url=url, state=state)


# ---------------------------------------------------------
# GET /callback — OAuth callback after Stripe redirect
# ---------------------------------------------------------
@router.get("/callback", response_model=StripeConnectionOut)
def stripe_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    token_data = stripe_service.exchange_connect_code(code)
    stripe_account_id = token_data["stripe_account_id"]
    stripe_publishable_key = token_data.get("stripe_publishable_key")

    account_details = stripe_service.get_account_details(stripe_account_id)

    existing = crud_stripe.get_connection_by_firm(db, firm_id=current_user.firm_id)
    if existing:
        raise HTTPException(status_code=400, detail="Stripe account already connected")

    connection = crud_stripe.create_connection(
        db,
        firm_id=current_user.firm_id,
        stripe_account_id=stripe_account_id,
        stripe_publishable_key=stripe_publishable_key,
        country=account_details.get("country"),
        default_currency=account_details.get("default_currency"),
        charges_enabled=account_details.get("charges_enabled", False),
        payouts_enabled=account_details.get("payouts_enabled", False),
        details_submitted=account_details.get("details_submitted", False),
    )
    return connection


# ---------------------------------------------------------
# GET /status — live connection status for this firm
# ---------------------------------------------------------
@router.get("/status", response_model=StripeConnectionStatusOut)
def get_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    connection = crud_stripe.get_connection_by_firm(db, firm_id=current_user.firm_id)
    if not connection:
        return StripeConnectionStatusOut(
            connected=False,
            charges_enabled=False,
            payouts_enabled=False,
            details_submitted=False,
            message="No Stripe account connected",
        )

    account_details = stripe_service.get_account_details(connection.stripe_account_id)
    crud_stripe.update_connection_status(
        db,
        connection,
        charges_enabled=account_details["charges_enabled"],
        payouts_enabled=account_details["payouts_enabled"],
        details_submitted=account_details["details_submitted"],
    )
    return StripeConnectionStatusOut(
        connected=True,
        charges_enabled=account_details["charges_enabled"],
        payouts_enabled=account_details["payouts_enabled"],
        details_submitted=account_details["details_submitted"],
        stripe_account_id=connection.stripe_account_id,
    )


# ---------------------------------------------------------
# POST /disconnect — deauthorize connected account
# ---------------------------------------------------------
@router.post("/disconnect")
def disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    connection = crud_stripe.get_connection_by_firm(db, firm_id=current_user.firm_id)
    if not connection:
        raise HTTPException(status_code=404, detail="No Stripe account connected")

    stripe_service.disconnect_account(connection.stripe_account_id)
    crud_stripe.disconnect_connection(db, connection)
    return {"message": "Stripe account disconnected"}
