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


def get_authorizations_in_warning_window(
    db: Session,
    max_days: int,
) -> list[IrsAuthorization]:
    """
    Active authorizations that have not yet lapsed but expire within
    max_days. This is the set the warning ladder walks.

    CROSS-FIRM BY DESIGN. This function takes no firm_id and must not be
    given one. It backs the nightly sweep, which runs once for the whole
    installation rather than once per firm, so it relies on the nightly
    sweep exemption to the tenant isolation rule. Scoping it to a single
    firm would silently stop expiry warnings for every other firm. The
    function it replaced, get_authorizations_expiring_soon, relied on the
    same exemption.

    Notification state is deliberately not filtered here. Which tiers have
    already fired lives in irs_authorization_warnings, and the sweep checks
    it per tier.
    """
    today = date.today()
    window_end = today + timedelta(days=max_days)
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until >= today,
            IrsAuthorization.valid_until <= window_end,
        )
    ).scalars().all()


def get_lapsed_active_authorizations(
    db: Session,
) -> list[IrsAuthorization]:
    """
    Authorizations still marked active whose valid_until is already in the
    past. These are the ones that slipped through, including any that
    lapsed months ago and were never picked up.

    CROSS-FIRM BY DESIGN. Same nightly sweep exemption as
    get_authorizations_in_warning_window above. Do not add a firm_id
    parameter to this function.

    This query drains itself: the sweep writes status = "expired" for
    everything it returns, so a given row is only ever seen once.
    """
    today = date.today()
    return db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.status == "active",
            IrsAuthorization.valid_until.isnot(None),
            IrsAuthorization.valid_until < today,
        )
    ).scalars().all()
