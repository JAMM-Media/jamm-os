# app/models/recent_document_view.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class RecentDocumentView(Base):
    """
    One row per (user, document) pair recording the most recent time that
    user accessed the document via preview or download.

    Updated on each qualifying interaction rather than accumulating a log --
    this is a fast-read projection for the "recent files" UI, not an audit
    trail. Full history lives in the audit log table.

    Scoped to a single engagement so the recent list is engagement-specific,
    matching the per-user, per-engagement design decision confirmed in the
    task specification.
    """

    __tablename__ = "recent_document_views"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", name="uq_recent_view_user_document"),
        Index(
            "ix_recent_document_views_firm_user_eng_ts",
            "firm_id",
            "user_id",
            "engagement_id",
            "last_viewed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    last_viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
