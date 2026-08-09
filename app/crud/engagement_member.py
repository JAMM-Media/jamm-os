# app/crud/engagement_member.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.engagement_member import EngagementMember


def get_member_for_firm(db: Session, member_id: UUID, firm_id: UUID) -> EngagementMember | None:
    return db.execute(
        select(EngagementMember).where(
            EngagementMember.firm_id == firm_id,
            EngagementMember.id == member_id,
        )
    ).scalars().first()


def get_membership(
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
    user_id: UUID,
) -> EngagementMember | None:
    """The single row for one user on one engagement, or None. This is the
    only question the permission rule ever needs to ask of this table."""
    return db.execute(
        select(EngagementMember).where(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == engagement_id,
            EngagementMember.user_id == user_id,
        )
    ).scalars().first()


def get_members_for_engagement(db: Session, firm_id: UUID, engagement_id: UUID):
    """Returns a query, scoped to the firm first, for use with pagination."""
    return (
        db.query(EngagementMember)
        .filter(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == engagement_id,
        )
        .order_by(
            EngagementMember.is_administrator.desc(),
            EngagementMember.created_at,
        )
    )


def create_member(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID,
    user_id: UUID,
    is_administrator: bool,
) -> EngagementMember:
    member = EngagementMember(
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=user_id,
        is_administrator=is_administrator,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def update_member(db: Session, member: EngagementMember, payload) -> EngagementMember:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, key, value)
    db.commit()
    db.refresh(member)
    return member


def delete_member(db: Session, member: EngagementMember) -> None:
    db.delete(member)
    db.commit()
