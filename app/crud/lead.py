# app/crud/lead.py

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.schemas.lead import LeadCreate, LeadUpdate
from app.core.enums import LeadProvenance, LeadStage

# Precedence order for provenance tiers. Higher number wins.
# crm_lead is the most trusted (system-captured), client_reported is the least.
PROVENANCE_TIER: dict[LeadProvenance, int] = {
    LeadProvenance.client_reported: 1,
    LeadProvenance.firm_entered: 2,
    LeadProvenance.crm_lead: 3,
}


def get_lead_for_firm(db: Session, lead_id: UUID, firm_id: UUID) -> Lead | None:
    return db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.firm_id == firm_id,
    ).first()


def get_leads_for_firm(
    db: Session,
    firm_id: UUID,
    stage: LeadStage | None = None,
    hot: bool | None = None,
):
    """Returns a query scoped to the firm, for use with paginate()."""
    query = db.query(Lead).filter(Lead.firm_id == firm_id)
    if stage is not None:
        query = query.filter(Lead.stage == stage.value)
    if hot is not None:
        query = query.filter(Lead.hot == hot)
    return query


def create_lead(
    db: Session,
    lead_in: LeadCreate,
    firm_id: UUID,
    provenance: LeadProvenance,
) -> Lead:
    """Create a lead with an explicitly-supplied provenance.

    provenance is a required plain argument, NOT read from lead_in. This
    makes it structurally impossible for a caller to claim a higher-trust
    provenance than the endpoint allows -- the service layer decides, the
    payload never does.
    """
    data = lead_in.model_dump(exclude={"provenance"})
    # Unwrap enum members to their string values for the VARCHAR-backed columns.
    for field in ("stage", "lost_reason", "referral_source", "source_platform"):
        v = data.get(field)
        if v is not None:
            data[field] = getattr(v, "value", v)
    lead = Lead(**data, firm_id=firm_id, provenance=provenance.value)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


def update_lead_with_precedence(
    db: Session,
    lead: Lead,
    update_in: LeadUpdate,
    new_provenance: LeadProvenance,
) -> Lead:
    """Apply updates subject to provenance precedence rules.

    Precedence is substitution, never blending (per CRM contract):
    - If new_provenance tier >= lead's current tier: apply all provided
      fields and update provenance to new_provenance.
    - If new_provenance tier < lead's current tier: only fill fields that
      are currently None on the lead. Never overwrite existing non-null
      values with lower-trust data.
    """
    current_tier = PROVENANCE_TIER[LeadProvenance(lead.provenance)]
    incoming_tier = PROVENANCE_TIER[new_provenance]

    changes = update_in.model_dump(exclude_unset=True, exclude={"provenance"})

    if incoming_tier >= current_tier:
        # Equal or higher tier: full update.
        for key, value in changes.items():
            setattr(lead, key, value)
        lead.provenance = new_provenance.value
    else:
        # Lower tier: only fill currently-blank fields.
        for key, value in changes.items():
            if getattr(lead, key) is None:
                setattr(lead, key, value)

    db.commit()
    db.refresh(lead)
    return lead
