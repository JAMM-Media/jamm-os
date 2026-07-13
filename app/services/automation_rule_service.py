# app/services/automation_rule_service.py

from uuid import UUID

from sqlalchemy.orm import Session

from app.crud import automation_rule as crud_rule
from app.models.automation_rule import AutomationRule
from app.schemas.automation_rule import AutomationRuleUpdate
from app.services.behavioral_log import build_changed_fields, log_event


def update_automation_rule(
    db: Session,
    rule: AutomationRule,
    payload: AutomationRuleUpdate,
    *,
    firm_id: UUID,
    current_user_id: UUID,
):
    tracked_fields = list(payload.model_dump(exclude_none=True).keys())
    old_values = {f: getattr(rule, f) for f in tracked_fields}

    updated = crud_rule.update_rule(db, rule=rule, payload=payload)

    new_values = {f: getattr(updated, f) for f in tracked_fields}
    changed_fields = build_changed_fields(old_values, new_values)
    if changed_fields:
        log_event(
            firm_id=firm_id,
            event_type="firm.automation_modified",
            entity_type="automation_rule",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "rule_name": updated.name,
                "changed_fields": changed_fields,
            },
        )

    return updated


def toggle_automation_rule(
    db: Session,
    rule: AutomationRule,
    enabled: bool,
    *,
    firm_id: UUID,
):
    result = crud_rule.toggle_rule(db, rule=rule, enabled=enabled)

    log_event(
        firm_id=firm_id,
        event_type="firm.automation_enabled" if enabled else "firm.automation_disabled",
        entity_type="automation_rule",
        entity_id=rule.id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "rule_name": rule.name,
            "rule_type": rule.trigger_event if hasattr(rule, 'trigger_event') else None,
            "execution_count": rule.execution_count if hasattr(rule, 'execution_count') else None,
        }
    )

    return result
