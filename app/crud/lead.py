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


def convert_lead_to_client(db: Session, lead: Lead):
    """Create a real Client from a won lead inside a single transaction.

    Fields carried forward: name, email, phone, referral_source,
    referring_client_id, entity_type, service_interest (-> business_description,
    the closest available Client field).

    Fields dropped (no Client equivalent): stage, lost_reason, source_platform,
    utm_*, referral_partner_id, revenue_band, urgency, hot, provenance,
    first_response_time. Listed explicitly rather than silently discarded.

    Note: Client.email has a global UNIQUE constraint. If the lead email
    already belongs to another client row the INSERT will raise IntegrityError.
    The caller (transition_lead_stage) does not catch this -- the error will
    surface as a 500 until a dedicated deduplication path is added.

    This function does NOT call db.commit() itself. The caller must commit.
    """
    from app.models.client import Client
    client = Client(
        firm_id=lead.firm_id,
        name=lead.name,
        email=lead.email,
        phone=lead.phone,
        referral_source=lead.referral_source,
        referring_client_id=lead.referring_client_id,
        entity_type=lead.entity_type,
        business_description=lead.service_interest,
    )
    db.add(client)
    db.flush()  # assigns client.id within the open transaction
    return client


def transition_lead_stage(
    db: Session,
    lead: Lead,
    new_stage: LeadStage,
    lost_reason=None,
) -> Lead:
    """The only correct way to change a lead's stage.

    Stage transitions are NOT provenance-gated -- they are a separate concern
    from attribution field updates and must not go through
    update_lead_with_precedence.

    Won is terminal: raises ValueError on any transition attempt off won.
    The won transition already created a real Client; reversing the stage does
    not undo that. A proper un-convert is a separate, future action.

    Lost is reopenable: a forward move off lost clears lost_reason and fires
    a lead.reopened event carrying the prior lost_reason for the intelligence
    layer.

    Raises ValueError if lost is requested with no lost_reason.
    Raises ValueError if any transition is attempted off won.
    Caller converts ValueError to HTTP 400.
    """
    from app.core.enums import LeadLostReason
    from app.services.behavioral_log import log_event

    if lead.stage == LeadStage.won.value:
        raise ValueError(
            "Won is a terminal stage. Transitions off won are not allowed. "
            "A dedicated un-convert action is required."
        )

    if new_stage == LeadStage.won:
        client = convert_lead_to_client(db, lead)
        lead.stage = LeadStage.won.value
        lead.converted_client_id = client.id
        db.commit()
        db.refresh(lead)
        log_event(
            event_type="lead.converted",
            firm_id=lead.firm_id,
            entity_type="lead",
            entity_id=lead.id,
            actor_type="staff",
        )
    elif new_stage == LeadStage.lost:
        if lost_reason is None:
            raise ValueError("lost_reason is required when transitioning a lead to lost")
        lead.stage = LeadStage.lost.value
        lead.lost_reason = lost_reason.value if hasattr(lost_reason, "value") else lost_reason
        db.commit()
        db.refresh(lead)
        log_event(
            event_type="lead.lost",
            firm_id=lead.firm_id,
            entity_type="lead",
            entity_id=lead.id,
            actor_type="staff",
            metadata={"lost_reason": str(lost_reason)},
        )
    else:
        if lead.stage == LeadStage.lost.value:
            prior_lost_reason = lead.lost_reason
            lead.lost_reason = None
            lead.stage = new_stage.value
            db.commit()
            db.refresh(lead)
            log_event(
                event_type="lead.reopened",
                firm_id=lead.firm_id,
                entity_type="lead",
                entity_id=lead.id,
                actor_type="staff",
                metadata={
                    "new_stage": new_stage.value,
                    "prior_lost_reason": prior_lost_reason,
                },
            )
        else:
            lead.stage = new_stage.value
            db.commit()
            db.refresh(lead)

    return lead
