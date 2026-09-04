# app/api/peer_network.py
#
# Deliberately separate from app/api/firm_chat.py per spec section 3.

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.core.enums import NotificationType, NotificationTier, RecipientType, UserRole
from app.dependencies.roles import require_firm_owner, require_system_admin
from app.models.peer_network import (ALLOWED_REACTIONS, PeerNetworkAlias, PeerNetworkMember, PeerNetworkMessage, PeerNetworkReaction, PeerNetworkRoom, PeerNetworkRoomMember)
from app.models.user import User
from app.services.notification_service import NotificationService
from app.services.peer_network_service import accept_terms, get_active_member, get_room_membership, grant_access, opt_in_firm

router = APIRouter()

# Regex for stored mention tokens: @{uuid}
_MENTION_RE = re.compile(
    r'@\{([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\}'
)


def _resolve_mentions(body: str, handle_map: dict, alias_map: dict) -> str:
    """Replace @{uuid} tokens with the viewer's per-viewer display text."""
    def _sub(m: re.Match) -> str:
        try:
            mid = uuid.UUID(m.group(1))
        except ValueError:
            return m.group(0)
        raw_handle = handle_map.get(mid)
        if raw_handle is None:
            return m.group(0)
        return "\u0000" + alias_map.get(mid, raw_handle) + "\u0001"
    return _MENTION_RE.sub(_sub, body)



# ---------------------------------------------------------------------------
# POST /peer-network/rooms
# ---------------------------------------------------------------------------

@router.post("/rooms", status_code=status.HTTP_201_CREATED)
def create_room(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    creator = get_active_member(db=db, user_id=current_user.id)

    room_type = (body.get("room_type") or "").strip()
    if room_type not in ("dm", "subgroup"):
        raise HTTPException(
            status_code=422,
            detail="room_type must be 'dm' or 'subgroup'. main and announcements are not user-creatable.",
        )

    raw_member_ids = body.get("member_ids") or []
    try:
        target_ids = [uuid.UUID(str(mid)) for mid in raw_member_ids]
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="All member_ids must be valid UUIDs.")

    # Validate every requested member is a real, active PeerNetworkMember.
    valid_targets: list[PeerNetworkMember] = []
    if target_ids:
        found = db.execute(
            select(PeerNetworkMember).where(
                PeerNetworkMember.id.in_(target_ids),
                PeerNetworkMember.is_active == True,  # noqa: E712
            )
        ).scalars().all()
        found_ids = {m.id for m in found}
        invalid_ids = [str(mid) for mid in target_ids if mid not in found_ids]
        if invalid_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid or inactive member ids: {', '.join(invalid_ids)}",
            )
        valid_targets = list(found)

    # Count total participants: creator + requested targets (deduplicated).
    all_member_ids = {creator.id} | {m.id for m in valid_targets}
    total_count = len(all_member_ids)

    if room_type == "dm":
        if total_count != 2:
            raise HTTPException(
                status_code=422,
                detail=f"A DM requires exactly 2 total participants (creator + 1 other). Got {total_count}.",
            )
        room_name = None  # DMs are never named.
    else:  # subgroup
        if total_count < 2:
            raise HTTPException(
                status_code=422,
                detail="A subgroup requires at least 2 total participants (creator + 1 other).",
            )
        room_name = (body.get("name") or "").strip() or None

    room = PeerNetworkRoom(room_type=room_type, name=room_name)
    db.add(room)
    db.flush()  # get room.id before adding members

    for mid in all_member_ids:
        db.add(PeerNetworkRoomMember(room_id=room.id, member_id=mid))

    db.commit()
    db.refresh(room)

    return {
        "id": str(room.id),
        "room_type": room.room_type,
        "name": room.name,
        "member_count": total_count,
    }


# ---------------------------------------------------------------------------
# POST /peer-network/messages/{message_id}/reactions
# ---------------------------------------------------------------------------

