# app/services/surface_promotion.py

"""
The finding-promotion path: the second writer into surface_items.

It is fully inert today, and that is the point rather than an unfinished edge.
PROMOTION_SEVERITY_THRESHOLDS ships empty, and a technique absent from that
registry fails CLOSED: no threshold, no promotion, no row. Since no ML
technique exists yet, nothing can be promoted, so the Observatory is empty on
day one by construction rather than by an accident of data.

The contract this function will honour when techniques arrive:

  - A finding is promoted only if its technique has an authored severity
    threshold and the finding's severity_score meets it.
  - Only gated, firm-scoped findings are eligible. findings.firm_id is nullable
    because network-wide findings have no firm; surface_items.firm_id is not
    nullable, so a null-firm finding can never become a firm-scoped row.
  - The surface row ECHOES the finding, never leads it. Resolution for a
    finding-backed row is decided by the finding's own recheck cycle, and the
    daily job deliberately has no clear condition for such rows.
  - This build never modifies a Finding. Promotion reads one and writes a
    surface row. Dismissing the surface row does not touch the finding.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import GateStatus, SurfaceKind
from app.core.surface_constants import get_promotion_severity_thresholds
from app.models.finding import Finding
from app.models.surface_item import SurfaceItem

logger = logging.getLogger(__name__)


def promote_finding_to_observatory(
    db: Session,
    finding: Finding,
    thresholds: Optional[dict] = None,
) -> Optional[SurfaceItem]:
    """
    Write an Observatory row for a qualified finding, or refuse and return None.

    Returns None for every refusal rather than raising, because promotion is
    something the pipeline attempts speculatively over many findings: a finding
    that does not qualify is the normal case, not an error.

    thresholds is injectable so a test can prove both branches without editing
    the Andrew-owned registry, exactly as findings_recheck takes its floors.
    """
    if thresholds is None:
        thresholds = get_promotion_severity_thresholds()

    # Fail closed on the registry FIRST. While a technique is absent there is no
    # authored opinion about what severity means for it, and guessing one is
    # precisely what the ratchet rule forbids.
    threshold = thresholds.get(finding.technique)
    if threshold is None:
        logger.debug(
            "promotion refused: technique %r has no authored threshold",
            finding.technique,
        )
        return None

    # A network-wide finding has no firm to show it to.
    if finding.firm_id is None:
        logger.debug("promotion refused: finding %s has no firm", finding.id)
        return None

    if finding.gate_status != GateStatus.passed:
        logger.debug("promotion refused: finding %s has not passed the gate", finding.id)
        return None

    if finding.severity_score is None or finding.severity_score < threshold:
        logger.debug("promotion refused: finding %s below threshold", finding.id)
        return None

    row = SurfaceItem(
        firm_id=finding.firm_id,
        kind=SurfaceKind.observatory,
        finding_id=finding.id,
        item_type=finding.technique,
        dedup_key=str(finding.id),
        headline=f"{finding.technique} finding for {finding.subject_key}",
        payload={
            "finding_id": str(finding.id),
            "technique": finding.technique,
            "subject_type": str(finding.subject_type),
            "subject_key": finding.subject_key,
            "severity_score": str(finding.severity_score),
        },
        rank=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
