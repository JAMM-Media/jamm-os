# app/api/pricing.py

"""Public config surface for the pricing service.

This is the pricing service's first HTTP endpoint. Everything the pricing
tables can do was service-layer only until now, so the access rules are stated
here in full rather than inherited from a neighbouring router.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.models.firm import Firm
from app.models.user import User
from app.dependencies.tenant import get_current_firm
from app.schemas.fee_schedule_config import FeeScheduleConfigOut
from app.services import pricing_config_service

router = APIRouter(prefix="/api/pricing", tags=["Pricing"])


@router.get("/config", response_model=FeeScheduleConfigOut)
def get_fee_schedule_config(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    # RBAC: firm_owner only, ON PURPOSE, NOT AS AN OVERSIGHT.
    #
    # require_firm_owner admits firm_owner and system_admin. Manager and staff
    # are refused 403. That is deliberately stricter than most read endpoints
    # in this codebase because a fee schedule is the firm's commercial core.
    #
    # A firm-owner-configurable per-role read/edit permissions setting is a
    # real planned item and would let an owner open this up to managers. It
    # touches several areas of the build, not just this endpoint, and belongs
    # in its own settings-tab session. Until that ships, do not widen this to
    # require_manager_or_above and do not add a local toggle here.
    _: User = Depends(require_firm_owner),
):
    """The merged fee schedule for the calling firm.

    NOT PAGINATED, ON PURPOSE, NOT AS AN OVERSIGHT. The standing rule that all
    list endpoints use PaginatedResponse[T] applies to endpoints that return a
    list. This one returns a single config object. Its interior collections are
    the parts of one indivisible whole: a paged catalog with unpaged firm
    pricing (or the reverse) would describe a fee schedule that does not exist,
    and the caller is a settings screen that needs the entire thing at once to
    render anything at all.

    Thin by construction: authenticate, check the role, call the service, return
    what it returns. No query logic lives here.
    """
    return pricing_config_service.get_fee_schedule_config(db, firm_id=current_firm.id)
