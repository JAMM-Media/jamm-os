# app/services/cooperative_service.py
#
# Deliberately separate from firm_chat_service.py per spec section 3.

import random
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.models.cooperative import CooperativeMember
from app.models.firm import Firm
from app.models.user import User


def _generate_handle(db: Session) -> str:
    """Generate a unique 'User NNNNN' handle not already in use."""
    for _ in range(20):
        candidate = f"User {random.randint(10000, 99999)}"
        existing = db.execute(
            select(CooperativeMember).where(CooperativeMember.handle == candidate)
        ).scalar_one_or_none()
        if existing is None:
            return candidate
    raise RuntimeError("Failed to generate a unique cooperative handle after 20 attempts")


def opt_in_firm(db: Session, calling_owner: User) -> dict:
    """Enable the Growth Cooperative for a firm and create the owner's member record.

    Only callable by a firm_owner. Idempotent if already enabled.
    """
    if calling_owner.role != UserRole.firm_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the firm owner can opt the firm into the Growth Cooperative.",
        )

    firm = db.execute(
        select(Firm).where(Firm.id == calling_owner.firm_id)
    ).scalar_one()

    firm.cooperative_enabled = True

    existing_member = db.execute(
        select(CooperativeMember).where(CooperativeMember.user_id == calling_owner.id)
    ).scalar_one_or_none()

    if existing_member is None:
        handle = _generate_handle(db)
        member = CooperativeMember(
            user_id=calling_owner.id,
            firm_id=calling_owner.firm_id,
            handle=handle,
            is_active=True,
            granted_by=None,
        )
        db.add(member)

    db.commit()

    if existing_member is None:
        db.refresh(member)
        return {"cooperative_enabled": True, "handle": member.handle}
    return {"cooperative_enabled": True, "handle": existing_member.handle}


def grant_access(db: Session, calling_owner: User, target_user_id: UUID) -> dict:
    """Grant a manager or owner access to the Growth Cooperative.

    Only callable by the firm's own owner. Staff are never eligible.
    Idempotent if the target already has an active member record.
    """
    if calling_owner.role != UserRole.firm_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the firm owner can grant Growth Cooperative access.",
        )

    firm = db.execute(
        select(Firm).where(Firm.id == calling_owner.firm_id)
    ).scalar_one()

    if not firm.cooperative_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This firm has not opted into the Growth Cooperative.",
        )

    target = db.execute(
        select(User).where(User.id == target_user_id, User.firm_id == calling_owner.firm_id)
    ).scalar_one_or_none()

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in this firm.",
        )

    if target.role == UserRole.staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff members are not eligible for Growth Cooperative access.",
        )

    existing = db.execute(
        select(CooperativeMember).where(CooperativeMember.user_id == target_user_id)
    ).scalar_one_or_none()

    if existing is not None:
        return {"granted": True, "handle": existing.handle, "already_existed": True}

    handle = _generate_handle(db)
    member = CooperativeMember(
        user_id=target_user_id,
        firm_id=calling_owner.firm_id,
        handle=handle,
        is_active=True,
        granted_by=calling_owner.id,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return {"granted": True, "handle": member.handle, "already_existed": False}


def get_active_member(db: Session, user_id: UUID) -> CooperativeMember:
    """Return the caller's active CooperativeMember or raise 403."""
    member = db.execute(
        select(CooperativeMember).where(
            CooperativeMember.user_id == user_id,
            CooperativeMember.is_active == True,  # noqa: E712
        )
    ).scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have active access to the Growth Cooperative.",
        )
    return member
