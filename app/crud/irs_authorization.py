# app/crud/irs_authorization.py

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.irs_authorization import IrsAuthorization
from app.schemas.irs_authorization import IrsAuthorizationCreate, IrsAuthorizationUpdate


def create_irs_authorization(
    db: Session,
    auth_in: IrsAuthorizationCreate,
    firm_id: UUID,
) -> IrsAuthorization:
    auth = IrsAuthorization(**auth_in.model_dump(), firm_id=firm_id)
    db.add(auth)
    db.commit()
    db.refresh(auth)
    return auth


def get_irs_authorization(
    db: Session,
    auth_id: UUID,
    firm_id: UUID,
) -> IrsAuthorization | None:
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.id == auth_id,
            IrsAuthorization.firm_id == firm_id,
        )
    ).scalars().first()


def list_irs_authorizations(
    db: Session,
    firm_id: UUID,
    client_id: Optional[UUID] = None,
    form_type: Optional[str] = None,
    status: Optional[str] = None,
) -> list[IrsAuthorization]:
    stmt = select(IrsAuthorization).where(IrsAuthorization.firm_id == firm_id)
    if client_id:
        stmt = stmt.where(IrsAuthorization.client_id == client_id)
    if form_type:
        stmt = stmt.where(IrsAuthorization.form_type == form_type)
    if status:
        stmt = stmt.where(IrsAuthorization.status == status)
    stmt = stmt.order_by(IrsAuthorization.created_at.desc())
    return db.execute(stmt).scalars().all()


def update_irs_authorization(
    db: Session,
    auth: IrsAuthorization,
    auth_in: IrsAuthorizationUpdate,
) -> IrsAuthorization:
    for key, value in auth_in.model_dump(exclude_unset=True).items():
        setattr(auth, key, value)
    db.commit()
    db.refresh(auth)
    return auth


def get_active_authorization_for_client(
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    form_type: str,
) -> IrsAuthorization | None:
    """
    Returns the most recent active authorization of the given form_type
    for a client. Used to verify authorization is on file before
    allowing transcript requests or automation actions.
    """
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.firm_id == firm_id,
            IrsAuthorization.client_id == client_id,
            IrsAuthorization.form_type == form_type,
            IrsAuthorization.status == "active",
        ).order_by(IrsAuthorization.created_at.desc())
    ).scalars().first()


def get_authorizations_expiring_soon(
    db: Session,
    days: int = 30,
) -> list[IrsAuthorization]:
    """
    Returns active authorizations whose valid_until falls within the
    next N days and where expiry_notification_sent is False.
    """
    today = date.today()
    window_end = today + timedelta(days=days)
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until <= window_end,
            IrsAuthorization.valid_until >= today,
            IrsAuthorization.expiry_notification_sent == False,
        )
    ).scalars().all()
