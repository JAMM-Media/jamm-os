# app/services/findings.py

import logging
import os
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app.core.enums import GateBar, GateStatus, SubjectType
from app.models.finding import Finding
from app.services.behavioral_log import log_event

log = logging.getLogger(__name__)


def fire_finding_event_if_firm_scoped(finding: Finding, event_type: str, metadata: dict) -> None:
    """
    behavioral_events.firm_id is a NOT NULL FK to firms.id, so a null-firm
    (network-wide) finding has no firm to attribute the event to and the
    event is skipped entirely.

    KNOWN CAPTURE GAP: network-wide findings currently generate zero
    behavioral signal. Resolving this is a BLOCKING PRECONDITION of the
    correlation engine build (the first technique expected to produce
    null-firm findings in volume) — that session must decide between
    widening behavioral_events.firm_id to nullable or standing up a
    separate platform-wide event stream. Deliberately deferred, not an
    oversight.
    """
    if finding.firm_id is not None:
        log_event(
            event_type=event_type,
            firm_id=finding.firm_id,
            entity_type="finding",
            entity_id=finding.id,
            metadata=metadata,
        )
        return

    if os.environ.get("JAMM_TESTING") != "1":
        log.error(
            "findings.null_firm_event_skipped: %s fired for finding %s with no firm_id; "
            "behavioral signal was dropped pending the correlation engine session's "
            "capture-gap decision",
            event_type,
            finding.id,
        )


def create_or_update_finding(
    db: Session,
    *,
    technique: str,
    firm_id: Optional[uuid.UUID],
    subject_type: SubjectType,
    subject_key: str,
    gate_bar: GateBar,
    metric_key: Optional[str] = None,
    statistics: Optional[dict] = None,
    data_sufficiency: Optional[dict] = None,
) -> Finding:
    """
    Fingerprint upsert keyed on (technique, firm_id, subject_type, subject_key).
    Inserts with gate_status pending, or on an existing fingerprint match,
    updates statistics/data_sufficiency and resets gate_status to pending
    for re-judgment. Fires finding.created on insert, finding.recomputed on
    update, for firm-scoped findings only (see fire_finding_event_if_firm_scoped
    for the null-firm capture gap).
    """
    if subject_type == SubjectType.metric and subject_key != metric_key:
        raise ValueError("subject_key must equal metric_key when subject_type is metric")

    statistics = statistics if statistics is not None else {}
    data_sufficiency = data_sufficiency if data_sufficiency is not None else {}

    query = db.query(Finding).filter(
        Finding.technique == technique,
        Finding.subject_type == subject_type,
        Finding.subject_key == subject_key,
    )
    query = query.filter(Finding.firm_id.is_(None)) if firm_id is None else query.filter(
        Finding.firm_id == firm_id
    )
    existing = query.first()

    event_metadata = {
        "technique": technique,
        "subject_type": subject_type.value,
        "subject_key": subject_key,
        "gate_bar": gate_bar.value,
    }

    if existing is not None:
        existing.statistics = statistics
        existing.data_sufficiency = data_sufficiency
        existing.gate_status = GateStatus.pending
        db.commit()
        db.refresh(existing)

        fire_finding_event_if_firm_scoped(existing, "finding.recomputed", event_metadata)
        return existing

    finding = Finding(
        technique=technique,
        firm_id=firm_id,
        subject_type=subject_type,
        subject_key=subject_key,
        metric_key=metric_key,
        gate_bar=gate_bar,
        statistics=statistics,
        data_sufficiency=data_sufficiency,
        gate_status=GateStatus.pending,
    )
    db.add(finding)
    db.commit()
    db.refresh(finding)

    fire_finding_event_if_firm_scoped(finding, "finding.created", event_metadata)
    return finding


def get_findings_for_firm(db: Session, firm_id: uuid.UUID) -> list[Finding]:
    """
    Firm-scoped query helper. firm_id is nullable on Finding for network-wide
    findings, but a firm-scoped query must never return those rows.
    """
    return (
        db.query(Finding)
        .filter(Finding.firm_id == firm_id)
        .filter(Finding.firm_id.isnot(None))
        .all()
    )
