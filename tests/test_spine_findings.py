# tests/test_spine_findings.py

import uuid
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from tests.conftest import TestingSessionLocal
from app.core.enums import BetterDirection, GateBar, GateStatus, SubjectType
from app.models.finding import Finding
from app.models.firm import Firm
from app.models.metric_registry import MetricRegistry
from app.schemas.finding import FindingCreate
from app.services.findings import create_or_update_finding, get_findings_for_firm


def _make_firm(name_prefix="Test Firm") -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"{name_prefix} {uuid.uuid4()}", slug=f"test-firm-{uuid.uuid4()}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


def _make_metric_registry_row(key="engagement_velocity") -> str:
    db = TestingSessionLocal()
    try:
        row = MetricRegistry(
            key=key,
            display_name="Engagement Velocity",
            unit="days",
            better_direction=BetterDirection.lower,
            benchmark_eligible=True,
            tier=1,
        )
        db.add(row)
        db.commit()
        return key
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fingerprint integrity at the DB level
# ---------------------------------------------------------------------------

def test_insert_metric_finding_with_existing_metric_key_succeeds():
    metric_key = _make_metric_registry_row()
    firm_id = _make_firm()

    db = TestingSessionLocal()
    try:
        finding = Finding(
            firm_id=firm_id,
            technique="correlation",
            subject_type=SubjectType.metric,
            subject_key=metric_key,
            metric_key=metric_key,
            gate_bar=GateBar.firm_facing,
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)
        assert finding.id is not None
        assert finding.gate_status == GateStatus.pending
    finally:
        db.close()


def test_insert_metric_finding_with_unknown_metric_key_rejected_by_fk():
    firm_id = _make_firm()

    db = TestingSessionLocal()
    try:
        finding = Finding(
            firm_id=firm_id,
            technique="correlation",
            subject_type=SubjectType.metric,
            subject_key="does_not_exist_in_registry",
            metric_key="does_not_exist_in_registry",
            gate_bar=GateBar.firm_facing,
        )
        db.add(finding)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_insert_metric_finding_with_null_metric_key_rejected_by_check_constraint():
    firm_id = _make_firm()

    db = TestingSessionLocal()
    try:
        finding = Finding(
            firm_id=firm_id,
            technique="correlation",
            subject_type=SubjectType.metric,
            subject_key="some_key",
            metric_key=None,
            gate_bar=GateBar.firm_facing,
        )
        db.add(finding)
        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_pydantic_validator_rejects_subject_key_mismatch_with_metric_key():
    with pytest.raises(ValidationError):
        FindingCreate(
            technique="correlation",
            subject_type=SubjectType.metric,
            subject_key="one_key",
            metric_key="a_different_key",
            gate_bar=GateBar.firm_facing,
        )


# ---------------------------------------------------------------------------
# Fingerprint upsert
# ---------------------------------------------------------------------------

def test_fingerprint_upsert_produces_one_row_with_updated_statistics():
    firm_id = _make_firm()

    db = TestingSessionLocal()
    try:
        with patch("app.services.findings.log_event") as mock_log_event:
            first = create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=firm_id,
                subject_type=SubjectType.pattern,
                subject_key="pattern-a",
                gate_bar=GateBar.firm_facing,
                statistics={"z_score": 1.0},
            )
            first.gate_status = GateStatus.passed
            db.commit()

            second = create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=firm_id,
                subject_type=SubjectType.pattern,
                subject_key="pattern-a",
                gate_bar=GateBar.firm_facing,
                statistics={"z_score": 2.5},
            )

        assert second.id == first.id

        rows = (
            db.query(Finding)
            .filter(Finding.technique == "anomaly", Finding.subject_key == "pattern-a")
            .all()
        )
        assert len(rows) == 1
        assert rows[0].statistics == {"z_score": 2.5}
        assert rows[0].gate_status == GateStatus.pending

        assert mock_log_event.call_count == 2
        event_types = [call.kwargs["event_type"] for call in mock_log_event.call_args_list]
        assert event_types == ["finding.created", "finding.recomputed"]
    finally:
        db.close()


def test_network_wide_findings_with_same_fingerprint_dedupe_via_coalesce_index():
    with patch("app.services.findings.log_event") as mock_log_event:
        db = TestingSessionLocal()
        try:
            first = create_or_update_finding(
                db,
                technique="drift",
                firm_id=None,
                subject_type=SubjectType.pattern,
                subject_key="network-pattern",
                gate_bar=GateBar.internal,
                statistics={"n": 1},
            )
            second = create_or_update_finding(
                db,
                technique="drift",
                firm_id=None,
                subject_type=SubjectType.pattern,
                subject_key="network-pattern",
                gate_bar=GateBar.internal,
                statistics={"n": 2},
            )
            assert second.id == first.id

            rows = (
                db.query(Finding)
                .filter(Finding.technique == "drift", Finding.subject_key == "network-pattern")
                .all()
            )
            assert len(rows) == 1
            assert rows[0].statistics == {"n": 2}

            # Null-firm findings never fire a behavioral event: behavioral_events.firm_id
            # is NOT NULL and there is no firm to attribute the event to.
            mock_log_event.assert_not_called()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_firm_scoped_query_excludes_other_firms_and_null_firm_rows():
    firm_a = _make_firm("Firm A")
    firm_b = _make_firm("Firm B")

    db = TestingSessionLocal()
    try:
        with patch("app.services.findings.log_event"):
            create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=firm_a,
                subject_type=SubjectType.pattern,
                subject_key="pattern-firm-a",
                gate_bar=GateBar.firm_facing,
            )
            create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=firm_b,
                subject_type=SubjectType.pattern,
                subject_key="pattern-firm-b",
                gate_bar=GateBar.firm_facing,
            )
            create_or_update_finding(
                db,
                technique="anomaly",
                firm_id=None,
                subject_type=SubjectType.pattern,
                subject_key="pattern-network-wide",
                gate_bar=GateBar.internal,
            )

        results = get_findings_for_firm(db, firm_a)

        assert len(results) == 1
        assert results[0].firm_id == firm_a
        assert all(row.firm_id is not None for row in results)
        assert all(row.firm_id == firm_a for row in results)
    finally:
        db.close()
