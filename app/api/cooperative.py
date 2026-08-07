# app/api/cooperative.py
#
# Deliberately separate from app/api/firm_chat.py per spec section 3.

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner
from app.models.cooperative import CooperativeAlias, CooperativeMember, CooperativeMessage, CooperativeRoom
from app.models.user import User
from app.services.cooperative_service import get_active_member, grant_access, opt_in_firm

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /cooperative/opt-in
# ---------------------------------------------------------------------------

@router.post("/opt-in", status_code=status.HTTP_200_OK)
def opt_in(
    db: Session = Depends(get_db),
    calling_owner: User = Depends(require_firm_owner),
):
    return opt_in_firm(db=db, calling_owner=calling_owner)


# ---------------------------------------------------------------------------
# POST /cooperative/members/{user_id}/grant
# ---------------------------------------------------------------------------

@router.post("/members/{user_id}/grant", status_code=status.HTTP_200_OK)
def grant_member_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    calling_owner: User = Depends(require_firm_owner),
):
    return grant_access(db=db, calling_owner=calling_owner, target_user_id=user_id)


# ---------------------------------------------------------------------------
# GET /cooperative/rooms
# ---------------------------------------------------------------------------

@router.get("/rooms")
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active CooperativeMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    rooms = db.execute(select(CooperativeRoom)).scalars().all()
    return {
        "items": [{"id": str(r.id), "room_type": r.room_type, "name": r.name} for r in rooms],
        "total": len(rooms),
        "my_handle": member.handle,
    }


# ---------------------------------------------------------------------------
# GET /cooperative/rooms/{room_id}/messages
# ---------------------------------------------------------------------------

@router.get("/rooms/{room_id}/messages")
def list_messages(
    room_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active CooperativeMember status, not firm-scoped role.
    member = get_active_member(db=db, user_id=current_user.id)

    room = db.execute(
        select(CooperativeRoom).where(CooperativeRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    # Real count query -- no unbounded fetch.
    total = db.execute(
        select(func.count()).select_from(CooperativeMessage).where(CooperativeMessage.room_id == room_id)
    ).scalar_one()

    offset = (page - 1) * page_size
    paginated = db.execute(
        select(CooperativeMessage)
        .where(CooperativeMessage.room_id == room_id)
        .order_by(CooperativeMessage.created_at.asc())
        .limit(page_size)
        .offset(offset)
    ).scalars().all()

    # Resolve handles and the caller's own aliases in one pass.
    member_ids = {m.author_member_id for m in paginated if m.author_member_id}
    handle_map: dict[uuid.UUID, str] = {}
    alias_map: dict[uuid.UUID, str] = {}
    if member_ids:
        members = db.execute(
            select(CooperativeMember).where(CooperativeMember.id.in_(member_ids))
        ).scalars().all()
        handle_map = {m.id: m.handle for m in members}

        aliases = db.execute(
            select(CooperativeAlias).where(
                CooperativeAlias.owner_member_id == member.id,
                CooperativeAlias.target_member_id.in_(member_ids),
            )
        ).scalars().all()
        alias_map = {a.target_member_id: a.label for a in aliases}

    items = []
    for m in paginated:
        raw_handle = handle_map.get(m.author_member_id, "[deleted]") if m.author_member_id else "[deleted]"
        display = alias_map.get(m.author_member_id, raw_handle) if m.author_member_id else raw_handle
        items.append({
            "id": str(m.id),
            "room_id": str(m.room_id),
            "author_member_id": str(m.author_member_id) if m.author_member_id else None,
            "author_handle": raw_handle,
            "author_display": display,
            "body": m.body,
            "created_at": m.created_at.isoformat(),
        })

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# POST /cooperative/rooms/{room_id}/messages
# ---------------------------------------------------------------------------

@router.post("/rooms/{room_id}/messages", status_code=status.HTTP_201_CREATED)
def post_message(
    room_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active CooperativeMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    room = db.execute(
        select(CooperativeRoom).where(CooperativeRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message body cannot be empty.")

    message = CooperativeMessage(
        room_id=room_id,
        author_member_id=member.id,
        body=text,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return {
        "id": str(message.id),
        "room_id": str(message.room_id),
        "author_handle": member.handle,
        "author_display": member.handle,
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# PATCH /cooperative/members/{target_member_id}/alias
# ---------------------------------------------------------------------------

@router.patch("/members/{target_member_id}/alias", status_code=status.HTTP_200_OK)
def set_alias(
    target_member_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active CooperativeMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    if target_member_id == member.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot set an alias for yourself.",
        )

    target = db.execute(
        select(CooperativeMember).where(CooperativeMember.id == target_member_id)
    ).scalar_one_or_none()

    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label cannot be empty.")

    existing = db.execute(
        select(CooperativeAlias).where(
            CooperativeAlias.owner_member_id == member.id,
            CooperativeAlias.target_member_id == target_member_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.label = label
        db.commit()
        return {"alias_set": True, "label": existing.label, "target_handle": target.handle}

    alias = CooperativeAlias(
        owner_member_id=member.id,
        target_member_id=target_member_id,
        label=label,
    )
    db.add(alias)
    db.commit()
    return {"alias_set": True, "label": label, "target_handle": target.handle}
