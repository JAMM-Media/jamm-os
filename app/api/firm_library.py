# app/api/firm_library.py
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services import firm_library_seed_service

router = APIRouter(prefix="/firm-library", tags=["firm-library"])


@router.post("/seed-starter-templates", status_code=200)
def seed_starter_templates_endpoint(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    count = firm_library_seed_service.seed_starter_templates(
        db,
        firm_id=current_firm.id,
        user=current_user,
    )
    return {"seeded": count}


@router.get("/starter-templates-status", status_code=200)
def starter_templates_status(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    has = firm_library_seed_service.has_starter_templates(db, firm_id=current_firm.id)
    return {"has_starter_templates": has}