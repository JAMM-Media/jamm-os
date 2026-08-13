# app/models/lead_message.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class LeadMessage(Base):
    __tablename__ = "lead_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # null when sender_role is "lead" -- a prospect has no User account.
    # Matches the exact reasoning used for ClientMessage.sender_id being
    # nullable on the client side.
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # "staff" or "lead" -- matching the "staff"/"client" vocabulary of ClientMessage
    sender_role: Mapped[str] = mapped_column(String(30), nullable=False)

    body: Mapped[str] = mapped_column(Text, nullable=False)

    # Freeform source tag populated by the capture mechanism that creates the row.
    # e.g. "inbound_email", "staff_note", "form_reply". Not enforced as an enum
    # since the full set of sources is not yet finalized.
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Matching ClientMessage's exact pattern.
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Composite index on the primary query path -- matching ClientMessage's pattern.
    __table_args__ = (
        Index("ix_lead_messages_firm_lead", "firm_id", "lead_id"),
    )

    sender: Mapped["User"] = relationship(
        "User",
        foreign_keys=[sender_id],
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="messages")
