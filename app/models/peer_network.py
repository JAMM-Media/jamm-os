# app/models/peer_network.py
#
# Deliberately separate from app/models/firm_chat.py per spec section 3:
# no shared models, no shared query helpers with any firm-scoped surface.
# Message authorship resolves only through PeerNetworkMember, never users.id directly.

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class PeerNetworkMember(Base):
    """One record per user who has been granted access to the Peer Network."""

    __tablename__ = "peer_network_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    handle: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_jamm_team: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    has_posted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    is_muted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    muted_reason: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        default=None,
    )

    muted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
    )

    muted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PeerNetworkRoom(Base):
    """A room in the Peer Network. Starts with a singleton "main" room."""

    __tablename__ = "peer_network_rooms"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    room_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class PeerNetworkRoomMember(Base):
    """Per-room membership for DMs and subgroups.

    main and announcements rooms are always open to every active network member
    and never have explicit membership rows. DM and subgroup rooms are private
    and only visible to members listed here.
    """

    __tablename__ = "peer_network_room_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    joined_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("room_id", "member_id", name="uq_peer_network_room_member"),
    )


class PeerNetworkMessage(Base):
    """A message posted in a PeerNetworkRoom.

    author_member_id references PeerNetworkMember, never users.id directly,
    so a deactivated member's past messages survive intact.
    """

    __tablename__ = "peer_network_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("peer_network_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    edited_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        default=None,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("peer_network_messages.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        index=True,
    )

    mentions: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)


class PeerNetworkAlias(Base):
    """Per-viewer private label for another member's handle.

    owner_member_id: the member who set the label.
    target_member_id: the member being labeled.
    Strictly per-viewer: only owner_member_id ever sees this alias.
    """

    __tablename__ = "peer_network_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    owner_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    label: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("owner_member_id", "target_member_id", name="uq_peer_network_alias_owner_target"),
    )


ALLOWED_REACTIONS = ["👍", "❤️", "😂", "🎉", "👏", "💡"]


class PeerNetworkReaction(Base):
    """Emoji reaction from a member on a message.

    Toggle behavior: adding the same emoji a second time removes it.
    Only emoji in ALLOWED_REACTIONS are accepted.
    """

    __tablename__ = "peer_network_reactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("peer_network_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    emoji: Mapped[str] = mapped_column(String(32), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("message_id", "member_id", "emoji", name="uq_peer_network_reaction"),
    )