@router.post("/messages/{message_id}/reactions", status_code=status.HTTP_200_OK)
def toggle_reaction(
    message_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)

    emoji = (body.get("emoji") or "").strip()
    if emoji not in ALLOWED_REACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Emoji must be one of: {', '.join(ALLOWED_REACTIONS)}",
        )

    message = db.execute(
        select(PeerNetworkMessage).where(PeerNetworkMessage.id == message_id)
    ).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    room = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id == message.room_id)
    ).scalar_one()
    if room.room_type in ("dm", "subgroup"):
        if get_room_membership(db=db, room_id=room.id, member_id=member.id) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room.",
            )

    existing = db.execute(
        select(PeerNetworkReaction).where(
            PeerNetworkReaction.message_id == message_id,
            PeerNetworkReaction.member_id == member.id,
            PeerNetworkReaction.emoji == emoji,
        )
    ).scalar_one_or_none()

    if existing:
        db.delete(existing)
    else:
        db.add(PeerNetworkReaction(
            message_id=message_id,
            member_id=member.id,
            emoji=emoji,
        ))
    db.commit()

    # Return updated reaction summary for this message.
    all_rxns = db.execute(
        select(PeerNetworkReaction).where(PeerNetworkReaction.message_id == message_id)
    ).scalars().all()
    from collections import defaultdict
    by_emoji: dict = defaultdict(list)
    for r in all_rxns:
        by_emoji[r.emoji].append(r.member_id)
    return {
        "message_id": str(message_id),
        "reactions": [
            {
                "emoji": e,
                "count": len(ids),
                "reacted_by_me": member.id in ids,
            }
            for e, ids in by_emoji.items()
        ],
    }


# POST /peer-network/rooms/{room_id}/hide
# ---------------------------------------------------------------------------

@router.post("/rooms/{room_id}/hide", status_code=status.HTTP_200_OK)
def hide_room(
    room_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)

    room = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    if room.room_type in ("main", "announcements"):
        raise HTTPException(
            status_code=422,
            detail="Main and Announcements rooms cannot be hidden.",
        )

    row = get_room_membership(db=db, room_id=room.id, member_id=member.id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this room.",
        )

    row.is_hidden = True
    db.commit()

    return {"hidden": True, "room_id": str(room_id)}


# PATCH /peer-network/rooms/{room_id}
# ---------------------------------------------------------------------------

@router.patch("/rooms/{room_id}", status_code=status.HTTP_200_OK)
def rename_room(
    room_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)

    room = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    if room.room_type != "subgroup":
        raise HTTPException(
            status_code=422,
            detail="Only subgroup rooms can be renamed. DMs are never named; main and announcements are not user-renameable.",
        )

    if get_room_membership(db=db, room_id=room.id, member_id=member.id) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this room.",
        )

    new_name = (body.get("name") or "").strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="name is required and cannot be empty.")

    room.name = new_name
    db.commit()

    return {"id": str(room.id), "room_type": room.room_type, "name": room.name}


# GET /peer-network/aliases
# ---------------------------------------------------------------------------

@router.get("/aliases")
def list_my_aliases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)
    aliases = db.execute(
        select(PeerNetworkAlias).where(PeerNetworkAlias.owner_member_id == member.id)
    ).scalars().all()
    target_ids = [a.target_member_id for a in aliases]
    handle_map: dict[uuid.UUID, str] = {}
    if target_ids:
        targets = db.execute(
            select(PeerNetworkMember).where(PeerNetworkMember.id.in_(target_ids))
        ).scalars().all()
        handle_map = {t.id: t.handle for t in targets}
    return {
        "items": [
            {
                "target_member_id": str(a.target_member_id),
                "label": a.label,
                "handle": handle_map.get(a.target_member_id, a.label),
            }
            for a in aliases
        ],
        "total": len(aliases),
    }


# ---------------------------------------------------------------------------
# GET /peer-network/members/search
# ---------------------------------------------------------------------------

