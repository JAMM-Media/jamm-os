# app/services/confidence_gate.py

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.enums import FindingLifecycleState, GateBar, GateStatus
from app.core.intelligence_constants import (
    FIRM_FACING_SIGNIFICANCE_ALPHA,
    INTERNAL_SIGNIFICANCE_ALPHA,
    INTERNAL_SUFFICIENCY_FACTOR,
    SEVERITY_MODIFIER_CAP,
)
from app.models.finding import Finding
from app.services.findings import fire_finding_event


class GateResult(BaseModel):
    passed: bool
    sufficiency_passed: bool
    significance_passed: bool
    reason: Optional[str] = None


def _check_significance(finding: Finding) -> bool:
    is_internal = finding.gate_bar == GateBar.internal
    alpha = INTERNAL_SIGNIFICANCE_ALPHA if is_internal else FIRM_FACING_SIGNIFICANCE_ALPHA
    statistics = finding.statistics or {}
    p_value = statistics.get("p_value")
    return p_value is not None and p_value <= alpha


def _build_gate_result(sufficiency_passed: bool, significance_passed: bool, sufficiency_reason: str) -> GateResult:
    passed = sufficiency_passed and significance_passed

    reason = None
    if not passed:
        failed_checks = []
        if not sufficiency_passed:
            failed_checks.append(sufficiency_reason)
        if not significance_passed:
            failed_checks.append("significance")
        reason = "failed: " + " and ".join(failed_checks)

    return GateResult(
        passed=passed,
        sufficiency_passed=sufficiency_passed,
        significance_passed=significance_passed,
        reason=reason,
    )


def confidence_gate(finding: Finding, sufficiency_floors: dict) -> GateResult:
    """
    Evaluates data sufficiency against the floors and statistical
    significance against the alpha for the finding's gate_bar as two
    fully independent checks. Hard AND. One never borrows from the other.

    Floors arrive as a parameter because each technique owns its own
    floors (set in that technique's future build session). This function
    owns the STRUCTURE of the gate, not the technique-specific numbers.
    """
    is_internal = finding.gate_bar == GateBar.internal

    effective_floors = sufficiency_floors
    if is_internal:
        effective_floors = {
            key: floor * INTERNAL_SUFFICIENCY_FACTOR for key, floor in sufficiency_floors.items()
        }

    data_sufficiency = finding.data_sufficiency or {}
    sufficiency_passed = all(
        data_sufficiency.get(key, 0) >= floor for key, floor in effective_floors.items()
    )

    significance_passed = _check_significance(finding)

    return _build_gate_result(sufficiency_passed, significance_passed, "sufficiency")


def _compute_severity(finding: Finding) -> None:
    """
    Mutates finding.severity_modifiers and finding.severity_score in place.
    Only computes when severity_base_weight is present; otherwise severity
    stays null (the base-weight table is authored in a future session).
    Each modifier's raw value is capped at SEVERITY_MODIFIER_CAP before
    being multiplied in; both the raw and capped values are preserved.
    """
    if finding.severity_base_weight is None:
        finding.severity_score = None
        return

    raw_modifiers = finding.severity_modifiers or {}
    capped_modifiers: dict = {}
    product = Decimal("1")

    for name, value in raw_modifiers.items():
        raw_value = value["raw"] if isinstance(value, dict) else value
        raw_decimal = Decimal(str(raw_value))
        capped_decimal = min(raw_decimal, Decimal(str(SEVERITY_MODIFIER_CAP)))
        capped_modifiers[name] = {"raw": raw_value, "capped": float(capped_decimal)}
        product *= capped_decimal

    finding.severity_modifiers = capped_modifiers
    finding.severity_score = finding.severity_base_weight * product


_NO_FLOORS_REGISTERED = object()


def judge_finding(db: Session, finding_id: uuid.UUID, floors_by_technique: dict) -> Finding:
    """
    Loads the finding, runs confidence_gate, writes gate_status,
    failure_reason, gate_passed_at or gate_failed_at, sets lifecycle_state
    to indexed on pass, computes severity when severity_base_weight is
    present, and fires finding.gate_passed or finding.gate_failed.

    floors_by_technique is keyed by finding.technique. This is fail-closed
    by design, per the gate's hard-AND rule: a technique absent from this
    dict is NOT treated as "no floors" (which would vacuously pass
    sufficiency) — it fails sufficiency outright with a reason naming the
    unregistered technique. An empty {} floors dict for a technique that IS
    present is a deliberate, distinct choice from "not registered at all."
    Missing floors are never a pass.
    """
    finding = db.get(Finding, finding_id)

    floors = floors_by_technique.get(finding.technique, _NO_FLOORS_REGISTERED)
    if floors is _NO_FLOORS_REGISTERED:
        result = _build_gate_result(
            sufficiency_passed=False,
            significance_passed=_check_significance(finding),
            sufficiency_reason=f"no sufficiency floors registered for technique {finding.technique}",
        )
    else:
        result = confidence_gate(finding, floors)
    now = datetime.now(timezone.utc)

    if result.passed:
        finding.gate_status = GateStatus.passed
        finding.failure_reason = None
        finding.gate_passed_at = now
        finding.lifecycle_state = FindingLifecycleState.indexed
    else:
        finding.gate_status = GateStatus.failed
        finding.failure_reason = result.reason
        finding.gate_failed_at = now

    _compute_severity(finding)

    db.commit()
    db.refresh(finding)

    event_metadata = {
        "technique": finding.technique,
        "subject_type": finding.subject_type.value,
        "subject_key": finding.subject_key,
        "gate_bar": finding.gate_bar.value,
    }
    if not result.passed:
        event_metadata["failure_reason"] = finding.failure_reason

    event_type = "finding.gate_passed" if result.passed else "finding.gate_failed"
    fire_finding_event(finding, event_type, event_metadata)

    return finding
