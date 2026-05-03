# app/services/auth_service.py

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.firm import Firm
from app.models.user import User
from app.core.enums import StaffAuthPolicy, UserRole
from app.core.security import verify_password, create_access_token
from app.schemas.totp import LoginRequest
from app.services.audit_service import write_audit_log
from app.services.totp_service import verify_totp_code, verify_backup_code
from app.services.behavioral_log import log_event


def authenticate_staff(
    *,
    db: Session,
    login_data: LoginRequest,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Authenticates a staff user. Returns (token_dict, None) on success,
    (None, error_code) on failure, or (requires_2fa_dict, None) when 2FA
    is required but no code provided.
    """
    user = db.query(User).filter(User.email == login_data.username).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        if user:
            write_audit_log(
                db=db,
                firm_id=user.firm_id,
                action="user.login_failed",
                actor_type="system",
                entity_type="user",
                entity_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            log_event(
                firm_id=user.firm_id,
                event_type="user.login_failed",
                entity_type="user",
                entity_id=user.id,
                actor_type="staff",
                actor_id=None,
                metadata={
                    "reason": "invalid_credentials",
                    "time_of_day": datetime.now(timezone.utc).hour,
                    "day_of_week": datetime.now(timezone.utc).weekday(),
                }
            )
        return None, "invalid_credentials"

    if not user.is_active:
        return None, "inactive"

    # --- Staff auth policy enforcement (firm_owner is always exempt) ---
    if user.role != UserRole.firm_owner:
        firm = db.execute(select(Firm).where(Firm.id == user.firm_id)).scalar_one_or_none()
        if firm and firm.staff_auth_policy == StaffAuthPolicy.MAGIC_LINK_ONLY.value:
            return None, "magic_link_only"

    # --- 2FA enforcement ---
    if user.totp_enabled:
        if not login_data.totp_code and not login_data.backup_code:
            return {"requires_2fa": True, "access_token": None}, None

        if login_data.totp_code:
            if not verify_totp_code(user.totp_secret, login_data.totp_code):
                return None, "invalid_2fa"
        elif login_data.backup_code:
            if not user.backup_codes_hash:
                return None, "no_backup_codes"
            valid, updated_json = verify_backup_code(
                user.backup_codes_hash, login_data.backup_code
            )
            if not valid:
                return None, "invalid_backup_code"
            user.backup_codes_hash = updated_json
            db.commit()

    access_token = create_access_token(data={
        "sub": str(user.id),
        "firm_id": str(user.firm_id),
        "token_version": user.token_version,
    })

    write_audit_log(
        db=db,
        firm_id=user.firm_id,
        action="user.login_success",
        actor_id=user.id,
        actor_type="staff",
        entity_type="user",
        entity_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    log_event(
        firm_id=user.firm_id,
        event_type="user.login",
        entity_type="user",
        entity_id=user.id,
        actor_type="staff",
        actor_id=user.id,
        metadata={
            "time_of_day": datetime.now(timezone.utc).hour,
            "day_of_week": datetime.now(timezone.utc).weekday(),
        }
    )

    return {"access_token": access_token, "token_type": "bearer"}, None