@router.get("/members/search")
def search_members(
    handle_prefix: str = Query(..., min_length=1, max_length=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)
    results = db.execute(
        select(PeerNetworkMember).where(
            PeerNetworkMember.is_active == True,  # noqa: E712
            PeerNetworkMember.handle.ilike(f"{handle_prefix}%"),
        ).limit(5)
    ).scalars().all()
    return {
        "items": [
            {"target_member_id": str(m.id), "handle": m.handle, "label": None}
            for m in results
            if m.id != member.id
        ],
        "total": len(results),
    }


# POST /peer-network/opt-in
# ---------------------------------------------------------------------------

@router.post("/opt-in", status_code=status.HTTP_200_OK)
def opt_in(
    db: Session = Depends(get_db),
    calling_owner: User = Depends(require_firm_owner),
):
    return opt_in_firm(db=db, calling_owner=calling_owner)


# ---------------------------------------------------------------------------
# POST /peer-network/members/{user_id}/grant
# ---------------------------------------------------------------------------

@router.post("/members/{user_id}/grant", status_code=status.HTTP_200_OK)
def grant_member_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    calling_owner: User = Depends(require_firm_owner),
):
    return grant_access(db=db, calling_owner=calling_owner, target_user_id=user_id)


# ---------------------------------------------------------------------------
# POST /peer-network/accept-terms
# ---------------------------------------------------------------------------

@router.post("/accept-terms", status_code=status.HTTP_200_OK)
def accept_peer_network_terms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return accept_terms(db=db, user_id=current_user.id)


# ---------------------------------------------------------------------------
# GET /peer-network/rooms
# ---------------------------------------------------------------------------

@router.get("/rooms")
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active PeerNetworkMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    # main and announcements are open to all active members.
    open_rooms = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.room_type.in_(["main", "announcements"]))
    ).scalars().all()

    # dm and subgroup rooms are private; only include where the member has a membership row
    # and has not hidden it.
    member_room_ids = db.execute(
        select(PeerNetworkRoomMember.room_id).where(
            PeerNetworkRoomMember.member_id == member.id,
            PeerNetworkRoomMember.is_hidden == False,  # noqa: E712
        )
    ).scalars().all()
    private_rooms = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id.in_(member_room_ids))
    ).scalars().all() if member_room_ids else []

    seen_ids = {r.id for r in open_rooms}
    rooms = list(open_rooms)
    for r in private_rooms:
        if r.id not in seen_ids:
            rooms.append(r)

    # Compute dm_display for DM rooms: the other participant's per-viewer display name.
    dm_room_ids = [r.id for r in rooms if r.room_type == "dm"]
    dm_display_map: dict[uuid.UUID, str] = {}
    if dm_room_ids:
        dm_member_rows = db.execute(
            select(PeerNetworkRoomMember).where(
                PeerNetworkRoomMember.room_id.in_(dm_room_ids)
            )
        ).scalars().all()
        other_id_by_room: dict[uuid.UUID, uuid.UUID] = {}
        for row in dm_member_rows:
            if row.member_id != member.id:
                other_id_by_room[row.room_id] = row.member_id
        other_ids = set(other_id_by_room.values())
        if other_ids:
            other_members = db.execute(
                select(PeerNetworkMember).where(PeerNetworkMember.id.in_(other_ids))
            ).scalars().all()
            handle_map_dm = {m.id: m.handle for m in other_members}
            dm_aliases = db.execute(
                select(PeerNetworkAlias).where(
                    PeerNetworkAlias.owner_member_id == member.id,
                    PeerNetworkAlias.target_member_id.in_(other_ids),
                )
            ).scalars().all()
            alias_map_dm = {a.target_member_id: a.label for a in dm_aliases}
            for room_id, other_id in other_id_by_room.items():
                raw = handle_map_dm.get(other_id, "Unknown")
                dm_display_map[room_id] = alias_map_dm.get(other_id, raw)

    def _room_item(r: PeerNetworkRoom) -> dict:
        return {
            "id": str(r.id),
            "room_type": r.room_type,
            "name": r.name,
            "dm_display": dm_display_map.get(r.id),
        }

    return {
        "items": [_room_item(r) for r in rooms],
        "total": len(rooms),
        "my_handle": member.handle,
        "has_posted": member.has_posted,
        "is_muted": member.is_muted,
        "muted_reason": member.muted_reason,
    }


