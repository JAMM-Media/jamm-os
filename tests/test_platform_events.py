# tests/test_platform_events.py

"""Routing tests for finding events across the two log tables.

Ruling 1, Aug 26, 2026 closed the null-firm capture gap. A finding with a
firm fires a behavioral event; a finding with no firm fires a platform event.
Before this ruling the null-firm case fired nothing at all.

FIXTURE RULE, load bearing: every count in this file is scoped by
entity_id == finding.id, never by table total. Seven existing tests in
tests/test_spine_findings.py, tests/test_spine_confidence_gate.py and
tests/test_spine_recheck.py create null-firm findings and now write
platform_events rows as a side effect. A count of the whole table would be
polluted by them and could not fail for the right reason. Do not relax this
into a table count.
"""

import os
import uuid
from unittest.mock import MagicMock, patch

from tests.conftest import TestingSessionLocal
from app.core.enums import GateBar, GateStatus, SubjectType
from app.models.behavioral_event import BehavioralEvent
from app.models.finding import Finding
from app.models.firm import Firm
from app.models.platform_event import PlatformEvent
from app.services.behavioral_log import log_platform_event
from app.services.confidence_gate import judge_finding
from app.services.findings import create_or_update_finding


def _make_firm() -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Test Firm {uuid.uuid4()}", slug=f"test-firm-{uuid.uuid4()}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


def _make_finding(db, **overrides) -> Finding:
    """Builds a Finding directly, so no create event is fired for it."""
    defaults = dict(
        firm_id=None,
        technique="anomaly",
        subject_type=SubjectType.pattern,
        subject_key=f"pattern-{uuid.uuid4()}",
        gate_bar=GateBar.firm_facing,
        gate_status=GateStatus.pending,
        statistics={"p_value": 0.001},
        data_sufficiency={"n": 5},
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def _platform_rows_for(db, entity_id):
    return (
        db.query(PlatformEvent)
        .filter(PlatformEvent.entity_id == entity_id)
        .order_by(PlatformEvent.occurred_at)
        .all()
    )


def _behavioral_rows_for(db, entity_id):
    return (
        db.query(BehavioralEvent)
        .filter(BehavioralEvent.entity_id == entity_id)
        .order_by(BehavioralEvent.occurred_at)
        .all()
    )


# ---------------------------------------------------------------------------
# Routing: null firm goes to platform_events
# ---------------------------------------------------------------------------

def test_null_firm_finding_created_writes_platform_event_not_behavioral_event():
    db = TestingSessionLocal()
    try:
        with patch("app.services.behavioral_log.SessionLocal", TestingSessionLocal):
            finding = create_or_update_finding(
                db,
                technique="drift",
                firm_id=None,
                subject_type=SubjectType.pattern,
                subject_key=f"network-pattern-{uuid.uuid4()}",
                gate_bar=GateBar.internal,
                statistics={"n": 1},
            )

        platform_rows = _platform_rows_for(db, finding.id)
        assert len(platform_rows) == 1, (
            "expected exactly one platform_events row for this finding, found "
            f"{len(platform_rows)}. A null-firm finding must fire to "
            "platform_events; before Ruling 1 it fired nothing at all."
        )
        assert platform_rows[0].event_type == "finding.created"
        assert platform_rows[0].entity_type == "finding"
        assert platform_rows[0].entity_id == finding.id
        assert platform_rows[0].extra_metadata["technique"] == "drift"

        assert _behavioral_rows_for(db, finding.id) == [], (
            "a null-firm finding must never reach behavioral_events, whose "
            "firm_id is NOT NULL and stays that way under Ruling 1"
        )
    finally:
        db.close()


def test_null_firm_finding_judged_writes_gate_event_to_platform_events():
    db = TestingSessionLocal()
    try:
        # The floors live in a local dict, not the module registry: the
        # registry ships empty by design and Phase 2 keeps it that way.
        floors_by_technique = {"anomaly": {"n": 1}}

        finding = _make_finding(
            db,
            statistics={"p_value": 0.001},
            data_sufficiency={"n": 5},
        )

        with patch("app.services.behavioral_log.SessionLocal", TestingSessionLocal):
            updated = judge_finding(db, finding.id, floors_by_technique)

        assert updated.gate_status == GateStatus.passed

        platform_rows = _platform_rows_for(db, finding.id)
        assert len(platform_rows) == 1, (
            f"expected one gate event in platform_events, found {len(platform_rows)}"
        )
        assert platform_rows[0].event_type == "finding.gate_passed"
        assert platform_rows[0].entity_type == "finding"

        assert _behavioral_rows_for(db, finding.id) == []
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Routing: a firm-scoped finding still goes to behavioral_events only
# ---------------------------------------------------------------------------

def test_firm_scoped_finding_still_writes_behavioral_event_only():
    """Pins routing in the other direction.

    Without this, a change that sent everything to platform_events would keep
    the two null-firm tests above green while silently draining the
    firm-scoped behavioral stream.
    """
    firm_id = _make_firm()

    db = TestingSessionLocal()
    try:
        with patch("app.services.behavioral_log.SessionLocal", TestingSessionLocal):
            finding = create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=firm_id,
                subject_type=SubjectType.pattern,
                subject_key=f"firm-pattern-{uuid.uuid4()}",
                gate_bar=GateBar.firm_facing,
                statistics={"z_score": 1.0},
            )

        behavioral_rows = _behavioral_rows_for(db, finding.id)
        assert len(behavioral_rows) == 1, (
            f"expected one behavioral_events row, found {len(behavioral_rows)}"
        )
        assert behavioral_rows[0].event_type == "finding.created"
        assert behavioral_rows[0].firm_id == firm_id

        assert _platform_rows_for(db, finding.id) == [], (
            "a firm-scoped finding must never reach platform_events, which "
            "exists only for events that belong to no firm"
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Production-marker refusal
# ---------------------------------------------------------------------------

def test_log_platform_event_refuses_production_marker_under_testing():
    """Defense in depth, mirroring the check inside log_event().

    NOTE: tests/test_behavioral_log.py has no equivalent guard for log_event.
    That gap is recorded, not fixed here: log_event is outside this session's
    scope fence. This test covers log_platform_event only.
    """
    entity_id = uuid.uuid4()
    fake_settings = MagicMock()
    fake_settings.DATABASE_URL = "postgresql+psycopg://user:pw@db.ondigitalocean.com:25060/prod"

    session_factory = MagicMock()

    with patch.dict(os.environ, {"JAMM_TESTING": "1"}), patch(
        "app.services.behavioral_log.get_settings", return_value=fake_settings
    ), patch("app.services.behavioral_log.SessionLocal", session_factory):
        log_platform_event(
            event_type="finding.created",
            entity_type="finding",
            entity_id=entity_id,
        )

    session_factory.assert_not_called()

    db = TestingSessionLocal()
    try:
        assert _platform_rows_for(db, entity_id) == []
    finally:
        db.close()
