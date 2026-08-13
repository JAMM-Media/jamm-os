# app/api/referral_partners.py

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.schemas.referral_partner import (
    ReferralPartnerCreate,
    ReferralPartnerUpdate,
    ReferralPartnerOut,
)
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import referral_partner as crud_partner
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
from app.models.user import User

router = APIRouter(prefix="/api/v1/referral-partners", tags=["Referral Partners"])


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------
@router.post("/", response_model=ReferralPartnerOut, status_code=status.HTTP_201_CREATED)
def create_referral_partner(
    payload: ReferralPartnerCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return crud_partner.create_referral_partner(db=db, partner_in=payload, firm_id=current_firm.id)


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[ReferralPartnerOut])
def list_referral_partners(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    query = crud_partner.get_referral_partners_for_firm(db, current_firm.id)
    return paginate(query, limit=limit, offset=offset)


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{partner_id}", response_model=ReferralPartnerOut)
def get_referral_partner(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    partner = crud_partner.get_referral_partner_for_firm(db, partner_id, current_firm.id)
    if not partner:
        raise HTTPException(status_code=404, detail="Referral partner not found")
    return partner


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{partner_id}", response_model=ReferralPartnerOut)
def update_referral_partner(
    partner_id: UUID,
    payload: ReferralPartnerUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    partner = crud_partner.get_referral_partner_for_firm(db, partner_id, current_firm.id)
    if not partner:
        raise HTTPException(status_code=404, detail="Referral partner not found")
    return crud_partner.update_referral_partner(db=db, partner=partner, update_in=payload)


# ---------------------------------------------------------
# DELETE
#
# Real FK check before delete: ON DELETE SET NULL would silently null out
# live lead attribution without any caller knowing it happened. A 409 here
# makes the decision explicit -- callers must reassign or accept the
# consequence before the delete goes through.
# ---------------------------------------------------------
@router.delete("/{partner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_referral_partner(
    partner_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    partner = crud_partner.get_referral_partner_for_firm(db, partner_id, current_firm.id)
    if not partner:
        raise HTTPException(status_code=404, detail="Referral partner not found")
    if crud_partner.has_active_leads(db, partner_id, current_firm.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a referral partner that has leads referencing it. Reassign or close those leads first.",
        )
    crud_partner.delete_referral_partner(db=db, partner=partner)