# ---------------------------------------------------------------------------
# GET /peer-network/rooms/{room_id}/messages
# ---------------------------------------------------------------------------

@router.get("/rooms/{room_id}/messages")
def list_messages(
    room_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active PeerNetworkMember status, not firm-scoped role.
    member = get_active_member(db=db, user_id=current_user.id)

    room = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    if room.room_type in ("dm", "subgroup"):
        if get_room_membership(db=db, room_id=room.id, member_id=member.id) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room.",
            )

    # Real count query -- no unbounded fetch.
    total = db.execute(
        select(func.count()).select_from(PeerNetworkMessage).where(PeerNetworkMessage.room_id == room_id)
    ).scalar_one()

    offset = (page - 1) * page_size
    paginated = db.execute(
        select(PeerNetworkMessage)
        .where(PeerNetworkMessage.room_id == room_id)
        .order_by(PeerNetworkMessage.created_at.asc())
        .limit(page_size)
        .offset(offset)
    ).scalars().all()

    # Resolve handles and the caller's own aliases in one pass.
    # Include both author IDs and mention target IDs so tokens resolve per-viewer.
    member_ids: set[uuid.UUID] = {m.author_member_id for m in paginated if m.author_member_id}
    for msg in paginated:
        if msg.mentions:
            for mid_str in msg.mentions:
                try:
                    member_ids.add(uuid.UUID(mid_str))
                except (ValueError, AttributeError):
                    pass

    handle_map: dict[uuid.UUID, str] = {}
    alias_map: dict[uuid.UUID, str] = {}
    jamm_team_map: dict[uuid.UUID, bool] = {}
    if member_ids:
        members = db.execute(
            select(PeerNetworkMember).where(PeerNetworkMember.id.in_(member_ids))
        ).scalars().all()
        handle_map = {m.id: m.handle for m in members}
        jamm_team_map = {m.id: m.is_jamm_team for m in members}

        aliases = db.execute(
            select(PeerNetworkAlias).where(
                PeerNetworkAlias.owner_member_id == member.id,
                PeerNetworkAlias.target_member_id.in_(member_ids),
            )
        ).scalars().all()
        alias_map = {a.target_member_id: a.label for a in aliases}

    # Batch-fetch reactions for this page.
    page_message_ids = [m.id for m in paginated]
    all_reactions = db.execute(
        select(PeerNetworkReaction).where(PeerNetworkReaction.message_id.in_(page_message_ids))
    ).scalars().all() if page_message_ids else []

    from collections import defaultdict
    reactions_by_msg: dict = defaultdict(lambda: defaultdict(list))
    for rxn in all_reactions:
        reactions_by_msg[rxn.message_id][rxn.emoji].append(rxn.member_id)

    # Batch-fetch reply counts.
    reply_count_map: dict[uuid.UUID, int] = {}
    if page_message_ids:
        reply_rows = db.execute(
            select(PeerNetworkMessage.parent_id, func.count().label("cnt"))
            .where(PeerNetworkMessage.parent_id.in_(page_message_ids))
            .group_by(PeerNetworkMessage.parent_id)
        ).all()
        reply_count_map = {row.parent_id: row.cnt for row in reply_rows}

    items = []
    for m in paginated:
        raw_handle = handle_map.get(m.author_member_id, "[deleted]") if m.author_member_id else "[deleted]"
        display = alias_map.get(m.author_member_id, raw_handle) if m.author_member_id else raw_handle
        if m.is_deleted:
            resolved_body = "[deleted]"
        else:
            resolved_body = _resolve_mentions(m.body, handle_map, alias_map)
        items.append({
            "id": str(m.id),
            "room_id": str(m.room_id),
            "author_member_id": str(m.author_member_id) if m.author_member_id else None,
            "author_handle": raw_handle,
            "author_display": display,
            "body": resolved_body,
            "created_at": m.created_at.isoformat(),
            "edited": m.edited_at is not None,
            "deleted": m.is_deleted,
            "is_jamm_team": jamm_team_map.get(m.author_member_id, False) if m.author_member_id else False,
            "parent_id": str(m.parent_id) if m.parent_id else None,
            "reply_count": reply_count_map.get(m.id, 0),
            "reactions": [
                {
                    "emoji": emoji,
                    "count": len(reactor_ids),
                    "reacted_by_me": member.id in reactor_ids,
                }
                for emoji, reactor_ids in reactions_by_msg.get(m.id, {}).items()
            ],
        })

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# POST /peer-network/rooms/{room_id}/messages
# ---------------------------------------------------------------------------

