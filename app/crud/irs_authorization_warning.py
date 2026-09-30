# app/crud/irs_authorization_warning.py

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.irs_authorization_warning import IrsAuthorizationWarning
from app.schemas.irs_authorization_warning import IrsAuthorizationWarningCreate


def create_warning(
    db: Session,
    warning_in: IrsAuthorizationWarningCreate,
    firm_id: UUID,
) -> IrsAuthorizationWarning:
    """Record a warning tier that has already been delivered."""
    warning = IrsAuthorizationWarning(**warning_in.model_dump(), firm_id=firm_id)
    db.add(warning)
    db.commit()
    db.refresh(warning)
    return warning


def create_warnings_for_recipients(
    db: Session,
    *,
    firm_id: UUID,
    authorization_id: UUID,
    threshold_days: int,
    sent_at: datetime,
    recipient_user_ids: list[UUID],
) -> list[IrsAuthorizationWarning]:
    """
    Record one tier as delivered, one row per recipient, in a single commit.

    Every row carries the same sent_at, because they are one send: the tier
    fired once and reached several people. Letting each row stamp its own
    clock would make the earliest-row grouping in the ladder endpoint depend
    on iteration order.

    An empty recipient list writes nothing and commits nothing. The caller
    only ever passes recipients whose in-app notification landed, so an
    empty list means the tier reached nobody and must not be recorded.
    """
    if not recipient_user_ids:
        return []

    warnings = [
        IrsAuthorizationWarning(
            firm_id=firm_id,
            authorization_id=authorization_id,
            threshold_days=threshold_days,
            sent_at=sent_at,
            recipient_user_id=recipient_user_id,
        )
        for recipient_user_id in recipient_user_ids
    ]
    db.add_all(warnings)
    db.commit()
    for warning in warnings:
        db.refresh(warning)
    return warnings


def list_warnings_for_authorization(
    db: Session,
    firm_id: UUID,
    authorization_id: UUID,
) -> list[IrsAuthorizationWarning]:
    """All tiers that have fired for one authorization, most recent send first."""
    return db.execute(
        select(IrsAuthorizationWarning)
        .where(
            IrsAuthorizationWarning.firm_id == firm_id,
            IrsAuthorizationWarning.authorization_id == authorization_id,
        )
        .order_by(IrsAuthorizationWarning.sent_at.desc())
    ).scalars().all()


def get_warning_for_threshold(
    db: Session,
    firm_id: UUID,
    authorization_id: UUID,
    threshold_days: int,
) -> IrsAuthorizationWarning | None:
    """
    Any row for one specific tier, or None if that tier has not fired.

    This is the check the sweep makes before sending, and since Sep 24,
    2026 a tier can hold several rows, one per recipient. The question it
    answers is unchanged: has this tier fired at all. Which row comes back
    when several exist is not meaningful, and no caller reads it.
    """
    return db.execute(
        select(IrsAuthorizationWarning).where(
            IrsAuthorizationWarning.firm_id == firm_id,
            IrsAuthorizationWarning.authorization_id == authorization_id,
            IrsAuthorizationWarning.threshold_days == threshold_days,
        )
    ).scalars().first()


def delete_warnings_for_authorization(
    db: Session,
    firm_id: UUID,
    authorization_id: UUID,
) -> int:
    """
    Clear the ladder for an authorization and return how many rows went.

    Called when valid_until changes, so a renewal or a corrected typo
    recomputes its tiers from scratch. Deleting through the ORM rather than
    a Core delete() is deliberate: there are at most four rows per
    authorization, so there is nothing bulk about this operation.
    """
    warnings = db.execute(
        select(IrsAuthorizationWarning).where(
            IrsAuthorizationWarning.firm_id == firm_id,
            IrsAuthorizationWarning.authorization_id == authorization_id,
        )
    ).scalars().all()

    for warning in warnings:
        db.delete(warning)
    db.commit()
    return len(warnings)
