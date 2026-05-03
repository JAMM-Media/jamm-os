# app/api/settings.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.enums import StaffAuthPolicy
from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.settings import StaffAuthPolicyOut, StaffAuthPolicyUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.patch("/security/staff-auth-policy", response_model=StaffAuthPolicyOut)
def update_staff_auth_policy(
    body: StaffAuthPolicyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Firm owner updates the staff login policy for their firm.
    Controls whether staff can use password, magic link, or either.
    """
    current_firm.staff_auth_policy = body.staff_auth_policy.value
    db.commit()
    return StaffAuthPolicyOut(staff_auth_policy=current_firm.staff_auth_policy)