@router.post("/rooms/{room_id}/messages", status_code=status.HTTP_201_CREATED)
def post_message(
    room_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active PeerNetworkMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    # Separate mute check: muted members can read but not post.
    if member.is_muted:
        # appeals@jammpx.com is a placeholder pending a real support inbox.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your account has been muted: {member.muted_reason}. "
                "To appeal, contact appeals@jammpx.com."
            ),
        )

    room = db.execute(
        select(PeerNetworkRoom).where(PeerNetworkRoom.id == room_id)
    ).scalar_one_or_none()

    if room is None:
        raise HTTPException(status_code=404, detail="Room not found.")

    if room.room_type in ("dm", "subgroup"):
        if get_room_membership(db=db, room_id=room.id, member_id=member.id) is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this room.",
            )

    if room.room_type == "announcements" and current_user.role != UserRole.system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only JAMM team accounts can post in the Announcements room.",
        )

    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message body cannot be empty.")

    # Handle optional parent_id for replies; flatten if target is itself a reply.
    raw_parent_id = body.get("parent_id")
    resolved_parent_id: uuid.UUID | None = None
    if raw_parent_id:
        try:
            requested_parent = uuid.UUID(str(raw_parent_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="parent_id must be a valid UUID.")
        parent_msg = db.execute(
            select(PeerNetworkMessage).where(
                PeerNetworkMessage.id == requested_parent,
                PeerNetworkMessage.room_id == room_id,
            )
        ).scalar_one_or_none()
        if parent_msg is None:
            raise HTTPException(status_code=404, detail="Parent message not found in this room.")
        # Flatten: if the target parent is itself a reply, use its parent instead.
        resolved_parent_id = parent_msg.parent_id if parent_msg.parent_id else parent_msg.id

    if not member.has_posted:
        member.has_posted = True

    # Parse @{uuid} mention tokens, validate each is a real active member.
    raw_mention_ids = [uuid.UUID(m) for m in _MENTION_RE.findall(text)]
    mention_members: list[PeerNetworkMember] = []
    if raw_mention_ids:
        candidates = db.execute(
            select(PeerNetworkMember).where(
                PeerNetworkMember.id.in_(raw_mention_ids),
                PeerNetworkMember.is_active == True,  # noqa: E712
            )
        ).scalars().all()
        candidate_ids = {c.id for c in candidates}
        # Preserve original mention order, silently drop invalid IDs.
        seen: set[uuid.UUID] = set()
        for mid in raw_mention_ids:
            if mid in candidate_ids and mid not in seen:
                seen.add(mid)
                mention_members.append(next(c for c in candidates if c.id == mid))

    valid_mention_ids = [str(m.id) for m in mention_members]

    message = PeerNetworkMessage(
        room_id=room_id,
        author_member_id=member.id,
        body=text,
        mentions=valid_mention_ids if valid_mention_ids else None,
        parent_id=resolved_parent_id,
    )
    db.add(message)

    # Unhide this room for any other member who had hidden it, so the conversation
    # reappears in their sidebar automatically when a new message arrives.
    hidden_members = db.execute(
        select(PeerNetworkRoomMember).where(
            PeerNetworkRoomMember.room_id == room_id,
            PeerNetworkRoomMember.member_id != member.id,
            PeerNetworkRoomMember.is_hidden == True,  # noqa: E712
        )
    ).scalars().all()
    for row in hidden_members:
        row.is_hidden = False

    db.commit()
    db.refresh(message)

    # Send in-app notifications to mentioned members.
    # appeals@jammpx.com is a placeholder; NotificationService failure must not
    # abort the message send.
    if room.room_type == "dm":
        room_description = "in a direct message"
    elif room.room_type == "announcements":
        room_description = "in the Peer Network Announcements room"
    elif room.room_type == "subgroup" and room.name:
        room_description = f"in the group {room.name}"
    elif room.room_type == "subgroup":
        room_description = "in a group conversation"
    else:
        room_description = "in the Peer Network main room"

    for mentioned in mention_members:
        if mentioned.id == member.id:
            continue  # no self-notification
        try:
            NotificationService.create_notification(
                db=db,
                firm_id=mentioned.firm_id,
                recipient_id=mentioned.user_id,
                recipient_type=RecipientType.staff,
                title="You were mentioned in the Peer Network",
                body=f"{member.handle} mentioned you {room_description}.",
                notification_type=NotificationType.peer_network_mention,
                tier=NotificationTier.quiet,
            )
        except Exception:
            pass  # notification failure must not abort the message

    # For Announcements posts, notify every active member (distinct from mention-only logic).
    if room.room_type == "announcements":
        all_active_members = db.execute(
            select(PeerNetworkMember).where(
                PeerNetworkMember.is_active == True,  # noqa: E712
                PeerNetworkMember.id != member.id,
            )
        ).scalars().all()
        for target in all_active_members:
            try:
                NotificationService.create_notification(
                    db=db,
                    firm_id=target.firm_id,
                    recipient_id=target.user_id,
                    recipient_type=RecipientType.staff,
                    title="New announcement from JAMM",
                    body=f"{member.handle} posted a new announcement in the Peer Network.",
                    notification_type=NotificationType.peer_network_mention,
                tier=NotificationTier.silent,
                )
            except Exception:
                pass

    # Resolve mention tokens per sender (they are this response's viewer).
    mention_handle_map = {m.id: m.handle for m in mention_members}
    mention_alias_map: dict[uuid.UUID, str] = {}
    if valid_mention_ids:
        sender_aliases = db.execute(
            select(PeerNetworkAlias).where(
                PeerNetworkAlias.owner_member_id == member.id,
                PeerNetworkAlias.target_member_id.in_([m.id for m in mention_members]),
            )
        ).scalars().all()
        mention_alias_map = {a.target_member_id: a.label for a in sender_aliases}

    resolved_body = _resolve_mentions(message.body, mention_handle_map, mention_alias_map)
    return {
        "id": str(message.id),
        "room_id": str(message.room_id),
        "author_member_id": str(message.author_member_id),
        "author_handle": member.handle,
        "author_display": member.handle,
        "body": resolved_body,
        "created_at": message.created_at.isoformat(),
        "edited": False,
        "deleted": False,
        "is_jamm_team": member.is_jamm_team,
        "parent_id": str(message.parent_id) if message.parent_id else None,
        "reply_count": 0,
        "reactions": [],
    }


# ---------------------------------------------------------------------------
# PATCH /peer-network/messages/{message_id}
# ---------------------------------------------------------------------------

@router.patch("/messages/{message_id}", status_code=status.HTTP_200_OK)
def edit_message(
    message_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)

    message = db.execute(
        select(PeerNetworkMessage).where(PeerNetworkMessage.id == message_id)
    ).scalar_one_or_none()

    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    if message.author_member_id != member.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only edit your own messages.")
    if message.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A deleted message cannot be edited.")

    text = (body.get("body") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message body cannot be empty.")

    from datetime import datetime, timezone as tz
    message.body = text
    message.edited_at = datetime.now(tz.utc)
    db.commit()

    return {
        "id": str(message.id),
        "body": message.body,
        "edited": True,
        "deleted": False,
    }


# ---------------------------------------------------------------------------
# DELETE /peer-network/messages/{message_id}
# ---------------------------------------------------------------------------

@router.delete("/messages/{message_id}", status_code=status.HTTP_200_OK)
def delete_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    member = get_active_member(db=db, user_id=current_user.id)

    message = db.execute(
        select(PeerNetworkMessage).where(PeerNetworkMessage.id == message_id)
    ).scalar_one_or_none()

    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    if message.author_member_id != member.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own messages.")

    message.is_deleted = True
    db.commit()

    return {"deleted": True}


# ---------------------------------------------------------------------------
# DELETE /peer-network/admin/messages/{message_id}  (system admin only)
# ---------------------------------------------------------------------------

@router.delete("/admin/messages/{message_id}", status_code=status.HTTP_200_OK)
def admin_delete_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_system_admin),
):
    """Purge a message's body content entirely.

    This is a hard content purge, not a soft flag-only delete.
    is_deleted is set to True (so the UI renders the same placeholder
    as author-deleted messages) and the real body field is overwritten with
    a fixed placeholder, destroying the original text in the database.

    Note on edit history: this codebase edits messages in place with no
    version table, so overwriting the current body field is the complete
    purge available given tonight's real implementation.
    """
    message = db.execute(
        select(PeerNetworkMessage).where(PeerNetworkMessage.id == message_id)
    ).scalar_one_or_none()

    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    message.is_deleted = True
    message.body = "[removed by admin]"
    db.commit()

    return {"deleted": True, "purged": True}


