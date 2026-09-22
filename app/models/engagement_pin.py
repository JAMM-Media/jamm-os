# app/models/engagement_pin.py
"""
EngagementPin: shared curated link to a Document or DocumentFolder,
scoped to one engagement, visible to all engagement members, mutable
only by engagement administrators, managers, and firm owners.

item_id carries no FK constraint because it can reference either
documents.id or document_folders.id depending on item_type. This is
intentional -- a polymorphic reference without a DB-level FK.

Capped at 5 pins per engagement (PIN_CAP) by the service layer.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class EngagementPin(Base):
    __tablename__ = "engagement_pins"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('document', 'folder')",
            name="ck_engagement_pins_item_type",
        ),
        UniqueConstraint(
            "engagement_id", "item_type", "item_id",
            name="uq_engagement_pins_engagement_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'document' or 'folder' -- enforced by ck_engagement_pins_item_type.
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # No FK constraint -- references either documents.id or document_folders.id
    # depending on item_type (polymorphic reference).
    item_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    # Who pinned the item -- for display and audit, not for access control.
    # SET NULL preserves the pin record if the user account is later deleted.
    pinned_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
