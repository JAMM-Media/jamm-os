# app/services/recurring_engagement_service.py

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.engagement_template import EngagementTemplate
from app.models.recurring_engagement_log import RecurringEngagementLog
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.document_request import DocumentRequest
from app.crud.engagement_template import list_active_recurring_templates
from app.core.tax_deadlines import get_filing_deadline
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)


def _current_quarter_start(today: date) -> date:
    quarter_start_month = ((today.month - 1) // 3) * 3 + 1
    return date(today.year, quarter_start_month, 1)


def should_spawn(template: EngagementTemplate, client: Client, db) -> bool:
    today = date.today()
    cadence = template.recurrence_cadence

    day_matches = today.day == template.recurrence_day

    if cadence == 'monthly':
        if not day_matches:
            return False
    elif cadence == 'quarterly':
        if not (day_matches and today.month in (1, 4, 7, 10)):
            return False
    elif cadence == 'annually':
        if not (day_matches and today.month == template.recurrence_month):
            return False
    else:
        return False

    # Check if we already spawned in the current period
    stmt = (
        select(RecurringEngagementLog)
        .where(RecurringEngagementLog.template_id == template.id)
        .where(RecurringEngagementLog.client_id == client.id)
        .order_by(RecurringEngagementLog.spawned_at.desc())
        .limit(1)
    )
    last_log = db.execute(stmt).scalars().first()

    if last_log is None:
        return True

    last_date = last_log.spawned_at.date()

    if cadence == 'monthly':
        current_period_start = date(today.year, today.month, 1)
        return last_date < current_period_start
    elif cadence == 'quarterly':
        return last_date < _current_quarter_start(today)
    elif cadence == 'annually':
        return last_date.year < today.year

    return False


def spawn_recurring_engagements() -> None:
    db = SessionLocal()
    try:
        templates = list_active_recurring_templates(db)
        spawned_count = 0

        for template in templates:
            clients = db.execute(
                select(Client)
                .where(Client.firm_id == template.firm_id)
                .where(Client.is_active == True)
            ).scalars().all()

            for client in clients:
                try:
                    if not should_spawn(template, client, db):
                        continue

                    today = date.today()

                    filing_deadline = None
                    if template.engagement_type:
                        deadline_tuple = get_filing_deadline(template.engagement_type)
                        if deadline_tuple:
                            month, day = deadline_tuple
                            try:
                                filing_deadline = date(today.year, month, day)
                            except ValueError:
                                pass

                    engagement = Engagement(
                        firm_id=template.firm_id,
                        client_id=client.id,
                        name=template.name,
                        engagement_type=template.engagement_type,
                        filing_deadline=filing_deadline,
                        status="planning",
                        start_date=today,
                    )
                    db.add(engagement)
                    db.flush()

                    for task_tmpl in (template.task_templates or []):
                        title = task_tmpl.get("title", "") if isinstance(task_tmpl, dict) else getattr(task_tmpl, "title", "")
                        notes = task_tmpl.get("description") if isinstance(task_tmpl, dict) else getattr(task_tmpl, "description", None)
                        if not title:
                            continue
                        db.add(Task(
                            firm_id=template.firm_id,
                            client_id=client.id,
                            engagement_id=engagement.id,
                            title=title,
                            notes=notes,
                        ))

                    if template.document_checklist:
                        checklist_items = [
                            {
                                "id": str(uuid.uuid4()),
                                "label": item,
                                "description": "",
                                "is_required": True,
                                "status": "pending",
                            }
                            for item in template.document_checklist
                            if isinstance(item, str) and item.strip()
                        ]
                        if checklist_items:
                            db.add(DocumentRequest(
                                firm_id=template.firm_id,
                                client_id=client.id,
                                engagement_id=engagement.id,
                                title=f"{template.name} — Documents",
                                checklist_items=checklist_items,
                                status="pending",
                            ))

                    log_entry = RecurringEngagementLog(
                        firm_id=template.firm_id,
                        template_id=template.id,
                        client_id=client.id,
                        engagement_id=engagement.id,
                    )
                    db.add(log_entry)

                    template.last_spawned_at = datetime.now(timezone.utc)
                    db.commit()

                    write_audit_log(
                        db=db,
                        firm_id=template.firm_id,
                        action="engagement.recurring_spawn",
                        actor_type="system",
                        entity_type="engagement",
                        entity_id=engagement.id,
                    )

                    spawned_count += 1

                except Exception as exc:
                    logger.error(
                        "Error spawning recurring engagement for template %s client %s: %s",
                        template.id, client.id, exc,
                    )
                    db.rollback()

        logger.info("Recurring engagement check complete: %d engagements spawned", spawned_count)

    except Exception as exc:
        logger.error("Fatal error in spawn_recurring_engagements: %s", exc)
    finally:
        db.close()
