# app/models/engagement_template.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Text, Integer, JSON, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base



class EngagementTemplate(Base):
    __tablename__ = "engagement_templates"

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
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    engagement_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    estimated_hours: Mapped[Optional[float]] = mapped_column(
        Numeric(6, 2), nullable=True
    )
    # JSON array of task template objects: [{ title, description, order }]
    task_templates: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    # JSON array of document request item strings: ["W-2", "1099-INT", ...]
    document_checklist: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    use_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    is_recurring: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    recurrence_cadence: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    recurrence_day: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    recurrence_month: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    recurrence_advance_days: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=14
    )
    last_spawned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
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
        "Firm", back_populates="engagement_templates"
    )
