# app/api/auth.py

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.totp import LoginRequest
from app.schemas.password_reset import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.schemas.staff_refresh import StaffRefreshResponse
import app.services.auth_service as auth_service
import app.services.password_reset_service as password_reset_service
import app.services.staff_magic_link as staff_magic_link_service
import app.services.staff_refresh_service as staff_refresh_service

settings = get_settings()

router = APIRouter()


def _client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else None


@limiter.limit("5/minute")
@router.post("/token")
def login(
    request: Request,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Issues a JWT on successful login.

    Accepts JSON body with username, password, and optional totp_code/backup_code.
    When 2FA is enabled and no code is provided, returns requires_2fa=True
    without issuing a token.

    The token includes:
    - "sub": user's UUID
    - "firm_id": the firm this user belongs to
    - "token_version": current version (for session invalidation)
    """
    result, error = auth_service.authenticate_staff(
        db=db,
        login_data=login_data,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    if error == "account_locked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to too many failed login attempts. Try again in 30 minutes.",
        )
    if error == "invalid_credentials":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if error == "inactive":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )
    if error == "magic_link_only":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your firm requires magic link login. Check your email for a login link.",
        )
    if error == "invalid_2fa":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid 2FA code",
        )
    if error == "no_backup_codes":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No backup codes available",
        )
    if error == "invalid_backup_code":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid backup code",
        )

    # 2FA prompt — no token issued yet, no refresh needed
    if result.get("requires_2fa"):
        return result

    # Successful login — look up user and issue refresh token
    current_user = db.execute(
        select(User).where(User.email == login_data.username)
    ).scalar_one()
    raw_refresh = staff_refresh_service.issue_staff_refresh_token(current_user, db)

    response = JSONResponse(content={
        "access_token": result["access_token"],
        "token_type": "bearer",
    })
    response.set_cookie(
        key="jamm_refresh_token",
        value=raw_refresh,
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        path="/auth/refresh",
        max_age=60 * 60 * 12,  # 12 hours absolute max
    )
    return response


class _MagicLinkRequest(BaseModel):
    email: EmailStr


@router.post("/request-magic-link")
@limiter.limit("5/15minutes")
def request_magic_link(
    body: _MagicLinkRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Request a magic link for staff login.
    Always returns the same response (user enumeration prevention).
    Silently does nothing if firm policy is PASSWORD_ONLY.
    """
    staff_magic_link_service.request_staff_magic_link(email=body.email, db=db)
    return {"message": "If that email is registered, a link is on its way."}


@router.get("/verify-magic-link")
def verify_magic_link(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Exchange a magic link token for a staff JWT.
    One-time use. Returns 401 if invalid or expired.
    """
    result, err = staff_magic_link_service.verify_staff_magic_link(token=token, db=db)
    if err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=err,
        )
    return result


@router.post("/refresh", response_model=StaffRefreshResponse)
def refresh_staff_token(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Accepts the staff refresh token from the jamm_refresh_token HttpOnly cookie.
    Issues a new access token and rotates the refresh token.
    Returns 401 if the token is missing, invalid, or expired.
    """
    raw_token = request.cookies.get("jamm_refresh_token")
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token provided.",
        )

    result = staff_refresh_service.refresh_staff_access_token(raw_token, db)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired. Please log in again.",
        )

    return StaffRefreshResponse(
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        staff_refresh_service.revoke_staff_refresh_token(current_user, db)
    except Exception:
        pass

    response = JSONResponse(content={"message": "Logged out successfully"})
    response.delete_cookie(key="jamm_token", path="/")
    response.delete_cookie(key="jamm_refresh_token", path="/auth/refresh")
    return response


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Accepts an email address and sends a reset link if the account exists.
    Always returns the same response regardless of whether the email exists
    — prevents user enumeration attacks.
    """
    password_reset_service.request_password_reset(
        email=payload.email,
        db=db,
    )
    return ForgotPasswordResponse(
        message="If an account with that email exists, a reset link has been sent."
    )


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Validates the reset token and sets the new password.
    Returns 400 if the token is invalid, expired, or already used.
    On success, all existing sessions for that user are invalidated.
    """
    success, policy_error = password_reset_service.reset_password(
        token=payload.token,
        new_password=payload.new_password,
        db=db,
    )
    if policy_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=policy_error,
        )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )
    return ResetPasswordResponse(message="Password reset successful. Please log in.")
