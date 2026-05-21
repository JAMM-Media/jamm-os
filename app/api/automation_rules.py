# app/api/automation_rules.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.crud import automation_rule as crud_rule
from app.schemas.automation_rule import (
    AutomationExecutionLogOut,
    AutomationRuleCreate,
    AutomationRuleOut,
    AutomationRuleUpdate,
)
from app.schemas.pagination import PaginatedResponse

router = APIRouter(prefix="/automation-rules", tags=["automation"])


# IMPORTANT: /execution-logs is defined BEFORE /{rule_id} to prevent FastAPI
# from matching the literal string "execution-logs" as a UUID rule_id.

# --- GET /execution-logs ---
@router.get("/execution-logs", response_model=PaginatedResponse[AutomationExecutionLogOut])
def list_execution_logs(
    rule_id: Optional[UUID] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    items = crud_rule.get_execution_logs(
        db, firm_id=current_firm.id, rule_id=rule_id, skip=skip, limit=limit
    )
    total = crud_rule.count_execution_logs(db, firm_id=current_firm.id, rule_id=rule_id)
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


# --- GET / ---
@router.get("/", response_model=PaginatedResponse[AutomationRuleOut])
def list_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    enabled_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    items = crud_rule.get_rules_for_firm(
        db, firm_id=current_firm.id, skip=skip, limit=limit, enabled_only=enabled_only
    )
    total = crud_rule.count_rules_for_firm(db, firm_id=current_firm.id)
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


# --- POST / ---
@router.post("/", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: AutomationRuleCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    return crud_rule.create_rule(db, payload=payload, firm_id=current_firm.id)


# --- GET /{rule_id} ---
@router.get("/{rule_id}", response_model=AutomationRuleOut)
def get_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_staff_or_above),
):
    rule = crud_rule.get_rule(db, rule_id=rule_id, firm_id=current_firm.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    return rule


# --- PATCH /{rule_id} ---
@router.patch("/{rule_id}", response_model=AutomationRuleOut)
def update_rule(
    rule_id: UUID,
    payload: AutomationRuleUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    rule = crud_rule.get_rule(db, rule_id=rule_id, firm_id=current_firm.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    return crud_rule.update_rule(db, rule=rule, payload=payload)


# --- DELETE /{rule_id} ---
@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    rule = crud_rule.get_rule(db, rule_id=rule_id, firm_id=current_firm.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    crud_rule.delete_rule(db, rule=rule)


# --- POST /{rule_id}/toggle ---
@router.post("/{rule_id}/toggle", response_model=AutomationRuleOut)
def toggle_rule(
    rule_id: UUID,
    enabled: bool = Query(...),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    rule = crud_rule.get_rule(db, rule_id=rule_id, firm_id=current_firm.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    from app.services.behavioral_log import log_event

    result = crud_rule.toggle_rule(db, rule=rule, enabled=enabled)

    log_event(
        firm_id=current_firm.id,
        event_type="firm.automation_enabled" if enabled else "firm.automation_disabled",
        entity_type="automation_rule",
        entity_id=rule_id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "rule_name": rule.name,
            "rule_type": rule.trigger_event if hasattr(rule, 'trigger_event') else None,
            "execution_count": rule.execution_count if hasattr(rule, 'execution_count') else None,
        }
    )

    return result


# --- POST /{rule_id}/simulate ---
@router.post("/{rule_id}/simulate")
def simulate_rule(
    rule_id: UUID,
    mock_payload: dict,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    rule = crud_rule.get_rule(db, rule_id=rule_id, firm_id=current_firm.id)
    if not rule:
        raise HTTPException(status_code=404, detail="Automation rule not found")
    mock_payload["firm_id"] = str(current_firm.id)
    from app.services import condition_evaluator
    conditions_passed = condition_evaluator.evaluate(rule.trigger_conditions, mock_payload)
    return {
        "would_trigger": conditions_passed,
        "conditions_evaluated": len(rule.trigger_conditions),
        "conditions_passed": conditions_passed,
        "trigger_event": rule.trigger_event,
        "actions_that_would_execute": [
            {"type": a.get("type"), "order": a.get("order", 0)}
            for a in rule.actions
        ] if conditions_passed else [],
        "rule_is_enabled": rule.is_enabled,
    }
