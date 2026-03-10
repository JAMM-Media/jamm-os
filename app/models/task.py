# app/models/task.py

import uuid
from datetime import datetime, date, timezone

from sqlalchemy import String, Boolean, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes this task to one accounting firm.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Tasks are dual-keyed: they belong to BOTH a client AND an engagement.
    # This is a core architectural decision documented in the master instructions.
    # Why? Because later features (invoicing, time tracking, reporting) need
    # to be able to ask both "show me all tasks for this client" AND
    # "show me all tasks in this engagement" efficiently, without extra JOINs.
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="todo")
    due_date: Mapped[date | None] = mapped_column(Date)
    assigned_to: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

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

    firm: Mapped["Firm"] = relationship("Firm", back_populates="tasks")
    client: Mapped["Client"] = relationship(back_populates="tasks")
    engagement: Mapped["Engagement"] = relationship(back_populates="tasks")