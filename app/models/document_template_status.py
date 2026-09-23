# app/models/document_template_status.py
"""
DocumentTemplateStatus: lifecycle state for a Firm Library template item.

item_id carries no FK constraint because it can reference either
documents.id or document_folders.id depending on item_type. This is
intentional -- a polymorphic reference without a DB-level FK.

An item not present in this table is an ordinary client document and
is never part of the template lifecycle.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TemplateStatus
from app.db.base_class import Base


class DocumentTemplateStatus(Base):
    __tablename__ = "document_template_statuses"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('document', 'folder')",
            name="ck_document_template_statuses_item_type",
        ),
        UniqueConstraint(
            "firm_id", "item_type", "item_id",
            name="uq_document_template_statuses_firm_item",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'document' or 'folder' -- enforced by ck_document_template_statuses_item_type.
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # No FK constraint -- references either documents.id or document_folders.id
    # depending on item_type (polymorphic reference).
    item_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    status: Mapped[TemplateStatus] = mapped_column(
        sa.Enum(TemplateStatus, native_enum=False, length=30),
        nullable=False,
        default=TemplateStatus.vendor_sample,
    )

    # Set when moved to firm_approved; preserved on revert_to_draft for audit.
    published_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )