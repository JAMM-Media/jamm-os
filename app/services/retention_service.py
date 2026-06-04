# app/services/retention_service.py

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.retention import DataRetentionPolicy
from app.services.audit_service import write_audit_log


def create_default_policy(db: Session, firm_id: uuid.UUID) -> DataRetentionPolicy:
    """Create a DataRetentionPolicy with defaults for the given firm."""
    policy = DataRetentionPolicy(
        firm_id=firm_id,
        document_retention_years=7,
        auto_flag_enabled=True,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def flag_old_documents(
    db: Session,
    firm_id: uuid.UUID,
    retention_years: int,
) -> list[Document]:
    """
    Returns documents older than the retention period.
    Document model has no is_deleted field (uses hard delete),
    so we query all live documents by firm_id and age.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_years * 365)
    stmt = select(Document).where(
        Document.firm_id == firm_id,
        Document.created_at < cutoff,
    )
    return list(db.execute(stmt).scalars().all())


def run_retention_check(db: Session, firm_id: uuid.UUID) -> dict:
    """
    Runs the retention check for the firm, updates last_ran_at, writes audit log.
    """
    policy = db.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.firm_id == firm_id)
    ).scalar_one_or_none()

    if policy is None:
        policy = create_default_policy(db, firm_id)

    results = flag_old_documents(db, firm_id, policy.document_retention_years)

    policy.last_ran_at = datetime.now(timezone.utc)
    db.commit()

    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="retention.check_ran",
        actor_type="system",
        metadata={"flagged_count": len(results)},
    )

    return {
        "firm_id": str(firm_id),
        "flagged_count": len(results),
        "flagged_document_ids": [str(d.id) for d in results],
    }
