# tests/test_surface_promotion_and_ranking.py

"""The promotion stub's fail-closed contract, and the NULL-fee ranking law."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.enums import (
    GateBar,
    GateStatus,
    InvoiceStatus,
    SubjectType,
    SurfaceKind,
)
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.invoice import Invoice
from app.models.surface_item import SurfaceItem
from app.services.surface_daily_job import run_surface_generation_for_firm
from app.services.surface_generators import (
    ITEM_INVOICE_OVERDUE,
    ITEM_WORK_UNBILLED,
    rank_candidates,
)
from app.services.surface_promotion import promote_finding_to_observatory
from tests.conftest import TestingSessionLocal


class _Row:
    """Minimal stand-in carrying only what the ranking comparison reads."""

    def __init__(self, name, tier, time_urgency, magnitude):
        self.name = name
        self.tier = tier
        self.time_urgency = time_urgency
        self.magnitude = magnitude

    def __repr__(self):
        return self.name


# ---------------------------------------------------------------------------
# The NULL-fee law
# ---------------------------------------------------------------------------

def test_time_outranks_magnitude_within_a_tier():
    """Magnitude is a boost, never a creator. Time decides first."""
    older_unpriced = _Row("older_unpriced", 2, 30, None)
    newer_expensive = _Row("newer_expensive", 2, 5, Decimal("9000"))

    assert rank_candidates([newer_expensive, older_unpriced]) == [
        older_unpriced,
        newer_expensive,
    ]


def test_tier_one_outranks_tier_two_outright():
    tier_one = _Row("tier_one", 1, 1, None)
    tier_two = _Row("tier_two", 2, 99, Decimal("9000"))

    assert rank_candidates([tier_two, tier_one]) == [tier_one, tier_two]


def test_a_null_fee_is_not_treated_as_zero():
    """The assertion that separates a correct implementation from a plausible one.

    A zero magnitude is a real, small magnitude and loses the tiebreak to a
    larger one. A NULL magnitude is the ABSENCE of a boost: it gets no lift and
    no penalty, so the comparison stops at time and leaves the existing order
    alone.

    If NULL were quietly coerced to zero, these two cases would behave
    identically and the unpriced item would sink below the priced one. They
    must not.
    """
    priced = _Row("priced", 2, 10, Decimal("500"))
    zero = _Row("zero", 2, 10, Decimal("0"))
    unpriced = _Row("unpriced", 2, 10, None)

    # Zero is a magnitude, and it loses to a bigger one wherever it starts.
    assert rank_candidates([zero, priced]) == [priced, zero]
    assert rank_candidates([priced, zero]) == [priced, zero]

    # NULL is not a magnitude. It neither wins nor loses the tiebreak, so the
    # input order survives in BOTH directions. That symmetry is the proof: a
    # coerced zero could not produce it.
    assert rank_candidates([unpriced, priced]) == [unpriced, priced]
    assert rank_candidates([priced, unpriced]) == [priced, unpriced]


def test_null_fee_ranking_through_the_real_job(firm_a_owner):
    """End to end: an unpriced engagement ranks by time and does not crash.

    work_unbilled carries no magnitude, because no fee column exists on
    engagements at all. It still has to rank, and rank above a newer invoice.
    """
    firm_id = firm_a_owner["firm_id"]
    now = datetime.now(timezone.utc)

    db = TestingSessionLocal()
    try:
        client_row = Client(firm_id=firm_id, name="Ranking Client", email=f"{uuid4().hex[:8]}@x.com")
        db.add(client_row)
        db.commit()
        db.refresh(client_row)
        client_id = client_row.id

        engagement = Engagement(
            firm_id=firm_id,
            client_id=client_id,
            name="Unpriced completed work",
            status="completed",
            completed_at=now - timedelta(days=40),
        )
        db.add(engagement)

        db.add(Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number=f"INV-{uuid4().hex[:8]}",
            subtotal=Decimal("9000.00"),
            total_amount=Decimal("9000.00"),
            amount_paid=Decimal("0.00"),
            status=InvoiceStatus.sent,
            due_date=date.today() - timedelta(days=3),
        ))
        db.commit()
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        run_surface_generation_for_firm(db, firm_id)
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        rows = db.query(SurfaceItem).filter(
            SurfaceItem.firm_id == firm_id
        ).order_by(SurfaceItem.rank).all()
        ordered = [row.item_type for row in rows]
        unbilled = next(r for r in rows if r.item_type == ITEM_WORK_UNBILLED)
        assert unbilled.payload["rank_inputs"]["magnitude"] is None, (
            "an absent fee was recorded as something other than null"
        )
    finally:
        db.close()

    assert ordered.index(ITEM_WORK_UNBILLED) < ordered.index(ITEM_INVOICE_OVERDUE), (
        "the unpriced older item was outranked by a newer priced one"
    )


# ---------------------------------------------------------------------------
# The promotion stub
# ---------------------------------------------------------------------------

def _make_finding(db, firm_id, technique="some_technique", severity="9.9"):
    finding = Finding(
        firm_id=firm_id,
        technique=technique,
        # An entity-subject finding, so no metric_key is needed. metric_key is
        # an FK into metric_registry, and the table's check constraint only
        # demands one when subject_type is metric.
        subject_type=SubjectType.entity,
        subject_key=f"client:{uuid4()}",
        statistics={},
        data_sufficiency={},
        gate_bar=GateBar.firm_facing,
        gate_status=GateStatus.passed,
        severity_score=Decimal(severity),
        eligible_surfaces=["observatory"],
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def test_promotion_is_inert_because_the_registry_is_empty(firm_a_owner):
    """The shipped state: no technique has thresholds, so nothing promotes."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        finding = _make_finding(db, firm_id)
        result = promote_finding_to_observatory(db, finding)

        assert result is None
        assert db.query(SurfaceItem).filter(
            SurfaceItem.firm_id == firm_id
        ).count() == 0
    finally:
        db.close()


