# app/models/cooperative.py
#
# Deliberately separate from app/models/firm_chat.py per spec section 3:
# no shared models, no shared query helpers with any firm-scoped surface.
# Message authorship resolves only through CooperativeMember, never users.id directly.

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class CooperativeMember(Base):
    """One record per user who has been granted access to the Growth Cooperative."""

    __tablename__ = "cooperative_members"

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

    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class CooperativeRoom(Base):
    """A room in the Growth Cooperative. Starts with a singleton "main" room."""

    __tablename__ = "cooperative_rooms"

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


class CooperativeMessage(Base):
    """A message posted in a CooperativeRoom.

    author_member_id references CooperativeMember, never users.id directly,
    so a deactivated member's past messages survive intact.
    """

    __tablename__ = "cooperative_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    room_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("cooperative_rooms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cooperative_members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
