# app/api/settings.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.enums import StaffAuthPolicy
from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.firm import FirmOut
from app.services import firm_service
from app.schemas.settings import StaffAuthPolicyOut, StaffAuthPolicyUpdate, EmailSettingsUpdate, ReviewSettingsUpdate, EmailCalendarSyncUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.patch("/security/staff-auth-policy", response_model=StaffAuthPolicyOut)
def update_staff_auth_policy(
    body: StaffAuthPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Firm owner updates the staff login policy for their firm.
    Controls whether staff can use password, magic link, or either.
    """
    firm = firm_service.update_staff_auth_policy(
        db,
        firm=current_firm,
        staff_auth_policy=body.staff_auth_policy.value,
        current_user_id=current_user.id,
    )
    return StaffAuthPolicyOut(staff_auth_policy=firm.staff_auth_policy)


@router.patch("/review")
def update_review_settings(
    body: ReviewSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    return firm_service.update_review_settings(
        db,
        firm=current_firm,
        google_review_url=body.google_review_url,
        review_requests_enabled=body.review_requests_enabled,
        current_user_id=current_user.id,
    )


@router.patch("/email-calendar-sync", response_model=FirmOut)
def update_email_calendar_sync(
    body: EmailCalendarSyncUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    return firm_service.update_email_calendar_sync(
        db,
        firm=current_firm,
        updates=body.model_dump(),
        current_user_id=current_user.id,
    )


@router.patch("/email")
def update_email_settings(
    body: EmailSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    return firm_service.update_email_settings(
        db,
        firm=current_firm,
        reply_to=str(body.reply_to) if body.reply_to is not None else None,
        display_name=body.display_name,
        current_user_id=current_user.id,
    )
