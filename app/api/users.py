# app/api/users.py

from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db.session import get_db
from app.models.user import User
from app.models.firm import Firm
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.schemas.task import TaskOut, TaskStatus
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import user as crud_user
from app.crud import task as crud_task
from app.crud import firm as crud_firm
from app.schemas.firm import FirmOut, FirmUpdate
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner, require_staff_or_above
from app.services.audit_service import write_audit_log
from app.services import s3 as s3_service

router = APIRouter(prefix="/users", tags=["users"])


# -------------------------------------------------------------------
# POST /users/ — Create a new user
# Only firm_owner can add new staff to their firm.
# firm_id is injected from the JWT — not taken from the request body.
# -------------------------------------------------------------------
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    existing = crud_user.get_user_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # Override firm_id with the authenticated firm — never trust what's in the payload.
    user_in_with_firm = user_in.model_copy(update={"firm_id": current_firm.id})
    return crud_user.create_user(db, user_in_with_firm)


# -------------------------------------------------------------------
# GET /users/ — List all users in this firm
# -------------------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
    limit: int = Query(50, le=1000),
    offset: int = 0,
    desc: bool = False,
):
    query = db.query(User).filter(User.firm_id == current_firm.id)
    query = query.order_by(User.created_at.desc() if desc else User.created_at)
    return paginate(query, limit=limit, offset=offset)


# -------------------------------------------------------------------
# GET /users/me — Return the currently logged-in user
# MUST be defined before GET /users/{user_id}
# -------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
def read_users_me(
    current_user: User = Depends(get_current_user),
    current_firm: Firm = Depends(get_current_firm),
):
    user_out = UserOut.model_validate(current_user)
    user_out.firm_type = current_firm.firm_type
    user_out.concierge_active = current_firm.concierge_active
    return user_out


# -------------------------------------------------------------------
# GET /users/firm — Return the current user's firm details
# Accessible to all staff roles (staff, manager, firm_owner).
# system_admin is excluded by design — they are not firm members.
# -------------------------------------------------------------------
@router.get("/firm", response_model=FirmOut)
def get_my_firm(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_firm: Firm = Depends(get_current_firm),
):
    firm = crud_firm.get_firm(db, current_firm.id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")
    return firm


# -------------------------------------------------------------------
# PATCH /users/firm/settings — Firm owner updates their firm settings
# -------------------------------------------------------------------
@router.patch("/firm/settings", response_model=FirmOut)
def update_my_firm_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    """
    Allows a firm_owner to update their firm's settings JSON blob.
    Merges the payload into the existing settings dict rather than
    replacing it entirely — so updating fee_schedule does not wipe
    other settings keys.
    """
    firm = crud_firm.get_firm(db, current_firm.id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    # Merge into existing settings rather than replace
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
        from app.services.behavioral_log import log_event
        log_event(
            firm_id=current_firm.id,
            event_type="firm.fee_schedule_updated",
            entity_type="firm",
            entity_id=current_firm.id,
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
    return updated


# -------------------------------------------------------------------
# GET /users/{user_id}/workload — Tasks assigned to this user
# Accessible to any staff member (staff can view their own workload,
# managers/owners can view anyone's).
# -------------------------------------------------------------------
@router.get("/{user_id}/workload", response_model=PaginatedResponse[TaskOut])
def get_user_workload(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    status: TaskStatus | None = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    query = crud_task.get_tasks_for_user(
        db,
        user_id=user_id,
        firm_id=current_firm.id,
        status=status.value if status else None,
    )
    return paginate(query, limit=limit, offset=offset)


# -------------------------------------------------------------------
# GET /users/{user_id} — Get a single user (must belong to same firm)
# -------------------------------------------------------------------
@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -------------------------------------------------------------------
# PATCH /users/{user_id} — Update a user
# -------------------------------------------------------------------
@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    old_is_active = user.is_active
    old_totp_enabled = user.totp_enabled
    updated = crud_user.update_user(db, user, user_in)

    if user_in.role is not None and user_in.role != old_role:
        ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
            request.client.host if request.client else None
        )
        write_audit_log(
            db=db,
            firm_id=current_firm.id,
            action="user.role_changed",
            actor_id=current_user.id,
            actor_type="staff",
            entity_type="user",
            entity_id=user_id,
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
            metadata={"old_role": str(old_role), "new_role": str(user_in.role)},
        )

    from app.services.behavioral_log import log_event

    if user_in.role is not None and updated.role != old_role:
        log_event(
            firm_id=current_firm.id,
            event_type="user.role_changed",
            entity_type="user",
            entity_id=user_id,
            actor_type="staff",
            actor_id=current_user.id,
            metadata={
                "from_role": str(old_role),
                "to_role": str(updated.role),
            }
        )

    if updated.is_active != old_is_active:
        log_event(
            firm_id=current_firm.id,
            event_type="user.active_changed",
            entity_type="user",
            entity_id=user_id,
            actor_type="staff",
            actor_id=current_user.id,
            metadata={
                "from_active": old_is_active,
                "to_active": updated.is_active,
            }
        )

    if updated.totp_enabled != old_totp_enabled:
        log_event(
            firm_id=current_firm.id,
            event_type="user.totp_changed",
            entity_type="user",
            entity_id=user_id,
            actor_type="staff",
            actor_id=current_user.id,
            metadata={
                "from_enabled": old_totp_enabled,
                "to_enabled": updated.totp_enabled,
            }
        )

    return updated


class _CostRateBody(BaseModel):
    cost_rate: Optional[float] = None


# -------------------------------------------------------------------
# PATCH /users/{user_id}/cost-rate — Set staff cost rate (firm_owner only)
# -------------------------------------------------------------------
@router.patch("/{user_id}/cost-rate", response_model=UserOut)
def update_user_cost_rate(
    user_id: UUID,
    body: _CostRateBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    from app.services.behavioral_log import log_event
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old_cost_rate = user.cost_rate
    user.cost_rate = body.cost_rate
    db.commit()
    db.refresh(user)
    log_event(
        firm_id=current_firm.id,
        event_type="staff.cost_rate_set",
        entity_type="user",
        entity_id=user_id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "cost_rate": body.cost_rate,
            "user_id": str(user_id),
            "from_cost_rate": old_cost_rate,
            "to_cost_rate": body.cost_rate,
        },
    )
    return user


# -------------------------------------------------------------------
# DELETE /users/{user_id} — Delete a user
# -------------------------------------------------------------------
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud_user.delete_user(db, user)
