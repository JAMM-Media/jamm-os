# app/services/auth_service.py

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.firm import Firm
from app.models.user import User
from app.core.config import get_settings
from app.core.enums import StaffAuthPolicy, UserRole
from app.core.security import verify_password, create_access_token
from app.schemas.totp import LoginRequest
from app.services.audit_service import write_audit_log
from app.services.totp_service import verify_totp_code, verify_backup_code
from app.services.behavioral_log import log_event

settings = get_settings()


def _send_failed_login_alert(firm_id, user_email: str) -> None:
    try:
        from app.db.session import SessionLocal
        from app.models.user import User
        from app.core.enums import UserRole
        from app.models.firm import Firm
        from app.services.email_service import EmailService
        _db = SessionLocal()
        try:
            firm_owner = _db.query(User).filter(
                User.firm_id == firm_id,
                User.role == UserRole.firm_owner,
                User.is_active == True,
            ).first()
            if not firm_owner:
                return
            firm = _db.query(Firm).filter(Firm.id == firm_id).first()
            firm_name = firm.name if firm else "Your firm"
            EmailService.send_notification_email(
                to_email=firm_owner.email,
                firm_name=firm_name,
                recipient_name=firm_owner.full_name or "Firm Owner",
                title="Failed login attempt",
                body=f"A failed login attempt was made for the account {user_email}. If this was not you or a member of your team, review your firm security settings.",
                app_url="https://app.jammpx.com/settings?tab=security",
            )
        finally:
            _db.close()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed login alert email error: %s", type(exc).__name__)


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

    # Check lockout BEFORE password verification
    if user and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return None, "account_locked"

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
            threading.Thread(
                target=_send_failed_login_alert,
                kwargs={"firm_id": user.firm_id, "user_email": user.email},
                daemon=True,
            ).start()

            firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
            firm_settings = firm.settings or {} if firm else {}
            # `or {}` rather than a .get default: the default only fires when the
            # key is absent, and the blob accepts arbitrary unvalidated values, so
            # password_policy can legitimately be present and null. A null policy
            # means no policy, which is the same thing as an absent one.
            policy = firm_settings.get("password_policy") or {}
            max_attempts = int(policy.get("max_failed_attempts", 5))

            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= max_attempts:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
                user.failed_login_count = 0
                db.commit()
                return None, "account_locked"
            db.commit()
        return None, "invalid_credentials"

    if not user.is_active:
        return None, "inactive"

    # Load firm settings (used for auth policy and session timeout)
    firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
    firm_settings = firm.settings or {} if firm else {}

    # --- Staff auth policy enforcement (firm_owner is always exempt) ---
    if user.role != UserRole.firm_owner:
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

    # Reset counter on successful login
    if user.failed_login_count > 0:
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()

    session_jti = str(uuid.uuid4())
    user.current_session_jti = session_jti
    db.commit()

    session_timeout = int(firm_settings.get("session_timeout_minutes", settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "firm_id": str(user.firm_id),
            "token_version": user.token_version,
            "jti": session_jti,
        },
        expires_delta=timedelta(minutes=session_timeout),
    )

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
