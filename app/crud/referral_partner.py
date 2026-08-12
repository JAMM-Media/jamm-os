# app/crud/referral_partner.py

from uuid import UUID
from sqlalchemy.orm import Session

from app.models.referral_partner import ReferralPartner
from app.schemas.referral_partner import ReferralPartnerCreate, ReferralPartnerUpdate
from app.models.lead import Lead


def get_referral_partner_for_firm(
    db: Session, partner_id: UUID, firm_id: UUID
) -> ReferralPartner | None:
    return db.query(ReferralPartner).filter(
        ReferralPartner.id == partner_id,
        ReferralPartner.firm_id == firm_id,
    ).first()


def get_referral_partners_for_firm(db: Session, firm_id: UUID):
    """Returns a query scoped to the firm, for use with paginate()."""
    return db.query(ReferralPartner).filter(ReferralPartner.firm_id == firm_id)


def create_referral_partner(
    db: Session,
    partner_in: ReferralPartnerCreate,
    firm_id: UUID,
) -> ReferralPartner:
    partner = ReferralPartner(**partner_in.model_dump(), firm_id=firm_id)
    db.add(partner)
    db.commit()
    db.refresh(partner)
    return partner


def update_referral_partner(
    db: Session,
    partner: ReferralPartner,
    update_in: ReferralPartnerUpdate,
) -> ReferralPartner:
    for key, value in update_in.model_dump(exclude_unset=True).items():
        setattr(partner, key, value)
    db.commit()
    db.refresh(partner)
    return partner


def has_active_leads(db: Session, partner_id: UUID, firm_id: UUID) -> bool:
    """True if any lead in this firm still references this partner.

    This is a real FK check, not a trust-in-SET-NULL. Letting ON DELETE SET NULL
    silently null out live attribution data without anyone knowing it happened
    would corrupt acquisition reporting. Callers must see this before deleting.
    """
    return db.query(Lead).filter(
        Lead.referral_partner_id == partner_id,
        Lead.firm_id == firm_id,
    ).limit(1).count() > 0


def delete_referral_partner(db: Session, partner: ReferralPartner) -> None:
    db.delete(partner)
    db.commit()
