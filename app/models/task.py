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

    # A CLIENT task is dual-keyed: it belongs to BOTH a client AND an
    # engagement. This is a core architectural decision documented in the
    # master instructions. Why? Because later features (invoicing, time
    # tracking, reporting) need to be able to ask both "show me all tasks for
    # this client" AND "show me all tasks in this engagement" efficiently,
    # without extra JOINs.
    #
    # Both are nullable ONLY to make room for INTERNAL tasks, which belong to
    # the firm and to no client or engagement at all. task_type is what says
    # which kind a row is; the nullability is a consequence of that, not an
    # invitation to create half-populated client tasks.
    #
    # The invariant (client => both set, internal => both null) is enforced in
    # app/services/task_service.py, via the TaskCreate validator. That is the
    # only path that VALIDATES the invariant, and the only one that fires
    # behavioral events, but it is not the only path that creates a task.
    # These three build a Task directly and are not checked by anything:
    #
    #   app/services/engagement_template_service.py
    #   app/services/esign_service.py
    #   app/services/recurring_engagement_service.py
    #
    # All three happen to satisfy the invariant today, because each sets both
    # client_id and engagement_id and leans on the task_type server default.
    # They are correct by habit rather than by enforcement, so anything added
    # to the rule in task_service will not reach them. Route new creation
    # paths through task_service.create_task.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=True,
    )
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=True,
    )

    # 'client' or 'internal'. Kept as a plain String to match every other
    # status-like column on this model (status, and Engagement.engagement_type),
    # with the allowed values expressed as the TaskType enum in
    # app/schemas/task.py.
    task_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
        server_default="client",
        index=True,
    )

    # Set once, at creation, from whether the creator assigned the task to
    # themselves. Deliberately NOT derived later by comparing a creator to
    # assigned_to: a reassignment would erase the original relationship and
    # the Employee Archive would silently change its mind about history.
    is_self_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="todo")
    due_date: Mapped[date | None] = mapped_column(Date)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
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
    client: Mapped["Client | None"] = relationship(back_populates="tasks")
    engagement: Mapped["Engagement | None"] = relationship(back_populates="tasks")
    assignee: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_to])
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="task")