# app/models/document_favorite.py
"""
DocumentFavorite: per-user bookmark for a Document or DocumentFolder.

item_id carries no FK constraint because it can reference either
documents.id or document_folders.id depending on item_type. This is
intentional -- a polymorphic reference without a DB-level FK.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class DocumentFavorite(Base):
    __tablename__ = "document_favorites"
    __table_args__ = (
        CheckConstraint(
            "item_type IN ('document', 'folder')",
            name="ck_document_favorites_item_type",
        ),
        UniqueConstraint(
            "user_id", "item_type", "item_id",
            name="uq_document_favorites_user_item",
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

    # 'document' or 'folder' -- enforced by ck_document_favorites_item_type.
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # No FK constraint -- references either documents.id or document_folders.id
    # depending on item_type (polymorphic reference).
    item_id: Mapped[uuid.UUID] = mapped_column(nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )
