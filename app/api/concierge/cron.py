# app/api/concierge/cron.py

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.concierge.triggers import evaluate_triggers
from app.models.concierge_notification import ConciergeNotification

logger = logging.getLogger(__name__)


def run_trigger_check(firm_id: UUID, db: Session) -> int:
    triggers = evaluate_triggers(firm_id, db)

    fired = 0
    for trigger in triggers:
        trigger_type = trigger["trigger_type"]

        existing = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == False,
            )
        ).scalar_one_or_none()

        if existing is not None:
            continue

        notification = ConciergeNotification(
            firm_id=firm_id,
            trigger_type=trigger_type,
            message=trigger["message"],
            created_at=datetime.now(timezone.utc),
            is_read=False,
        )
        db.add(notification)
        fired += 1

    db.commit()
    logger.info("trigger_check firm=%s fired=%d evaluated=%d", firm_id, fired, len(triggers))
    return fired
