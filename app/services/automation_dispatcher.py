# app/services/automation_dispatcher.py

import logging
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID

from sqlalchemy import select

from app.models.automation_rule import AutomationRule, AutomationExecutionLog
from app.core.enums import TriggerEvent, AutomationExecutionStatus
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)


def dispatch(
    event: TriggerEvent,
    payload: Dict[str, Any],
) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        _dispatch_with_db(event, payload, db)
    except Exception as e:
        logger.warning(f"dispatch() encountered an unexpected error: {e}")
    finally:
        try:
            db.close()
        except Exception as e:
            logger.warning(f"dispatch() failed closing DB session: {e}")


def _dispatch_with_db(
    event: TriggerEvent,
    payload: Dict[str, Any],
    db,
) -> None:
    try:
        firm_id_raw = payload.get("firm_id")
        if not firm_id_raw:
            logger.error("dispatch() called without firm_id in payload — aborting")
            return

        firm_id = UUID(str(firm_id_raw)) if not isinstance(firm_id_raw, UUID) else firm_id_raw

        try:
            stmt = select(AutomationRule).where(
                AutomationRule.firm_id == firm_id,
                AutomationRule.trigger_event == event,
                AutomationRule.is_enabled == True,
            )
            rules = db.execute(stmt).scalars().all()
        except Exception as e:
            logger.warning(f"dispatch() failed querying automation rules: {e}")
            return

        if not rules:
            logger.debug(f"No enabled rules for event={event.value} firm={firm_id}")
            return

        for rule in rules:
            try:
                _execute_rule(rule, payload, db)
            except Exception as e:
                logger.error(f"Unhandled exception executing rule {rule.id}: {e}")

    except Exception as e:
        logger.warning(f"_dispatch_with_db() encountered an unexpected error: {e}")


def _execute_rule(
    rule: AutomationRule,
    payload: Dict[str, Any],
    db,
) -> None:
    try:
        from app.services import condition_evaluator

        conditions_passed = condition_evaluator.evaluate(rule.trigger_conditions, payload)

        if not conditions_passed:
            try:
                log_entry = AutomationExecutionLog(
                    firm_id=rule.firm_id,
                    rule_id=rule.id,
                    trigger_event=rule.trigger_event,
                    trigger_payload=payload,
                    status=AutomationExecutionStatus.skipped,
                    actions_executed=[],
                    error_message="Conditions not met",
                )
                db.add(log_entry)
                db.commit()
            except Exception as e:
                logger.warning(f"_execute_rule() failed writing skipped log for rule {rule.id}: {e}")
            return

        from app.services import automation_actions

        sorted_actions = sorted(rule.actions, key=lambda a: a.get("order", 0))

        executed = []
        overall_status = AutomationExecutionStatus.success

        for action in sorted_actions:
            action_type = action.get("type")
            action_config = action.get("config", {})
            try:
                result = automation_actions.execute(
                    action_type=action_type,
                    config=action_config,
                    payload=payload,
                    db=db,
                )
                executed.append({"type": action_type, "status": "success", "result": str(result)})
            except Exception as e:
                executed.append({"type": action_type, "status": "failed", "error": str(e)})
                logger.error(f"Action {action_type} failed for rule {rule.id}: {e}")
                overall_status = AutomationExecutionStatus.partial

        if executed and all(e["status"] == "failed" for e in executed):
            overall_status = AutomationExecutionStatus.failed

        first_error = next(
            (e.get("error") for e in executed if e["status"] == "failed"), None
        )

        try:
            log_entry = AutomationExecutionLog(
                firm_id=rule.firm_id,
                rule_id=rule.id,
                trigger_event=rule.trigger_event,
                trigger_payload=payload,
                status=overall_status,
                actions_executed=executed,
                error_message=None if overall_status == AutomationExecutionStatus.success else first_error,
            )
            db.add(log_entry)
            db.commit()
        except Exception as e:
            logger.warning(f"_execute_rule() failed writing execution log for rule {rule.id}: {e}")

        try:
            rule.execution_count += 1
            rule.last_executed_at = datetime.now(timezone.utc)
            db.add(rule)
            db.commit()
        except Exception as e:
            logger.warning(f"_execute_rule() failed updating rule stats for rule {rule.id}: {e}")

        if overall_status == AutomationExecutionStatus.failed:
            log_event(
                firm_id=rule.firm_id,
                event_type="automation.failed",
                entity_type="automation_rule",
                entity_id=rule.id,
                actor_type="automation",
                actor_id=None,
                metadata={
                    "trigger_event": str(rule.trigger_event),
                    "failure_reason": first_error,
                }
            )
        else:
            log_event(
                firm_id=rule.firm_id,
                event_type="automation.fired",
                entity_type="automation_rule",
                entity_id=rule.id,
                actor_type="automation",
                actor_id=None,
                metadata={
                    "trigger_event": str(rule.trigger_event),
                    "rule_name": rule.name,
                    "actions_executed": len(executed),
                }
            )

    except Exception as e:
        logger.error(f"_execute_rule() failed for rule {rule.id}: {e}")
