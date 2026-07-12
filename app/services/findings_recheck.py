# app/services/findings_recheck.py

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.enums import GateStatus
from app.db.session import SessionLocal
from app.models.finding import Finding
from app.services.confidence_gate import judge_finding

log = logging.getLogger(__name__)


def recheck_failed_findings(floors_by_technique: Optional[dict] = None) -> dict:
    """
    Weekly job. Queries findings WHERE gate_status = failed (served by the
    ix_findings_failed partial index), re-runs judge_finding on each, and
    stamps last_recheck_at on every row it touches regardless of outcome.

    floors_by_technique defaults to {} — today no technique has authored
    its floors yet, so every finding fails closed via judge_finding's
    fail-closed rule (a technique absent from the dict never passes
    sufficiency).

    The scheduler (app/main.py) currently invokes this with no floors
    argument at all, so every scheduled recheck run defaults to an empty
    floors_by_technique and fails every finding it touches closed. Wiring
    a real floors source into this job is a BLOCKING precondition of the
    first technique build, alongside the floor registry design itself.

    Creates its own SessionLocal() in a try/finally block, per the
    background-task rule: never inherit the request session.
    """
    floors_by_technique = floors_by_technique if floors_by_technique is not None else {}

    db = SessionLocal()
    try:
        failed_ids = [
            row.id
            for row in db.query(Finding.id).filter(Finding.gate_status == GateStatus.failed).all()
        ]

        touched = 0
        for finding_id in failed_ids:
            finding = judge_finding(db, finding_id, floors_by_technique)
            finding.last_recheck_at = datetime.now(timezone.utc)
            db.commit()
            touched += 1

        log.info("findings_recheck.recheck_failed_findings: touched %s findings", touched)
        return {"touched": touched}
    finally:
        db.close()
