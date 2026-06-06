# app/crud/integration.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.services.token_encryption import encrypt_token


def get_integration(db: Session, firm_id: uuid.UUID, provider: str) -> Optional[Integration]:
    stmt = select(Integration).where(
        Integration.firm_id == firm_id,
        Integration.provider == provider,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_integrations_for_firm(db: Session, firm_id: uuid.UUID) -> list[Integration]:
    stmt = (
        select(Integration)
        .where(Integration.firm_id == firm_id)
        .order_by(Integration.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def create_integration(db: Session, firm_id: uuid.UUID, provider: str) -> Integration:
    integration = Integration(
        firm_id=firm_id,
        provider=provider,
        status="disconnected",
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def update_integration_tokens(
    db: Session,
    integration: Integration,
    access_token: str,
    refresh_token: str,
    expires_at: Optional[datetime],
    scopes: Optional[str],
    external_account_id: Optional[str],
) -> Integration:
    integration.encrypted_access_token = encrypt_token(access_token)
    integration.encrypted_refresh_token = encrypt_token(refresh_token)
    integration.token_expires_at = expires_at
    integration.scopes = scopes
    integration.external_account_id = external_account_id
    integration.status = "connected"
    integration.connected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(integration)
    return integration


def update_integration_status(
    db: Session,
    integration: Integration,
    status: str,
    error_message: Optional[str] = None,
) -> Integration:
    integration.status = status
    integration.error_message = error_message
    db.commit()
    db.refresh(integration)
    return integration


def delete_integration(db: Session, integration: Integration) -> None:
    db.delete(integration)
    db.commit()


def get_user_integration(
    db: Session, firm_id: uuid.UUID, user_id: uuid.UUID, provider: str
) -> Optional[Integration]:
    return db.execute(
        select(Integration).where(
            Integration.firm_id == firm_id,
            Integration.user_id == user_id,
            Integration.provider == provider,
        )
    ).scalar_one_or_none()


def create_user_integration(
    db: Session, firm_id: uuid.UUID, user_id: uuid.UUID, provider: str
) -> Integration:
    integration = Integration(firm_id=firm_id, user_id=user_id, provider=provider, status="disconnected")
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def get_integrations_for_user(
    db: Session, firm_id: uuid.UUID, user_id: uuid.UUID
) -> list[Integration]:
    return list(
        db.execute(
            select(Integration).where(
                Integration.firm_id == firm_id,
                Integration.user_id == user_id,
            )
        ).scalars().all()
    )
