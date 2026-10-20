# app/services/automation_rule_service.py

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.crud import automation_rule as crud_rule
from app.models.automation_rule import AutomationRule
from app.schemas.automation_rule import AutomationRuleUpdate
from app.services.behavioral_log import build_changed_fields, log_event


# Fields that constitute the rule's actual behavior. Editing one of these on
# a preset-lineage rule is what "customized" means; renaming or toggling
# enabled/disabled does not count (toggling has its own event entirely).
_CONFIGURATION_FIELDS = {"actions", "trigger_conditions", "trigger_event"}


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

    if (
        updated.preset_key is not None
        and not updated.is_customized
        and _CONFIGURATION_FIELDS.intersection(changed_fields)
    ):
        updated.is_customized = True
        db.add(updated)
        db.commit()
        db.refresh(updated)

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


# ---------------------------------------------------------------------------
# Create, delete and reset moved out of app/api/automation_rules.py (Phase 7).
# Updates and toggles already fired; these three were silent.
# ---------------------------------------------------------------------------

def create_automation_rule(
    db: Session,
    *,
    payload,  # AutomationRuleCreate
    firm_id: UUID,
    current_user_id: UUID,
):
    rule = crud_rule.create_rule(db, payload=payload, firm_id=firm_id)

    log_event(
        firm_id=firm_id,
        event_type="firm.automation_created",
        entity_type="automation_rule",
        entity_id=rule.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "rule_name": rule.name,
            "trigger_event": rule.trigger_event,
            "is_preset": rule.preset_key is not None,
        },
    )
    return rule


def delete_automation_rule(
    db: Session,
    *,
    rule: AutomationRule,
    firm_id: UUID,
    current_user_id: UUID,
) -> None:
    rule_id = rule.id
    metadata = {
        "rule_name": rule.name,
        "trigger_event": rule.trigger_event,
        "is_preset": rule.preset_key is not None,
    }

    crud_rule.delete_rule(db, rule=rule)

    log_event(
        firm_id=firm_id,
        event_type="firm.automation_deleted",
        entity_type="automation_rule",
        entity_id=rule_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata=metadata,
    )


def reset_automation_rule(
    db: Session,
    *,
    rule: AutomationRule,
    firm_id: UUID,
    current_user_id: UUID,
):
    if not rule.default_actions:
        raise HTTPException(status_code=400, detail="No default actions stored for this rule")
    rule.actions = rule.default_actions
    rule.is_customized = False
    db.commit()
    db.refresh(rule)

    log_event(
        firm_id=firm_id,
        event_type="firm.automation_reset",
        entity_type="automation_rule",
        entity_id=rule.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "rule_name": rule.name,
            "trigger_event": rule.trigger_event,
        },
    )
    return rule
