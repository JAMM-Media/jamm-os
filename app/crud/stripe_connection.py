# app/crud/stripe_connection.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stripe_connection import StripeConnection
from app.core.enums import StripeConnectionStatus


def get_connection_by_firm(db: Session, firm_id: uuid.UUID) -> Optional[StripeConnection]:
    stmt = select(StripeConnection).where(StripeConnection.firm_id == firm_id)
    return db.execute(stmt).scalar_one_or_none()


def create_connection(
    db: Session,
    firm_id: uuid.UUID,
    stripe_account_id: str,
    stripe_publishable_key: Optional[str],
    country: Optional[str],
    default_currency: Optional[str],
    charges_enabled: bool,
    payouts_enabled: bool,
    details_submitted: bool,
) -> StripeConnection:
    connection = StripeConnection(
        firm_id=firm_id,
        stripe_account_id=stripe_account_id,
        stripe_publishable_key=stripe_publishable_key,
        country=country,
        default_currency=default_currency,
        charges_enabled=charges_enabled,
        payouts_enabled=payouts_enabled,
        details_submitted=details_submitted,
        status=StripeConnectionStatus.connected,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)
    return connection


def update_connection_status(
    db: Session,
    connection: StripeConnection,
    charges_enabled: bool,
    payouts_enabled: bool,
    details_submitted: bool,
) -> StripeConnection:
    connection.charges_enabled = charges_enabled
    connection.payouts_enabled = payouts_enabled
    connection.details_submitted = details_submitted
    connection.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)
    return connection


def disconnect_connection(db: Session, connection: StripeConnection) -> StripeConnection:
    connection.status = StripeConnectionStatus.disconnected
    connection.disconnected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(connection)
    return connection
