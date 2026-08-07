# app/api/cooperative.py
#
# Deliberately separate from app/api/firm_chat.py per spec section 3.

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.cooperative import CooperativeMessage, CooperativeRoom
from app.models.firm import Firm
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
    get_active_member(db=db, user_id=current_user.id)

    rooms = db.execute(select(CooperativeRoom)).scalars().all()
    return {
        "items": [{"id": str(r.id), "room_type": r.room_type, "name": r.name} for r in rooms],
        "total": len(rooms),
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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Room not found.")

    total_stmt = select(CooperativeMessage).where(CooperativeMessage.room_id == room_id)
    all_messages = db.execute(total_stmt.order_by(CooperativeMessage.created_at.asc())).scalars().all()

    offset = (page - 1) * page_size
    paginated = all_messages[offset: offset + page_size]

    # Resolve handles in a single pass over the paginated slice.
    from app.models.cooperative import CooperativeMember
    member_ids = {m.author_member_id for m in paginated if m.author_member_id}
    handle_map: dict[uuid.UUID, str] = {}
    if member_ids:
        members = db.execute(
            select(CooperativeMember).where(CooperativeMember.id.in_(member_ids))
        ).scalars().all()
        handle_map = {m.id: m.handle for m in members}

    items = [
        {
            "id": str(m.id),
            "room_id": str(m.room_id),
            "author_handle": handle_map.get(m.author_member_id, "[deleted]") if m.author_member_id else "[deleted]",
            "body": m.body,
            "created_at": m.created_at.isoformat(),
        }
        for m in paginated
    ]

    return {"items": items, "total": len(all_messages)}


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
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Room not found.")

    text = (body.get("body") or "").strip()
    if not text:
        from fastapi import HTTPException
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
        "body": message.body,
        "created_at": message.created_at.isoformat(),
    }
