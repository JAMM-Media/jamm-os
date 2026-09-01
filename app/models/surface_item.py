# app/models/surface_item.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DismissalReason, SurfaceKind
from app.db.base_class import Base


class SurfaceItem(Base):
    """
    One row shown to a firm owner on a curated surface.

    Everything on the Morning Briefing and in the Observatory lives in this
    one table. Two writers feed it: the daily rule-based generators (rows with
    finding_id NULL) and the finding-promotion path (rows carrying finding_id,
    inert while the promotion registry ships empty).

    The division of labour against the findings ledger is absolute. The
    findings table holds the EPISTEMIC lifecycle: does the pattern still hold.
    This table holds the PRESENTATION lifecycle: shown, dismissed,
    implemented, resolved. The agenda never edits the workpapers, so nothing
    in this module or its services ever writes to a Finding.

    Where a row is finding-backed, its resolved_at ECHOES the finding's own
    recheck cycle and never leads it.

    Operational truth lives in these columns, written inside the request
    transaction. The behavioral event log only ever echoes them afterwards,
    fire and forget. No generator, endpoint, or job reads behavioral_events to
    make a decision about a row.
    """

    __tablename__ = "surface_items"

    __table_args__ = (
        # One live row per condition instance, per surface. A row stops being
        # the live representative of its condition only when it resolves, so
        # the predicate is resolved_at IS NULL and nothing else.
        #
        # This is deliberately wider than "currently displayed". A row that
        # was dismissed not_relevant or was_wrong is unresolved forever, so it
        # keeps blocking new rows for the same condition, which is exactly the
        # ruled behavior that those two reasons never resurface. A row
        # dismissed already_handling, or marked implemented, is likewise still
        # live: its suppression window expires and the same row comes back
        # rather than a duplicate being written beside it.
        #
        # Declared on the model, not only in the migration, because
        # tests/conftest.py builds the test database with create_all(). An
        # index that exists only in a migration would be absent from every
        # test run, and the rule it enforces would be untested by
        # construction. A scratch-database guard proves the migrated world
        # agrees with this declaration.
        Index(
            "uq_surface_items_open_condition",
            "firm_id",
            "kind",
            "item_type",
            "dedup_key",
            unique=True,
            postgresql_where=text("resolved_at IS NULL"),
        ),
        # Minimum required index: every read is firm-scoped and surface-scoped.
        Index("ix_surface_items_firm_kind", "firm_id", "kind"),
        # Serving and ranking. The daily job ranks and slots unresolved rows,
        # and both surfaces read them back in rank order.
        Index(
            "ix_surface_items_firm_kind_rank",
            "firm_id",
            "kind",
            "rank",
            postgresql_where=text("resolved_at IS NULL"),
        ),
        # Echo lookups: find the surface rows belonging to a finding when its
        # own recheck cycle resolves it.
        Index("ix_surface_items_finding", "finding_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    kind: Mapped[SurfaceKind] = mapped_column(
        sa.Enum(SurfaceKind, native_enum=False),
        nullable=False,
    )

    # NULL for the rule-based generators. Set only by the promotion path.
    #
    # RESTRICT rather than SET NULL: a deleted finding must not silently turn
    # a promoted row into something indistinguishable from a rule-based row.
    # Findings are never deleted in normal operation; they archive.
    #
    # findings.firm_id is nullable because network-wide findings have no firm.
    # firm_id on THIS table is not nullable, so a null-firm finding can never
    # be promoted into a firm-scoped row. The promotion path refuses them.
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("findings.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # The generator key today (invoice_overdue, irs_auth_expiring, and the
    # rest), a technique key once promotion is live.
    item_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Identifies the underlying condition instance, for example the invoice id
    # for invoice_overdue, so the same condition never produces duplicate
    # live rows. Scoped by firm, kind and item_type in the unique index above.
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False)

    headline: Mapped[str] = mapped_column(String(500), nullable=False)

    # Structured facts the frontend renders: numbers, delta shapes, resolved
    # outcome copy. none_as_null so an assigned Python None becomes SQL NULL
    # rather than a stored JSON null, which is present-but-null and defeats
    # ordinary existence checks.
    payload: Mapped[dict] = mapped_column(
        JSONB(none_as_null=True),
        nullable=False,
        default=dict,
    )

    # Recomputed by the daily job. Lower sorts first.
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # Briefing display membership. NULL means active but not slotted.
    slotted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counts briefing APPEARANCES (times served), not calendar days.
    # last_served_on makes the increment idempotent within a day.
    appearance_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_served_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[Optional[DismissalReason]] = mapped_column(
        sa.Enum(DismissalReason, native_enum=False),
        nullable=True,
    )

    implemented_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Set by already_handling and by mark_implemented, counted from the click.
    suppressed_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Snapshot of the measured values at action time, used to compute the
    # delta copy when a suppression window expires. Reading history back out
    # of the behavioral log is forbidden; this column is why it is never
    # needed. none_as_null for the same reason as payload.
    value_at_action: Mapped[Optional[dict]] = mapped_column(
        JSONB(none_as_null=True),
        nullable=True,
    )

    # Set by was_wrong. There is no review UI in this build.
    flagged_for_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
