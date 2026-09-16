# app/models/task_file_link.py

"""
Task-to-document links.

A TaskFileLink records that a document is referenced by a task. The link is
a reference only; the document itself is never copied. Only CLIENT-type tasks
can carry file links because only CLIENT tasks belong to an engagement, which
is what scopes the picker and the access gate.

Unlinking is a real DELETE of the row. The link carries no content worth
preserving; if a document is trashed, its own deleted_at captures that state
and the link row stays (the spec says trashed files remain visible with a
label, not hidden). Soft-deleting the link itself would be indistinguishable
from the document being trashed, so it is never done.

UniqueConstraint on (task_id, document_id): the same file cannot be linked
twice to the same task. Linking twice is not an error (the service is
idempotent), but only one row may exist at the database level.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class TaskFileLink(Base):
    __tablename__ = "task_file_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes every query without a join to tasks.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # created_by is informational; SET NULL if the user is deactivated or
    # deleted so the link itself is not cascade-removed with the user.
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("task_id", "document_id", name="uq_task_file_link"),
    )
