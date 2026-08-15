# app/api/availability_windows.py

"""
Availability window CRUD endpoints.

RBAC assumption (contract section 7.2 does not specify who can edit whose windows):
  - Any staff member can VIEW all windows in the firm (team scheduling visibility).
  - A staff member can only CREATE/UPDATE/DELETE their OWN windows.
  - A firm_owner or manager can CREATE/UPDATE/DELETE any staff member's windows.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud import availability_window as crud_aw
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import UserRole
from app.schemas.availability_window import (
    AvailabilityWindowCreate,
    AvailabilityWindowOut,
    AvailabilityWindowUpdate,
)
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate

router = APIRouter(prefix="/api/v1/availability-windows", tags=["Availability Windows"])

_MANAGER_ROLES = {UserRole.firm_owner, UserRole.manager, UserRole.system_admin}


def _assert_can_modify(current_user: User, window_user_id: UUID) -> None:
    """Raise 403 if the current user may not modify a window owned by window_user_id."""
    if current_user.role not in _MANAGER_ROLES and current_user.id != window_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You may only modify your own availability windows",
        )


# ---------------------------------------------------------------------------
# GET /availability-windows/ -- list all windows in the firm (team visibility)
# ---------------------------------------------------------------------------

@router.get("/", response_model=PaginatedResponse[AvailabilityWindowOut])
def list_firm_windows(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    query = crud_aw.get_windows_for_firm_query(db, current_firm.id)
    return paginate(query, limit=limit, offset=offset)


# ---------------------------------------------------------------------------
# GET /availability-windows/mine -- current user's own windows
# ---------------------------------------------------------------------------

@router.get("/mine", response_model=list[AvailabilityWindowOut])
def list_my_windows(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return crud_aw.get_windows_for_user(db, current_user.id, current_firm.id)


# ---------------------------------------------------------------------------
# POST /availability-windows/ -- create a window
# ---------------------------------------------------------------------------

@router.post("/", response_model=AvailabilityWindowOut, status_code=status.HTTP_201_CREATED)
def create_window(
    payload: AvailabilityWindowCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    # Staff members can only create their own windows.
    # Managers and firm_owners may specify any user_id within the firm.
    if current_user.role not in _MANAGER_ROLES:
        target_user_id = current_user.id
    else:
        target_user_id = payload.user_id

    try:
        return crud_aw.create_window(db, target_user_id, current_firm.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# ---------------------------------------------------------------------------
# PATCH /availability-windows/{window_id} -- update a window
# ---------------------------------------------------------------------------

@router.patch("/{window_id}", response_model=AvailabilityWindowOut)
def update_window(
    window_id: UUID,
    payload: AvailabilityWindowUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    window = crud_aw.get_window(db, window_id, current_firm.id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")

    _assert_can_modify(current_user, window.user_id)

    try:
        updated = crud_aw.update_window(db, window_id, current_firm.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return updated


# ---------------------------------------------------------------------------
# DELETE /availability-windows/{window_id} -- delete a window
# ---------------------------------------------------------------------------

@router.delete("/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(
    window_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    window = crud_aw.get_window(db, window_id, current_firm.id)
    if window is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Window not found")

    _assert_can_modify(current_user, window.user_id)

    crud_aw.delete_window(db, window_id, current_firm.id)