# ---------------------------------------------------------------------------
# POST /peer-network/admin/members/{member_id}/mute  (system admin only)
# ---------------------------------------------------------------------------

@router.post("/admin/members/{member_id}/mute", status_code=status.HTTP_200_OK)
def mute_member(
    member_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_system_admin),
):
    reason = (body.get("reason") or "").strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A specific reason citing the T&C clause violated is required.")

    member = db.execute(
        select(PeerNetworkMember).where(PeerNetworkMember.id == member_id)
    ).scalar_one_or_none()

    if member is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    from datetime import datetime, timezone
    member.is_muted = True
    member.muted_reason = reason
    member.muted_at = datetime.now(timezone.utc)
    member.muted_by = admin.id
    db.commit()

    return {"muted": True, "member_id": str(member.id), "reason": reason}


# ---------------------------------------------------------------------------
# POST /peer-network/admin/members/{member_id}/unmute  (system admin only)
# ---------------------------------------------------------------------------

@router.post("/admin/members/{member_id}/unmute", status_code=status.HTTP_200_OK)
def unmute_member(
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_system_admin),
):
    member = db.execute(
        select(PeerNetworkMember).where(PeerNetworkMember.id == member_id)
    ).scalar_one_or_none()

    if member is None:
        raise HTTPException(status_code=404, detail="Member not found.")

    member.is_muted = False
    member.muted_reason = None
    member.muted_at = None
    member.muted_by = None
    db.commit()

    return {"muted": False, "member_id": str(member.id)}


