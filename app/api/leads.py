# app/api/leads.py

from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.lead import LeadCreate, LeadUpdate, LeadOut
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import lead as crud_lead
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.user import User
from app.core.enums import LeadProvenance, LeadStage, LeadLostReason

router = APIRouter(prefix="/api/v1/leads", tags=["Leads"])


# ---------------------------------------------------------
# CREATE LEAD
#
# This endpoint is staff-facing only. Provenance is unconditionally
# firm_entered -- a staff member typing in a lead cannot claim crm_lead
# provenance, which would be a false statement about how the data was
# captured. A separate, unauthenticated public endpoint will be needed
# for the future intake form, which will pass crm_lead, and that
# endpoint will intentionally never call this one.
# ---------------------------------------------------------
@router.post("/", response_model=LeadOut, status_code=status.HTTP_201_CREATED)
def create_lead(
    payload: LeadCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    from app.services.audit_service import write_audit_log
    lead = crud_lead.create_lead(
        db=db,
        lead_in=payload,
        firm_id=current_firm.id,
        provenance=LeadProvenance.firm_entered,
    )
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="lead.created",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="lead",
        entity_id=lead.id,
    )
    return lead


# ---------------------------------------------------------
# LIST LEADS
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[LeadOut])
def list_leads(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    stage: LeadStage | None = None,
    hot: bool | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    query = crud_lead.get_leads_for_firm(db, current_firm.id, stage=stage, hot=hot)
    return paginate(query, limit=limit, offset=offset)


# ---------------------------------------------------------
# GET SINGLE LEAD
# ---------------------------------------------------------
@router.get("/{lead_id}", response_model=LeadOut)
def get_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    lead = crud_lead.get_lead_for_firm(db, lead_id, current_firm.id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


# ---------------------------------------------------------
# UPDATE LEAD
#
# Always passes firm_entered as new_provenance -- same reasoning as
# create. Lower-tier updates will only fill blank fields on a higher-tier
# lead; equal-tier updates apply normally.
# ---------------------------------------------------------
@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    from app.services.audit_service import write_audit_log
    lead = crud_lead.get_lead_for_firm(db, lead_id, current_firm.id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    updated = crud_lead.update_lead_with_precedence(
        db=db,
        lead=lead,
        update_in=payload,
        new_provenance=LeadProvenance.firm_entered,
    )
    write_audit_log(
        db=db,
        firm_id=current_firm.id,
        action="lead.updated",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="lead",
        entity_id=lead.id,
    )
    return updated


# ---------------------------------------------------------
# TRANSITION LEAD STAGE
#
# Explicit action endpoint -- transitions are more consequential than
# generic field edits and deserve their own entry point. The existing
# PATCH endpoint is intentionally NOT modified to also handle transitions.
# ---------------------------------------------------------
class LeadTransitionRequest(BaseModel):
    new_stage: LeadStage
    lost_reason: LeadLostReason | None = None


@router.post("/{lead_id}/transition", response_model=LeadOut)
def transition_lead(
    lead_id: UUID,
    payload: LeadTransitionRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    lead = crud_lead.get_lead_for_firm(db, lead_id, current_firm.id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    try:
        updated = crud_lead.transition_lead_stage(
            db=db,
            lead=lead,
            new_stage=payload.new_stage,
            lost_reason=payload.lost_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return updated


# ---------------------------------------------------------
# LEAD ACTIVITY TIMELINE
#
# Returns a merged, chronologically sorted (newest first) list of
# LeadMessage and BehavioralEvent rows for this lead. Both sources
# are tenant-scoped via firm_id. Limit defaults to 50.
# ---------------------------------------------------------
class LeadActivityItemOut(BaseModel):
    id: str
    type: str
    occurred_at: datetime
    description: str
    source_type: str


@router.get("/{lead_id}/activity", response_model=list[LeadActivityItemOut])
def get_lead_activity(
    lead_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    limit: int = Query(50, le=200),
):
    lead = crud_lead.get_lead_for_firm(db, lead_id, current_firm.id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    from app.crud.lead_activity import get_lead_activity as _get_activity
    items = _get_activity(db, lead_id=lead_id, firm_id=current_firm.id, limit=limit)
    return [
        LeadActivityItemOut(
            id=item.id,
            type=item.type,
            occurred_at=item.occurred_at,
            description=item.description,
            source_type=item.source_type,
        )
        for item in items
    ]
