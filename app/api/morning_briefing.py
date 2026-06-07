# app/api/morning_briefing.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services.morning_briefing_service import get_morning_briefing_signals

router = APIRouter(prefix="/morning-briefing", tags=["morning-briefing"])


@router.get("")
def get_morning_briefing(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return get_morning_briefing_signals(current_firm.id, db)