# ---------------------------------------------------------------------------
# PATCH /peer-network/members/{target_member_id}/alias
# ---------------------------------------------------------------------------

@router.patch("/members/{target_member_id}/alias", status_code=status.HTTP_200_OK)
def set_alias(
    target_member_id: uuid.UUID,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Gate on active PeerNetworkMember status.
    member = get_active_member(db=db, user_id=current_user.id)

    if target_member_id == member.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot set an alias for yourself.",
        )

    target = db.execute(
        select(PeerNetworkMember).where(PeerNetworkMember.id == target_member_id)
    ).scalar_one_or_none()

    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found.")

    label = (body.get("label") or "").strip()
    if not label:
        raise HTTPException(status_code=422, detail="Label cannot be empty.")

    existing = db.execute(
        select(PeerNetworkAlias).where(
            PeerNetworkAlias.owner_member_id == member.id,
            PeerNetworkAlias.target_member_id == target_member_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.label = label
        db.commit()
        return {"alias_set": True, "label": existing.label, "target_handle": target.handle}

    alias = PeerNetworkAlias(
        owner_member_id=member.id,
        target_member_id=target_member_id,
        label=label,
    )
    db.add(alias)
    db.commit()
    return {"alias_set": True, "label": label, "target_handle": target.handle}
