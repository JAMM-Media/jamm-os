# app/api/retention.py

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.models.retention import DataRetentionPolicy
from app.schemas.retention import (
    FlaggedDocumentOut,
    RetentionPolicyOut,
    RetentionPolicyUpdate,
)
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.retention_service import (
    create_default_policy,
    flag_old_documents,
    run_retention_check,
)
from app.services.audit_service import write_audit_log

router = APIRouter(prefix="/retention", tags=["retention"])


def _get_or_create_policy(db: Session, firm_id) -> DataRetentionPolicy:
    policy = db.execute(
        select(DataRetentionPolicy).where(DataRetentionPolicy.firm_id == firm_id)
    ).scalar_one_or_none()
    if policy is None:
        policy = create_default_policy(db, firm_id)
    return policy


@router.get("/policy", response_model=RetentionPolicyOut)
def get_retention_policy(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    return _get_or_create_policy(db, current_firm.id)


@router.put("/policy", response_model=RetentionPolicyOut)
def update_retention_policy(
    body: RetentionPolicyUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_firm_owner),
):
    policy = _get_or_create_policy(db, current_firm.id)

    if body.document_retention_years is not None:
        policy.document_retention_years = body.document_retention_years
    if body.auto_flag_enabled is not None:
        policy.auto_flag_enabled = body.auto_flag_enabled

    db.commit()
    db.refresh(policy)

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="retention.policy_updated",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="retention_policy",
        entity_id=policy.id,
    )

    return policy


@router.get("/flagged", response_model=list[FlaggedDocumentOut])
def get_flagged_documents(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    policy = _get_or_create_policy(db, current_firm.id)
    docs = flag_old_documents(db, current_firm.id, policy.document_retention_years)

    results = []
    for doc in docs:
        reason = (
            f"Document is older than {policy.document_retention_years} year(s). "
            f"Retention policy is {policy.document_retention_years} years."
        )
        results.append(
            FlaggedDocumentOut(
                id=doc.id,
                filename=doc.filename,
                created_at=doc.created_at,
                client_id=doc.client_id,
                engagement_id=doc.engagement_id,
                retention_flag_reason=reason,
            )
        )
    return results


@router.post("/run-check")
def run_retention_check_endpoint(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_firm_owner),
):
    result = run_retention_check(db, current_firm.id)

    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="retention.check_ran_manually",
        actor_id=current_user.id,
        actor_type="staff",
    )

    return result
