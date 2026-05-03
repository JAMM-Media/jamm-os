# app/models/message.py

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class ClientMessage(Base):
    __tablename__ = "client_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # null when the sender is the client via portal
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # "staff" or "client"
    sender_role: Mapped[str] = mapped_column(String(30), nullable=False)

    body: Mapped[str] = mapped_column(Text, nullable=False)

    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Composite index on the primary query path
    __table_args__ = (
        Index("ix_client_messages_firm_client", "firm_id", "client_id"),
    )

    # Relationships
    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
    )

    read_receipts: Mapped[list["ClientMessageRead"]] = relationship(
        "ClientMessageRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class ClientMessageRead(Base):
    __tablename__ = "client_message_reads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("client_messages.id", ondelete="CASCADE"),
        nullable=False,
    )

    # null when the reader is the client — identified by reader_role
    reader_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )

    # "staff" or "client"
    reader_role: Mapped[str] = mapped_column(String(30), nullable=False)

    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("message_id", "reader_id", "reader_role", name="uq_message_read"),
    )

    # Relationships
    message: Mapped["ClientMessage"] = relationship(
        "ClientMessage",
        back_populates="read_receipts",
    )
