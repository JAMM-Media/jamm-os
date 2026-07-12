# app/models/finding.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import FindingLifecycleState, GateBar, GateStatus, SubjectType
from app.db.base_class import Base


class Finding(Base):
    """
    The standardized finding object. firm_id is NULLABLE on this table only:
    network-wide findings (cross-firm correlations) have no firm. Every
    firm-scoped query against this table must still filter firm_id to the
    requesting firm, and null-firm rows must never be returned by any
    firm-scoped query. This exception is deliberate and approved.
    """

    __tablename__ = "findings"

    __table_args__ = (
        CheckConstraint(
            "subject_type != 'metric' OR metric_key IS NOT NULL",
            name="ck_findings_metric_requires_metric_key",
        ),
        Index(
            "uq_findings_fingerprint",
            "technique",
            text("COALESCE(firm_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            "subject_type",
            "subject_key",
            unique=True,
        ),
        Index(
            "ix_findings_failed",
            "last_recheck_at",
            postgresql_where=text("gate_status = 'failed'"),
        ),
        Index(
            "ix_findings_passed",
            "firm_id",
            "severity_score",
            postgresql_where=text("gate_status = 'passed'"),
        ),
    )

    # --- Identity (the fingerprint) -----------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    technique: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    subject_type: Mapped[SubjectType] = mapped_column(
        sa.Enum(SubjectType, native_enum=False), nullable=False
    )

    subject_key: Mapped[str] = mapped_column(String(255), nullable=False)

    metric_key: Mapped[Optional[str]] = mapped_column(
        String(100),
        ForeignKey("metric_registry.key"),
        nullable=True,
    )

    # --- Statistics and judgment ---------------------------------------
    statistics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    data_sufficiency: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    confidence_tier: Mapped[Optional[int]] = mapped_column(nullable=True)

    gate_bar: Mapped[GateBar] = mapped_column(sa.Enum(GateBar, native_enum=False), nullable=False)
    gate_status: Mapped[GateStatus] = mapped_column(
        sa.Enum(GateStatus, native_enum=False),
        nullable=False,
        default=GateStatus.pending,
        index=True,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Severity (auditable components, never just the final number) --
    severity_base_weight: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)
    severity_modifiers: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    severity_score: Mapped[Optional[Decimal]] = mapped_column(Numeric, nullable=True)

    # --- Lifecycle -------------------------------------------------------
    lifecycle_state: Mapped[Optional[FindingLifecycleState]] = mapped_column(
        sa.Enum(FindingLifecycleState, native_enum=False), nullable=True
    )

    gate_passed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gate_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_recheck_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    surfaced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    displaced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Routing and composition ------------------------------------------
    eligible_surfaces: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Inert this session. No logic reads or writes it. Exists so the future
    # composition build needs no migration.
    composite_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("findings.id"),
        nullable=True,
    )

    # --- Standard spine ----------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
