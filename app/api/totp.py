# app/api/totp.py

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User
from app.core.enums import UserRole
from app.schemas.totp import TOTPSetupResponse, TOTPVerifyRequest, TOTPStatusResponse
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.services.totp_service import (
    generate_totp_secret,
    get_totp_uri,
    generate_qr_code_base64,
    verify_totp_code,
    generate_backup_codes,
    enable_2fa_for_user,
)
from app.services.audit_service import write_audit_log

router = APIRouter(tags=["2FA"])


@router.get("/2fa/status", response_model=TOTPStatusResponse)
def get_2fa_status(current_user: User = Depends(get_current_user)):
    return TOTPStatusResponse(
        totp_enabled=current_user.totp_enabled,
        is_required=(current_user.role == UserRole.firm_owner),
    )


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
def setup_2fa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, current_user.email)
    qr = generate_qr_code_base64(uri)
    raw_codes, hashed_codes = generate_backup_codes()

    current_user.totp_secret = secret
    current_user.backup_codes_hash = json.dumps(hashed_codes)
    # totp_enabled stays False until verified
    db.commit()

    write_audit_log(
        db=db,
        firm_id=current_user.firm_id,
        action="user.2fa_setup_initiated",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="user",
        entity_id=current_user.id,
    )

    return TOTPSetupResponse(
        secret=secret,
        qr_code_base64=qr,
        backup_codes=raw_codes,
    )


@router.post("/2fa/verify")
def verify_2fa(
    request: Request,
    body: TOTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.totp_secret:
        raise HTTPException(status_code=400, detail="2FA not set up. Call /auth/2fa/setup first.")

    if not verify_totp_code(current_user.totp_secret, body.code):
        raise HTTPException(status_code=400, detail="Invalid code")

    enable_2fa_for_user(
        db=db,
        user=current_user,
        ip_address=request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent"),
    )

    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
def disable_2fa(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # firm_owner restriction: must not be the only 2FA-enabled owner
    if current_user.role == UserRole.firm_owner:
        other_enabled_owners = db.execute(
            select(User).where(
                User.firm_id == current_user.firm_id,
                User.role == UserRole.firm_owner,
                User.totp_enabled.is_(True),
                User.id != current_user.id,
            )
        ).scalars().first()
        if not other_enabled_owners:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot disable 2FA: you are the only firm_owner with 2FA enabled. "
                    "Another firm_owner must enable 2FA first to prevent lockout."
                ),
            )

    current_user.totp_secret = None
    current_user.totp_enabled = False
    current_user.backup_codes_hash = None
    db.commit()

    write_audit_log(
        db=db,
        firm_id=current_user.firm_id,
        action="user.2fa_disabled",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="user",
        entity_id=current_user.id,
    )

    return {"message": "2FA disabled"}


@router.post("/2fa/backup-codes/regenerate")
def regenerate_backup_codes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw_codes, hashed_codes = generate_backup_codes()
    current_user.backup_codes_hash = json.dumps(hashed_codes)
    db.commit()

    write_audit_log(
        db=db,
        firm_id=current_user.firm_id,
        action="user.backup_codes_regenerated",
        actor_id=current_user.id,
        actor_type="staff",
        entity_type="user",
        entity_id=current_user.id,
    )

    return {"backup_codes": raw_codes}
