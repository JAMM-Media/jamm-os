# app/services/engagement_member_service.py

"""
Business logic for engagement membership.

The permission rule for every mutating operation in this module is exactly:

    is_engagement_administrator OR firm_role in (firm_owner, manager)

firm_owner and manager can add members and promote administrators on ANY
engagement in their firm without being members of it. That is capability
without membership, and it is what guarantees an engagement can never be
orphaned when its only administrator leaves. They do NOT appear on the
member list unless somebody explicitly adds them.

system_admin is included alongside firm_owner and manager because every
other RBAC check in this codebase (see app/dependencies/roles.py) treats it
as at least manager-level. Leaving it out here would be the surprise, not
including it.
"""

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import NotificationType, NotificationTier, RecipientType, UserRole
from app.crud import engagement_member as crud_member
from app.models.engagement import Engagement
from app.models.engagement_member import EngagementMember
from app.models.user import User
from app.services.audit_service import write_audit_log

# Firm roles that carry membership-management capability on every engagement
# in the firm, member or not.
FIRM_WIDE_MANAGEMENT_ROLES = (
    UserRole.firm_owner,
    UserRole.manager,
    UserRole.system_admin,
)

# Roles a person must hold to be placed on an engagement at all. A
# client_portal_user is on the other side of the tenant boundary and can
# never be a member of internal work.
ASSIGNABLE_ROLES = (
    UserRole.firm_owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.system_admin,
)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_engagement_for_firm(db: Session, engagement_id: UUID, firm_id: UUID) -> Engagement:
    engagement = db.execute(
        select(Engagement).where(
            Engagement.firm_id == firm_id,
            Engagement.id == engagement_id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement


def is_member(db: Session, *, firm_id: UUID, engagement_id: UUID, user_id: UUID) -> bool:
    return crud_member.get_membership(db, firm_id, engagement_id, user_id) is not None


def is_engagement_administrator(
    db: Session, *, firm_id: UUID, engagement_id: UUID, user_id: UUID
) -> bool:
    membership = crud_member.get_membership(db, firm_id, engagement_id, user_id)
    return bool(membership and membership.is_administrator)


def can_manage_membership(
    db: Session, *, firm_id: UUID, engagement_id: UUID, user: User
) -> bool:
    if user.role in FIRM_WIDE_MANAGEMENT_ROLES:
        return True
    return is_engagement_administrator(
        db, firm_id=firm_id, engagement_id=engagement_id, user_id=user.id
    )


def require_can_manage_membership(
    db: Session, *, firm_id: UUID, engagement_id: UUID, user: User
) -> None:
    if not can_manage_membership(db, firm_id=firm_id, engagement_id=engagement_id, user=user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You must be an administrator of this engagement, or a manager "
                "or firm owner, to manage its members."
            ),
        )


def list_members(db: Session, *, firm_id: UUID, engagement_id: UUID):
    get_engagement_for_firm(db, engagement_id, firm_id)
    return crud_member.get_members_for_engagement(db, firm_id, engagement_id)


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def add_member(
    *,
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
    payload,  # EngagementMemberCreate
    current_user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> EngagementMember:
    get_engagement_for_firm(db, engagement_id, firm_id)
    require_can_manage_membership(
        db, firm_id=firm_id, engagement_id=engagement_id, user=current_user
    )

    target = db.execute(
        select(User).where(User.id == payload.user_id, User.firm_id == firm_id)
    ).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this firm")
    if target.role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Only internal firm users can be added to an engagement.",
        )

    if crud_member.get_membership(db, firm_id, engagement_id, payload.user_id):
        raise HTTPException(
            status_code=409,
            detail="That user is already a member of this engagement.",
        )

    member = crud_member.create_member(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=payload.user_id,
        is_administrator=payload.is_administrator,
    )

    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="engagement_member.added",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="engagement_member",
        entity_id=member.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "engagement_id": str(engagement_id),
            "user_id": str(payload.user_id),
            "as_administrator": bool(payload.is_administrator),
        },
    )

    # Being added straight in as an administrator is the same sensitive event
    # as being promoted afterwards, so it gets the same dedicated record
    # rather than hiding inside the 'added' entry's metadata.
    if member.is_administrator:
        _write_administrator_audit(
            db=db,
            firm_id=firm_id,
            member=member,
            promoted=True,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return member


def add_member_for_assignment(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID,
    user_id: UUID,
    acting_user: User,
) -> Optional[EngagementMember]:
    """Add a member as a side effect of assigning them a task.

    This grants nothing the acting user could not already have granted by
    hand. can_manage_membership() is the identical check add_member() makes,
    so the only thing collapsed here is the two-step dance of adding someone
    to the engagement and then assigning them the work. When the acting user
    does not hold that authority this returns None and writes nothing; the
    caller decides what refusal looks like.

    Never adds as an administrator. Authority to place someone on an
    engagement is not authority to make them able to place others.
    """
    if not can_manage_membership(
        db, firm_id=firm_id, engagement_id=engagement_id, user=acting_user
    ):
        return None

    existing = crud_member.get_membership(db, firm_id, engagement_id, user_id)
    if existing:
        return existing

    target = db.execute(
        select(User).where(User.id == user_id, User.firm_id == firm_id)
    ).scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found in this firm")
    if target.role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Only internal firm users can be added to an engagement.",
        )

    member = crud_member.create_member(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=user_id,
        is_administrator=False,
    )

    # Membership is access to a client's tax data. An addition that leaves no
    # trace is exactly what makes a member list unexplainable six months from
    # now, so the automatic path writes the same record the manual one does,
    # marked with how it happened.
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="engagement_member.added",
        actor_id=acting_user.id,
        actor_type="staff",
        entity_type="engagement_member",
        entity_id=member.id,
        metadata={
            "engagement_id": str(engagement_id),
            "user_id": str(user_id),
            "as_administrator": False,
            "via": "task_assignment",
        },
    )

    return member


