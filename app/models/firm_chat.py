# app/models/firm_chat.py

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("firm_id", "name", name="uq_channel_firm_name"),
    )

    # Relationships
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    messages: Mapped[list["FirmMessage"]] = relationship(
        "FirmMessage",
        back_populates="channel",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["ChannelMember"]] = relationship(
        "ChannelMember",
        back_populates="channel",
        cascade="all, delete-orphan",
    )


class ChannelMember(Base):
    __tablename__ = "channel_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_member"),
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class FirmMessage(Base):
    __tablename__ = "firm_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    channel_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    body: Mapped[str] = mapped_column(Text, nullable=False)

    # S3 object key only — never the full URL
    attachment_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # List of user UUIDs who were @mentioned
    mentions: Mapped[list | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_firm_messages_firm_channel", "firm_id", "channel_id"),
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    read_receipts: Mapped[list["FirmMessageRead"]] = relationship(
        "FirmMessageRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class FirmMessageRead(Base):
    __tablename__ = "firm_message_reads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firm_messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_firm_message_read"),
    )

    # Relationships
    message: Mapped["FirmMessage"] = relationship(
        "FirmMessage", back_populates="read_receipts"
    )
