# app/models/document_request_template.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Integer, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class DocumentRequestTemplate(Base):
    __tablename__ = "document_request_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False
    )
    engagement_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    title_default: Mapped[Optional[str]] = mapped_column(
        String(300), nullable=True
    )
    # JSON list of objects: [{"label": str, "is_required": bool}]
    items: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    use_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    firm: Mapped["Firm"] = relationship(
        "Firm", back_populates="document_request_templates"
    )
