# app/services/user_service.py

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.crud import user as crud_user
from app.crud import firm as crud_firm
from app.schemas.firm import FirmUpdate
from app.services import s3 as s3_service
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event, log_setting_changes


def update_firm_settings(
    *,
    db: Session,
    firm,
    payload: dict,
    firm_id: UUID,
):
    current_settings = firm.settings or {}
    merged = {**current_settings, **payload}

    if "fee_schedule" in payload:
        previous_schedule = current_settings.get("fee_schedule", {})

    # If portal_logo_s3_key is being replaced, delete the old logo from S3
    old_logo_key = current_settings.get("portal_logo_s3_key")
    new_logo_key = payload.get("portal_logo_s3_key")
    if new_logo_key is not None and old_logo_key and old_logo_key != new_logo_key:
        try:
            s3_service.delete_object(old_logo_key)
        except Exception:
            pass  # Never fail a settings save because of S3 cleanup

    if new_logo_key == "":
        # Explicit empty string means remove logo — also delete from S3
        if old_logo_key:
            try:
                s3_service.delete_object(old_logo_key)
            except Exception:
                pass

    updated = crud_firm.update_firm(
        db,
        firm,
        FirmUpdate(settings=merged),
    )
    if "fee_schedule" in payload:
        log_event(
            firm_id=firm_id,
            event_type="firm.fee_schedule_updated",
            entity_type="firm",
            entity_id=firm_id,
            actor_type="staff",
            actor_id=None,
            metadata={
                "fee_schedule": payload["fee_schedule"],
                "previous_fee_schedule": previous_schedule,
                "count": len(payload["fee_schedule"]),
                "changed_types": [
                    k for k in payload["fee_schedule"]
                    if str(payload["fee_schedule"].get(k)) != str(previous_schedule.get(k))
                ],
            }
        )

    log_setting_changes(
        firm_id=firm_id,
        actor_id=None,
        old_values={k: current_settings.get(k) for k in payload.keys()},
        new_values={k: merged.get(k) for k in payload.keys()},
    )
    return updated


def update_user(
    *,
    db: Session,
    user,
    payload,  # UserUpdate
    firm_id: UUID,
    current_user_id: UUID,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    old_role = user.role
    old_is_active = user.is_active
    old_totp_enabled = user.totp_enabled
    updated = crud_user.update_user(db, user, payload)

    if payload.role is not None and payload.role != old_role:
        write_audit_log(
            db=db,
            firm_id=firm_id,
            action="user.role_changed",
            actor_id=current_user_id,
            actor_type="staff",
            entity_type="user",
            entity_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"old_role": str(old_role), "new_role": str(payload.role)},
        )

    if payload.role is not None and updated.role != old_role:
        log_event(
            firm_id=firm_id,
            event_type="user.role_changed",
            entity_type="user",
            entity_id=user.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_role": str(old_role),
                "to_role": str(updated.role),
            }
        )

    if updated.is_active != old_is_active:
        log_event(
            firm_id=firm_id,
            event_type="user.active_changed",
            entity_type="user",
            entity_id=user.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_active": old_is_active,
                "to_active": updated.is_active,
            }
        )

    if updated.totp_enabled != old_totp_enabled:
        log_event(
            firm_id=firm_id,
            event_type="user.totp_changed",
            entity_type="user",
            entity_id=user.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_enabled": old_totp_enabled,
                "to_enabled": updated.totp_enabled,
            }
        )

    return updated


def update_user_cost_rate(
    *,
    db: Session,
    user,
    cost_rate: Optional[float],
    firm_id: UUID,
):
    old_cost_rate = user.cost_rate
    user.cost_rate = cost_rate
    db.commit()
    db.refresh(user)
    log_event(
        firm_id=firm_id,
        event_type="staff.cost_rate_set",
        entity_type="user",
        entity_id=user.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "cost_rate": cost_rate,
            "user_id": str(user.id),
            "from_cost_rate": old_cost_rate,
            "to_cost_rate": cost_rate,
        },
    )
    return user
