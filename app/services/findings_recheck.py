# app/services/findings_recheck.py

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.enums import GateStatus
from app.core.technique_floors import get_floors_by_technique
from app.db.session import SessionLocal
from app.models.finding import Finding
from app.services.confidence_gate import judge_finding

log = logging.getLogger(__name__)


def recheck_failed_findings(floors_by_technique: Optional[dict] = None) -> dict:
    """
    Weekly job. Queries findings WHERE gate_status = failed (served by the
    ix_findings_failed partial index), re-runs judge_finding on each, and
    stamps last_recheck_at on every row it touches regardless of outcome.

    floors_by_technique defaults to the Andrew-owned registry in
    app/core/technique_floors.py, read at call time so the value is always
    live. A caller passing an explicit dict, including an explicit empty {},
    overrides the registry and is honored as passed. The registry ships empty,
    so until a technique authors its floors every finding still fails closed
    via judge_finding's fail-closed rule. Ruling 2, Aug 26, 2026.

    Creates its own SessionLocal() in a try/finally block, per the
    background-task rule: never inherit the request session.
    """
    if floors_by_technique is None:
        floors_by_technique = get_floors_by_technique()

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
