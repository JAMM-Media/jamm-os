# tests/test_spine_confidence_gate.py

import uuid
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.core.enums import FindingLifecycleState, GateBar, GateStatus, SubjectType
from app.models.finding import Finding
from app.models.firm import Firm
from app.services.confidence_gate import confidence_gate, judge_finding

SUFFICIENCY_FLOORS = {"firms": 5, "observations": 100}


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


def _make_synthetic_finding(db, firm_id=None, **overrides) -> Finding:
    defaults = dict(
        firm_id=firm_id,
        technique="anomaly",
        subject_type=SubjectType.pattern,
        subject_key=f"pattern-{uuid.uuid4()}",
        gate_bar=GateBar.firm_facing,
        statistics={"p_value": 0.001},
        data_sufficiency={"firms": 10, "observations": 200},
    )
    defaults.update(overrides)
    finding = Finding(**defaults)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    return finding


# ---------------------------------------------------------------------------
# confidence_gate() structure
# ---------------------------------------------------------------------------

def test_passes_both_checks_sets_passed_indexed_and_fires_event():
    firm_id = _make_firm()
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            firm_id=firm_id,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 10, "observations": 200},
            gate_bar=GateBar.firm_facing,
        )

        with patch("app.services.findings.log_event") as mock_log_event:
            result = confidence_gate(finding, SUFFICIENCY_FLOORS)
            assert result.passed is True
            assert result.sufficiency_passed is True
            assert result.significance_passed is True
            assert result.reason is None

            updated = judge_finding(db, finding.id, {"anomaly": SUFFICIENCY_FLOORS})

        assert updated.gate_status == GateStatus.passed
        assert updated.lifecycle_state == FindingLifecycleState.indexed
        assert updated.gate_passed_at is not None
        mock_log_event.assert_called_once()
        assert mock_log_event.call_args.kwargs["event_type"] == "finding.gate_passed"
    finally:
        db.close()


def test_fails_sufficiency_only_reason_names_sufficiency():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 1, "observations": 5},
            gate_bar=GateBar.firm_facing,
        )
        result = confidence_gate(finding, SUFFICIENCY_FLOORS)

        assert result.passed is False
        assert result.sufficiency_passed is False
        assert result.significance_passed is True
        assert "sufficiency" in result.reason
        assert "significance" not in result.reason
    finally:
        db.close()


def test_fails_significance_only_reason_names_significance():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            statistics={"p_value": 0.5},
            data_sufficiency={"firms": 10, "observations": 200},
            gate_bar=GateBar.firm_facing,
        )
        result = confidence_gate(finding, SUFFICIENCY_FLOORS)

        assert result.passed is False
        assert result.sufficiency_passed is True
        assert result.significance_passed is False
        assert "significance" in result.reason
        assert "sufficiency" not in result.reason
    finally:
        db.close()


def test_fails_both_reason_names_both():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            statistics={"p_value": 0.5},
            data_sufficiency={"firms": 1, "observations": 5},
            gate_bar=GateBar.firm_facing,
        )
        result = confidence_gate(finding, SUFFICIENCY_FLOORS)

        assert result.passed is False
        assert result.sufficiency_passed is False
        assert result.significance_passed is False
        assert "sufficiency" in result.reason
        assert "significance" in result.reason
    finally:
        db.close()


def test_internal_bar_passes_finding_firm_facing_bar_fails():
    db = TestingSessionLocal()
    try:
        # p_value 0.03: above FIRM_FACING alpha (0.01) so firm_facing fails,
        # below INTERNAL alpha (0.05) so internal passes. Sufficiency is
        # generously satisfied for both bars so only significance differs.
        stats = {"p_value": 0.03}
        sufficiency = {"firms": 10, "observations": 200}

        firm_facing_finding = _make_synthetic_finding(
            db, statistics=stats, data_sufficiency=sufficiency, gate_bar=GateBar.firm_facing
        )
        internal_finding = _make_synthetic_finding(
            db, statistics=stats, data_sufficiency=sufficiency, gate_bar=GateBar.internal
        )

        firm_facing_result = confidence_gate(firm_facing_finding, SUFFICIENCY_FLOORS)
        internal_result = confidence_gate(internal_finding, SUFFICIENCY_FLOORS)

        assert firm_facing_result.passed is False
        assert internal_result.passed is True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Severity computation
# ---------------------------------------------------------------------------

def test_severity_stays_null_when_base_weight_is_null():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 10, "observations": 200},
            severity_base_weight=None,
            severity_modifiers={"some_modifier": 3},
        )
        with patch("app.services.findings.log_event"):
            updated = judge_finding(db, finding.id, {"anomaly": SUFFICIENCY_FLOORS})

        assert updated.severity_score is None
    finally:
        db.close()


def test_severity_computes_with_modifiers_capped_at_two():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            statistics={"p_value": 0.001},
            data_sufficiency={"firms": 10, "observations": 200},
            severity_base_weight=10,
            severity_modifiers={"volume_spike": 10},
        )
        with patch("app.services.findings.log_event"):
            updated = judge_finding(db, finding.id, {"anomaly": SUFFICIENCY_FLOORS})

        assert float(updated.severity_score) == 20.0
        assert updated.severity_modifiers["volume_spike"]["raw"] == 10
        assert updated.severity_modifiers["volume_spike"]["capped"] == 2.0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fail-closed on unregistered technique floors
# ---------------------------------------------------------------------------

def test_unregistered_technique_stays_failed_even_when_statistics_would_clear_any_bar():
    db = TestingSessionLocal()
    try:
        finding = _make_synthetic_finding(
            db,
            technique="totally_unregistered_technique",
            # p_value of 0 clears both the firm_facing (0.01) and internal
            # (0.05) significance alphas — statistics alone would pass.
            statistics={"p_value": 0.0},
            data_sufficiency={"firms": 10_000, "observations": 10_000_000},
            gate_bar=GateBar.firm_facing,
        )

        with patch("app.services.findings.log_event"):
            # floors_by_technique has entries for other techniques, but not
            # this finding's technique — must fail closed, not vacuously pass.
            updated = judge_finding(db, finding.id, {"anomaly": SUFFICIENCY_FLOORS})

        assert updated.gate_status == GateStatus.failed
        assert "no sufficiency floors registered for technique totally_unregistered_technique" in updated.failure_reason
    finally:
        db.close()
