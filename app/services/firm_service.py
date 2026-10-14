# app/services/firm_service.py

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud import firm as crud_firm
from app.schemas.firm import FirmCreate
from app.services.behavioral_log import log_event, log_setting_changes


def create_firm(
    db: Session,
    firm_in: FirmCreate,
    *,
    current_user_id: UUID,
):
    firm = crud_firm.create_firm(db, firm_in)

    log_event(
        firm_id=firm.id,
        event_type="firm.created",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "signup_source": firm.signup_source,
            "plan_tier": firm.subscription_tier,
        },
    )

    return firm


# ---------------------------------------------------------------------------
# Firm settings writes moved out of app/api/settings.py (Phase 7). Each one
# records firm.setting_changed per changed key through log_setting_changes.
# None of these keys holds a secret, so values are carried as-is.
# ---------------------------------------------------------------------------

def update_staff_auth_policy(
    db: Session,
    *,
    firm,
    staff_auth_policy: str,
    current_user_id: UUID,
):
    old_policy = firm.staff_auth_policy
    firm.staff_auth_policy = staff_auth_policy
    db.commit()

    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user_id,
        old_values={"staff_auth_policy": old_policy},
        new_values={"staff_auth_policy": firm.staff_auth_policy},
    )
    return firm


def update_review_settings(
    db: Session,
    *,
    firm,
    google_review_url: Optional[str],
    review_requests_enabled: Optional[bool],
    current_user_id: UUID,
):
    if google_review_url is not None and not google_review_url.startswith("https://"):
        raise HTTPException(
            status_code=400,
            detail="google_review_url must start with 'https://'",
        )
    existing = firm.settings or {}
    old_flags = firm.feature_flags or {}
    merged = {**existing}
    if google_review_url is not None:
        merged["google_review_url"] = google_review_url
    else:
        merged.pop("google_review_url", None)
    firm.settings = merged
    if review_requests_enabled is not None:
        existing_flags = firm.feature_flags or {}
        firm.feature_flags = {**existing_flags, "review_requests_enabled": review_requests_enabled}
    db.commit()

    # review_requests_enabled lives in the feature_flags column, not the
    # settings blob. The dotted key names the column it came from (ruled
    # Oct 12, 2026) and keeps the boolean value readable.
    new_flags = firm.feature_flags or {}
    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user_id,
        old_values={
            "google_review_url": existing.get("google_review_url"),
            "feature_flags.review_requests_enabled": old_flags.get("review_requests_enabled"),
        },
        new_values={
            "google_review_url": merged.get("google_review_url"),
            "feature_flags.review_requests_enabled": new_flags.get("review_requests_enabled"),
        },
    )
    return firm.settings


_EMAIL_CALENDAR_SYNC_KEYS = (
    "email_sync_enabled",
    "calendar_sync_enabled",
    "staff_can_disable_email_sync",
    "staff_can_disable_calendar_sync",
)


def update_email_calendar_sync(
    db: Session,
    *,
    firm,
    updates: dict,
    current_user_id: UUID,
):
    existing = firm.settings or {}
    merged = {**existing}
    for key in _EMAIL_CALENDAR_SYNC_KEYS:
        if updates.get(key) is not None:
            merged[key] = updates[key]
    firm.settings = merged
    db.commit()
    db.refresh(firm)

    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user_id,
        old_values={k: existing.get(k) for k in _EMAIL_CALENDAR_SYNC_KEYS},
        new_values={k: merged.get(k) for k in _EMAIL_CALENDAR_SYNC_KEYS},
    )
    return firm


def update_email_settings(
    db: Session,
    *,
    firm,
    reply_to: Optional[str],
    display_name: Optional[str],
    current_user_id: UUID,
):
    existing = firm.settings or {}
    merged = {**existing}
    if reply_to is not None:
        merged["email_reply_to"] = reply_to
    else:
        merged.pop("email_reply_to", None)
    if display_name is not None:
        merged["email_display_name"] = display_name
    else:
        merged.pop("email_display_name", None)
    firm.settings = merged
    db.commit()

    log_setting_changes(
        firm_id=firm.id,
        actor_id=current_user_id,
        old_values={k: existing.get(k) for k in ("email_reply_to", "email_display_name")},
        new_values={k: merged.get(k) for k in ("email_reply_to", "email_display_name")},
    )
    return firm.settings
