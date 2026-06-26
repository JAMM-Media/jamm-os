# app/api/financial_intelligence.py

import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.firm import Firm
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.services.financial_intelligence_service import (
    get_realization_rate,
    get_effective_hourly_rate,
    get_gross_margin,
    get_pricing_drift,
)

router = APIRouter(prefix="/api/v1/financial-intelligence", tags=["Financial Intelligence"])


@router.get("/realization-rate", response_model=dict)
def realization_rate(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return get_realization_rate(db, current_firm.id)


@router.get("/effective-hourly-rate", response_model=dict)
def effective_hourly_rate(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return get_effective_hourly_rate(db, current_firm.id)


@router.get("/gross-margin", response_model=dict)
def gross_margin(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return get_gross_margin(db, current_firm.id)


@router.get("/pricing-drift", response_model=dict)
def pricing_drift(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    return get_pricing_drift(db, current_firm.id)
