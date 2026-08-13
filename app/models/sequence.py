# app/models/sequence.py

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, Integer, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import StepType


class Sequence(Base):
    __tablename__ = "sequences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Nullable at creation -- a brand-new Sequence has no version yet.
    # Uses use_alter=True to break the circular FK dependency between
    # sequences and sequence_versions (each references the other).
    current_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sequence_versions.id", ondelete="SET NULL", use_alter=True, name="fk_sequences_current_version_id"),
        nullable=True,
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

    firm: Mapped["Firm"] = relationship("Firm", back_populates="sequences")

    versions: Mapped[list["SequenceVersion"]] = relationship(
        "SequenceVersion",
        back_populates="sequence",
        cascade="all, delete-orphan",
        foreign_keys="SequenceVersion.sequence_id",
    )


class SequenceVersion(Base):
    __tablename__ = "sequence_versions"

    __table_args__ = (
        UniqueConstraint("sequence_id", "version_number", name="uq_sequence_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    sequence_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Matches AutomationRule.preset_key: nullable String, indexed.
    # Records which preset lineage this version was generated from, never cleared.
    preset_lineage_key: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Bare FK only -- nothing needs to traverse creator yet.
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # NO updated_at -- SequenceVersion is genuinely immutable after creation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    sequence: Mapped["Sequence"] = relationship(
        "Sequence",
        back_populates="versions",
        foreign_keys=[sequence_id],
    )

    steps: Mapped[list["Step"]] = relationship(
        "Step",
        back_populates="version",
        cascade="all, delete-orphan",
    )


class Step(Base):
    __tablename__ = "sequence_steps"

    __table_args__ = (
        UniqueConstraint("sequence_version_id", "step_key", name="uq_step_version_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    sequence_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Preserves the real tree's own node IDs (T1, 22, R1, etc.)
    step_key: Mapped[str] = mapped_column(String(50), nullable=False)

    step_type: Mapped[StepType] = mapped_column(
        sa.Enum(StepType, name="steptype", native_enum=False),
        nullable=False,
    )

    # SMS seam from contract Section 6.8 -- always "email" today.
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="email",
        server_default="email",
    )

    # Freeform, matches the real tree's own phase labels.
    phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    is_modified_from_preset: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # Type-specific config; shape is not enforced at the DB level.
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # NO updated_at -- immutable after creation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    version: Mapped["SequenceVersion"] = relationship(
        "SequenceVersion",
        back_populates="steps",
    )


class StepEdge(Base):
    __tablename__ = "sequence_step_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Bare FKs only -- nothing needs to traverse edges from a step yet.
    from_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    to_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Freeform: "yes", "no", "timeout", "loop", etc.
    condition_label: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Only set on edges that loop back to an earlier step.
    loop_cap: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # NO updated_at -- immutable after creation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SequenceGoal(Base):
    __tablename__ = "sequence_goals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Bare FK -- goals are looked up via version, nothing traverses from goal outward.
    sequence_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Matches behavioral event type strings: "lead.call_booked", etc.
    goal_event: Mapped[str] = mapped_column(String(100), nullable=False)

    # Bare FK -- nothing needs to traverse from goal to target step yet.
    target_step_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sequence_steps.id"),
        nullable=False,
    )

    # Null means the goal applies across the whole version, not one phase.
    applies_to_phase: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # NO updated_at -- immutable after creation.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
