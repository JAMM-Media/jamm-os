# app/crud/automation_rule.py

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.automation_rule import AutomationExecutionLog, AutomationRule
from app.schemas.automation_rule import AutomationRuleCreate, AutomationRuleUpdate


def get_rule(db: Session, rule_id: UUID, firm_id: UUID) -> AutomationRule | None:
    stmt = select(AutomationRule).where(
        AutomationRule.id == rule_id,
        AutomationRule.firm_id == firm_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_rules_for_firm(
    db: Session,
    firm_id: UUID,
    skip: int = 0,
    limit: int = 50,
    enabled_only: bool = False,
) -> List[AutomationRule]:
    stmt = select(AutomationRule).where(AutomationRule.firm_id == firm_id)
    if enabled_only:
        stmt = stmt.where(AutomationRule.is_enabled == True)
    stmt = stmt.order_by(AutomationRule.created_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_rules_for_firm(db: Session, firm_id: UUID) -> int:
    stmt = select(func.count()).select_from(AutomationRule).where(
        AutomationRule.firm_id == firm_id
    )
    return db.execute(stmt).scalar_one()


def create_rule(
    db: Session,
    payload: AutomationRuleCreate,
    firm_id: UUID,
) -> AutomationRule:
    now = datetime.now(timezone.utc)
    rule = AutomationRule(
        firm_id=firm_id,
        name=payload.name,
        description=payload.description,
        is_enabled=payload.is_enabled,
        trigger_event=payload.trigger_event,
        trigger_conditions=[c.model_dump() for c in payload.trigger_conditions],
        actions=[a.model_dump() for a in payload.actions],
        execution_count=0,
        last_executed_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule(
    db: Session,
    rule: AutomationRule,
    payload: AutomationRuleUpdate,
) -> AutomationRule:
    data = payload.model_dump(exclude_none=True)
    if "trigger_conditions" in data:
        data["trigger_conditions"] = [
            c.model_dump() for c in payload.trigger_conditions
        ]
    if "actions" in data:
        data["actions"] = [a.model_dump() for a in payload.actions]
    for key, value in data.items():
        setattr(rule, key, value)
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


def delete_rule(db: Session, rule: AutomationRule) -> None:
    db.delete(rule)
    db.commit()


def toggle_rule(db: Session, rule: AutomationRule, enabled: bool) -> AutomationRule:
    rule.is_enabled = enabled
    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return rule


def get_execution_logs(
    db: Session,
    firm_id: UUID,
    rule_id: UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> List[AutomationExecutionLog]:
    stmt = select(AutomationExecutionLog).where(
        AutomationExecutionLog.firm_id == firm_id
    )
    if rule_id is not None:
        stmt = stmt.where(AutomationExecutionLog.rule_id == rule_id)
    stmt = stmt.order_by(AutomationExecutionLog.executed_at.desc()).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def count_execution_logs(
    db: Session,
    firm_id: UUID,
    rule_id: UUID | None = None,
) -> int:
    stmt = select(func.count()).select_from(AutomationExecutionLog).where(
        AutomationExecutionLog.firm_id == firm_id
    )
    if rule_id is not None:
        stmt = stmt.where(AutomationExecutionLog.rule_id == rule_id)
    return db.execute(stmt).scalar_one()