def notify_engagement_administrators(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID,
    title: str,
    body: str,
) -> int:
    """Notify whoever can act on an engagement membership problem.

    Falls back to the firm owners when the engagement has no administrator.
    That is a real state rather than a hypothetical: remove_member
    deliberately allows removing the last one, and firm_owner can always
    restore one.

    Returns the number of recipients notified.
    """
    from app.db.session import SessionLocal
    from app.services.notification_service import NotificationService

    recipient_ids = list(db.execute(
        select(EngagementMember.user_id).where(
            EngagementMember.firm_id == firm_id,
            EngagementMember.engagement_id == engagement_id,
            EngagementMember.is_administrator.is_(True),
        )
    ).scalars().all())

    if not recipient_ids:
        # is_active matters more here than anywhere else in this codebase. The
        # fallback fires precisely when there is nobody else to catch the
        # refusal, so a deactivated owner as the sole recipient means the
        # refusal reaches nobody at all. Matches anniversary_service.
        recipient_ids = list(db.execute(
            select(User.id).where(
                User.firm_id == firm_id,
                User.role == UserRole.firm_owner,
                User.is_active == True,
            )
        ).scalars().all())

    if not recipient_ids:
        return 0

    # Its own session, like every other notification written from the service
    # layer. The caller is about to raise, and a refused assignment must not
    # take the notification down with it, nor commit whatever else happens to
    # be sitting on the request session.
    notification_db = SessionLocal()
    try:
        for recipient_id in recipient_ids:
            NotificationService.create_notification(
                db=notification_db,
                firm_id=firm_id,
                recipient_id=recipient_id,
                recipient_type=RecipientType.staff,
                title=title,
                body=body,
                notification_type=NotificationType.system,
                tier=NotificationTier.quiet,
                related_entity_type="engagement",
                related_entity_id=engagement_id,
            )
    finally:
        notification_db.close()

    return len(recipient_ids)


def update_member(
    *,
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
    member_id: UUID,
    payload,  # EngagementMemberUpdate
    current_user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> EngagementMember:
    get_engagement_for_firm(db, engagement_id, firm_id)
    require_can_manage_membership(
        db, firm_id=firm_id, engagement_id=engagement_id, user=current_user
    )

    member = crud_member.get_member_for_firm(db, member_id, firm_id)
    if not member or member.engagement_id != engagement_id:
        raise HTTPException(status_code=404, detail="Engagement member not found")

    was_administrator = member.is_administrator
    updated = crud_member.update_member(db, member, payload)

    if updated.is_administrator != was_administrator:
        _write_administrator_audit(
            db=db,
            firm_id=firm_id,
            member=updated,
            promoted=updated.is_administrator,
            current_user=current_user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    return updated


def remove_member(
    *,
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
    member_id: UUID,
    current_user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """Removal is never blocked, including removal of the last administrator.
    An engagement with no administrator is a Morning Briefing item, not a
    refused request -- firm_owner and manager can always restore one."""
    get_engagement_for_firm(db, engagement_id, firm_id)
    require_can_manage_membership(
        db, firm_id=firm_id, engagement_id=engagement_id, user=current_user
    )

    member = crud_member.get_member_for_firm(db, member_id, firm_id)
    if not member or member.engagement_id != engagement_id:
        raise HTTPException(status_code=404, detail="Engagement member not found")

    removed_user_id = member.user_id
    was_administrator = member.is_administrator
    crud_member.delete_member(db, member)

    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="engagement_member.removed",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="engagement_member",
        entity_id=member_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "engagement_id": str(engagement_id),
            "user_id": str(removed_user_id),
            "was_administrator": was_administrator,
        },
    )
    return True


def ensure_creator_is_administrator(
    *,
    db: Session,
    firm_id: UUID,
    engagement_id: UUID,
    current_user_id: UUID,
) -> Optional[EngagementMember]:
    """Called from engagement creation. The creator becomes an administrator
    of the engagement they just created.

    Returns None without raising when the acting id is not a real user of
    this firm (background jobs and seed harnesses both create engagements
    with a synthetic actor id). Inserting anyway would violate the user_id
    foreign key and take the whole engagement creation down with it, and an
    engagement with no administrator is a recoverable state by design.
    """
    actor = db.execute(
        select(User).where(User.id == current_user_id, User.firm_id == firm_id)
    ).scalars().first()
    if not actor or actor.role not in ASSIGNABLE_ROLES:
        return None

    existing = crud_member.get_membership(db, firm_id, engagement_id, current_user_id)
    if existing:
        return existing

    return crud_member.create_member(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=current_user_id,
        is_administrator=True,
    )


def _write_administrator_audit(
    *,
    db: Session,
    firm_id: UUID,
    member: EngagementMember,
    promoted: bool,
    current_user: User,
    ip_address: Optional[str],
    user_agent: Optional[str],
) -> None:
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="engagement_member.promoted" if promoted else "engagement_member.demoted",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="engagement_member",
        entity_id=member.id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata={
            "engagement_id": str(member.engagement_id),
            "user_id": str(member.user_id),
            "is_administrator": bool(member.is_administrator),
        },
    )
