# app/api/settings.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import StaffAuthPolicy
from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.firm import FirmOut
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
    current_firm.staff_auth_policy = body.staff_auth_policy.value
    db.commit()
    return StaffAuthPolicyOut(staff_auth_policy=current_firm.staff_auth_policy)


@router.patch("/review")
def update_review_settings(
    body: ReviewSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    if body.google_review_url is not None and not body.google_review_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="google_review_url must start with 'https://'",
        )
    existing = current_firm.settings or {}
    merged = {**existing}
    if body.google_review_url is not None:
        merged["google_review_url"] = body.google_review_url
    else:
        merged.pop("google_review_url", None)
    current_firm.settings = merged
    if body.review_requests_enabled is not None:
        existing_flags = current_firm.feature_flags or {}
        current_firm.feature_flags = {**existing_flags, "review_requests_enabled": body.review_requests_enabled}
    db.commit()
    return current_firm.settings


@router.patch("/email-calendar-sync", response_model=FirmOut)
def update_email_calendar_sync(
    body: EmailCalendarSyncUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    existing = current_firm.settings or {}
    merged = {**existing}
    if body.email_sync_enabled is not None:
        merged["email_sync_enabled"] = body.email_sync_enabled
    if body.calendar_sync_enabled is not None:
        merged["calendar_sync_enabled"] = body.calendar_sync_enabled
    if body.staff_can_disable_email_sync is not None:
        merged["staff_can_disable_email_sync"] = body.staff_can_disable_email_sync
    if body.staff_can_disable_calendar_sync is not None:
        merged["staff_can_disable_calendar_sync"] = body.staff_can_disable_calendar_sync
    current_firm.settings = merged
    db.commit()
    db.refresh(current_firm)
    return current_firm


@router.patch("/email")
def update_email_settings(
    body: EmailSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    existing = current_firm.settings or {}
    merged = {**existing}
    if body.reply_to is not None:
        merged["email_reply_to"] = str(body.reply_to)
    else:
        merged.pop("email_reply_to", None)
    if body.display_name is not None:
        merged["email_display_name"] = body.display_name
    else:
        merged.pop("email_display_name", None)
    current_firm.settings = merged
    db.commit()
    return current_firm.settings