def test_promotion_fails_closed_for_an_unregistered_technique(firm_a_owner):
    """A technique absent from the registry writes no row, even injected.

    Injecting a populated registry proves the refusal is about THIS technique
    being absent rather than about the function being unable to write at all.
    The next test proves it can write, which is what makes this one meaningful.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        finding = _make_finding(db, firm_id, technique="unregistered_technique")
        result = promote_finding_to_observatory(
            db, finding, thresholds={"a_different_technique": Decimal("1.0")}
        )

        assert result is None
        assert db.query(SurfaceItem).count() == 0
    finally:
        db.close()


def test_promotion_writes_an_observatory_row_once_a_threshold_exists(firm_a_owner):
    """The positive control for the fail-closed tests above.

    Without this, "returns None" could mean the function is broken rather than
    correctly refusing, and every refusal test would pass against a stub that
    does nothing at all.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        finding = _make_finding(db, firm_id, technique="ready_technique", severity="7.5")
        result = promote_finding_to_observatory(
            db, finding, thresholds={"ready_technique": Decimal("5.0")}
        )

        assert result is not None
        assert result.kind == SurfaceKind.observatory
        assert result.finding_id == finding.id
        assert result.firm_id == finding.firm_id
    finally:
        db.close()


def test_promotion_refuses_a_finding_below_its_threshold(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        finding = _make_finding(db, firm_id, technique="ready_technique", severity="2.0")
        result = promote_finding_to_observatory(
            db, finding, thresholds={"ready_technique": Decimal("5.0")}
        )

        assert result is None
        assert db.query(SurfaceItem).count() == 0
    finally:
        db.close()


def test_promotion_refuses_a_null_firm_finding():
    """findings.firm_id is nullable for network-wide rows. surface_items is not.

    A network-wide finding has no firm to show it to, and promoting one would
    either violate the NOT NULL constraint or, worse, guess a firm.
    """
    db = TestingSessionLocal()
    try:
        finding = Finding(
            firm_id=None,
            technique="ready_technique",
            subject_type=SubjectType.pattern,
            subject_key="network_wide_pattern",
            statistics={},
            data_sufficiency={},
            gate_bar=GateBar.firm_facing,
            gate_status=GateStatus.passed,
            severity_score=Decimal("9.9"),
            eligible_surfaces=["observatory"],
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)

        result = promote_finding_to_observatory(
            db, finding, thresholds={"ready_technique": Decimal("1.0")}
        )

        assert result is None
        assert db.query(SurfaceItem).count() == 0
    finally:
        db.close()


def test_promotion_refuses_a_finding_that_has_not_passed_the_gate(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        finding = _make_finding(db, firm_id, technique="ready_technique")
        finding.gate_status = GateStatus.pending
        db.commit()

        result = promote_finding_to_observatory(
            db, finding, thresholds={"ready_technique": Decimal("1.0")}
        )

        assert result is None
    finally:
        db.close()
