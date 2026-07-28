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
from app.schemas.firm import FirmOut
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner, require_staff_or_above
import app.services.user_service as user_service

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
    user_out.concierge_entry_mode = (current_firm.settings or {}).get('concierge_entry_mode', 'floating')
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

    return user_service.update_firm_settings(
        db=db, firm=firm, payload=payload, firm_id=current_firm.id,
    )


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

    ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or (
        request.client.host if request.client else None
    )
    user_agent = request.headers.get("user-agent")

    return user_service.update_user(
        db=db, user=user, payload=user_in,
        firm_id=current_firm.id, current_user_id=current_user.id,
        ip_address=ip, user_agent=user_agent,
    )


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
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user_service.update_user_cost_rate(
        db=db, user=user, cost_rate=body.cost_rate, firm_id=current_firm.id,
    )


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
