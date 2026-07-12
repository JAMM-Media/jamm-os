# tests/test_spine_recheck.py

import uuid
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.core.enums import GateBar, GateStatus, SubjectType
from app.models.finding import Finding
from app.services.findings_recheck import recheck_failed_findings

FLOORS_BY_TECHNIQUE = {"anomaly": {"firms": 5, "observations": 100}}


def _make_finding(db, **overrides) -> Finding:
    defaults = dict(
        technique="anomaly",
        subject_type=SubjectType.pattern,
        subject_key=f"pattern-{uuid.uuid4()}",
        gate_bar=GateBar.firm_facing,
        gate_status=GateStatus.failed,
        statistics={"p_value": 0.5},
        data_sufficiency={"firms": 1, "observations": 5},
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


def test_recheck_flips_finding_that_now_clears_the_bar():
    db = TestingSessionLocal()
    try:
        finding = _make_finding(
            db,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 10, "observations": 200},
        )
        finding_id = finding.id
    finally:
        db.close()

    with patch("app.services.findings.log_event"), patch(
        "app.services.findings_recheck.SessionLocal", TestingSessionLocal
    ):
        recheck_failed_findings(FLOORS_BY_TECHNIQUE)

    db = TestingSessionLocal()
    try:
        updated = db.get(Finding, finding_id)
        assert updated.gate_status == GateStatus.passed
        assert updated.lifecycle_state.value == "indexed"
        assert updated.last_recheck_at is not None
    finally:
        db.close()


def test_recheck_leaves_still_failing_finding_failed_but_stamps_recheck():
    db = TestingSessionLocal()
    try:
        finding = _make_finding(
            db,
            statistics={"p_value": 0.9},
            data_sufficiency={"firms": 1, "observations": 5},
        )
        finding_id = finding.id
    finally:
        db.close()

    with patch("app.services.findings.log_event"), patch(
        "app.services.findings_recheck.SessionLocal", TestingSessionLocal
    ):
        recheck_failed_findings(FLOORS_BY_TECHNIQUE)

    db = TestingSessionLocal()
    try:
        updated = db.get(Finding, finding_id)
        assert updated.gate_status == GateStatus.failed
        assert updated.last_recheck_at is not None
    finally:
        db.close()


def test_recheck_touches_only_failed_rows_not_passed_rows():
    db = TestingSessionLocal()
    try:
        passed_finding = _make_finding(
            db,
            gate_status=GateStatus.passed,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 10, "observations": 200},
        )
        passed_id = passed_finding.id
    finally:
        db.close()

    with patch("app.services.findings.log_event"), patch(
        "app.services.findings_recheck.SessionLocal", TestingSessionLocal
    ):
        result = recheck_failed_findings(FLOORS_BY_TECHNIQUE)

    assert result["touched"] == 0

    db = TestingSessionLocal()
    try:
        untouched = db.get(Finding, passed_id)
        assert untouched.last_recheck_at is None
        assert untouched.gate_status == GateStatus.passed
    finally:
        db.close()
