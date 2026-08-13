# app/models/enrollment.py

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import EnrollmentStatus


class Enrollment(Base):
    __tablename__ = "enrollments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Denormalized from lead for direct tenant-scoped queries -- matching
    # how firm_id is handled on every other model rather than joining through Lead.
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

    # Denormalized from sequence_version_id at creation time.
    # Required for the partial unique index that enforces no-duplicate-concurrent-enrollment
    # at the SEQUENCE level (not version level), since a lead should not be enrolled
    # twice in the same sequence even across two different versions of it.
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The real pin -- set at enrollment, never changed even if the sequence is later edited.
    sequence_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable only in the brief instant between creation and first step assignment.
    current_step_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sequence_steps.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Null means no pending scheduled action (stopped, or waiting on an event with no timer).
    next_action_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[EnrollmentStatus] = mapped_column(
        sa.Enum(EnrollmentStatus, name="enrollmentstatus", native_enum=False),
        nullable=False,
        default=EnrollmentStatus.active,
        server_default="active",
    )

    # Keyed by loop identifier, incremented by future step-execution logic.
    # Checked against StepEdge.loop_cap before following a loop edge.
    loop_counts: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Set when status leaves active.
    stopped_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Enrollment is real mutable state -- it DOES get updated_at, unlike
    # the immutable Task 1 models (SequenceVersion, Step, StepEdge, SequenceGoal).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Nullable -- generated at email-send time, not at enrollment creation.
    # SHA-256 hex digest (64 chars). Raw token only exists transiently in email link.
    # Follows the exact same pattern as PortalSession.magic_link_token_hash.
    unsubscribe_token_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    unsubscribe_token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    lead: Mapped["Lead"] = relationship("Lead", back_populates="enrollments")
