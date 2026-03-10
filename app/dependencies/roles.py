# app/dependencies/roles.py

"""
Role-Based Access Control (RBAC) dependencies.

These are FastAPI dependencies — you add them to endpoint function signatures
to enforce that only certain roles can call that endpoint.

Usage:
    @router.delete("/{client_id}")
    def delete_client(
        client_id: UUID,
        db: Session = Depends(get_db),
        current_user: User = Depends(require_firm_owner),  # Only firm owners can delete
    ):
        ...

The dependency will automatically return 403 Forbidden if the user's role
doesn't meet the requirement. The router code never needs to check roles itself.
"""

from fastapi import Depends, HTTPException, status
from app.models.user import User
from app.core.enums import UserRole
from app.dependencies.auth import get_current_user


def require_firm_owner(user: User = Depends(get_current_user)) -> User:
    """Only firm_owner and system_admin can call this endpoint."""
    if user.role not in (UserRole.firm_owner, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Firm owner access required",
        )
    return user


def require_manager_or_above(user: User = Depends(get_current_user)) -> User:
    """firm_owner, manager, and system_admin can call this endpoint."""
    if user.role not in (UserRole.firm_owner, UserRole.manager, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or firm owner access required",
        )
    return user


def require_staff_or_above(user: User = Depends(get_current_user)) -> User:
    """Any internal staff role (not client_portal_user) can call this endpoint."""
    if user.role not in (
        UserRole.firm_owner,
        UserRole.manager,
        UserRole.staff,
        UserRole.system_admin,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff access required",
        )
    return user


def require_system_admin(user: User = Depends(get_current_user)) -> User:
    """Only system_admin (JAMM OS internal) can call this endpoint."""
    if user.role != UserRole.system_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System admin access required",
        )
    return user


# ---------------------------------------------------------------------------
# Legacy aliases — kept for backward compatibility during the Phase 1 transition.
# These will be removed once all routers are updated to use the new names.
# ---------------------------------------------------------------------------
require_admin = require_firm_owner
require_staff_or_admin = require_staff_or_above