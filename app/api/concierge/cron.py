# app/api/concierge/cron.py

import logging
from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

import anthropic
from app.core.config import get_settings
from app.api.concierge.triggers import evaluate_triggers
from app.models.concierge_notification import ConciergeNotification

logger = logging.getLogger(__name__)


# Trigger types that get AI-generated draft content
_DRAFT_ELIGIBLE_TRIGGERS = {
    "stalled_work",
    "unbilled_work",
    "overdue_invoices_alert",
    "staff_overload",
    "client_comm_gap",
    "pipeline_bottleneck_alert",
    "ar_alert",
}

_DRAFT_PROMPTS = {
    "stalled_work": "You are a practice management assistant. A firm owner has engagements that have not been updated in over 14 days. Write a short internal reminder note (2-3 sentences, plain text, no bullet points, no em dashes) the firm owner can use to prompt their team to provide a status update on stalled work. Do not address any specific client by name. Do not use filler phrases. Return only the draft text.",
    "unbilled_work": "You are a practice management assistant. A firm owner has completed work that has not been invoiced this month. Write a short internal reminder note (2-3 sentences, plain text, no bullet points, no em dashes) prompting the billing review. Do not use filler phrases. Return only the draft text.",
    "overdue_invoices_alert": "You are a practice management assistant. A firm owner has overdue invoices. Write a short, professional, non-aggressive payment follow-up email draft (3-4 sentences, plain text, no bullet points, no em dashes) that a firm owner could send to a client with an overdue invoice. Keep the tone professional and assume a good relationship. Do not address a specific client by name -- use [Client Name]. Do not use filler phrases. Return only the draft text.",
    "staff_overload": "You are a practice management assistant. One or more staff members are at or above full capacity this week. Write a short internal note (2-3 sentences, plain text, no bullet points, no em dashes) a firm owner can use to open a conversation about redistributing work. Do not use filler phrases. Return only the draft text.",
    "client_comm_gap": "You are a practice management assistant. A firm owner has not sent anything to several clients with active work in over 21 days. Write a short, warm status update email draft (3-4 sentences, plain text, no bullet points, no em dashes) a firm owner could send to a client to check in and provide a brief update. Do not address a specific client by name -- use [Client Name]. Do not use filler phrases. Return only the draft text.",
    "pipeline_bottleneck_alert": "You are a practice management assistant. Work is piling up at a specific status in the firm's pipeline. Write a short internal note (2-3 sentences, plain text, no bullet points, no em dashes) prompting the firm owner to investigate what is blocking progress at that stage. Do not use filler phrases. Return only the draft text.",
    "ar_alert": "You are a practice management assistant. A firm's overdue accounts receivable has reached or exceeded last month's total billing. Write a short, professional collections follow-up email draft (3-4 sentences, plain text, no bullet points, no em dashes) a firm owner could adapt for their most overdue client. Use [Client Name] as a placeholder. Keep the tone firm but professional. Do not use filler phrases. Return only the draft text.",
}


def _generate_notification_draft(trigger_type: str) -> str | None:
    """
    Call Fable 5 to generate a pre-written draft for an operational trigger.
    Returns the draft string, or None if generation fails or trigger is not eligible.
    Non-fatal -- a failure here must never block notification creation.
    """
    if trigger_type not in _DRAFT_ELIGIBLE_TRIGGERS:
        return None

    prompt = _DRAFT_PROMPTS.get(trigger_type)
    if not prompt:
        return None

    try:
        settings = get_settings()
        api_key = settings.ANTHROPIC_CONCIERGE_KEY
        if not api_key:
            return None

        client = anthropic.Anthropic(api_key=api_key)
        # TEMP: swapped from claude-fable-5 to claude-opus-4-8 and effort
        # low -> medium on 2026-06-19, following the US export control
        # directive suspending Fable 5 and Mythos 5 worldwide (June 12, 2026,
        # no announced return date). Effort raised to medium to isolate
        # whether reasoning depth affects tool-selection instruction-following
        # during today's client-scoping investigation. Revisit both the model
        # and effort level once Fable 5 access is restored, or once effort:low
        # is confirmed to work reliably on Opus 4.8 for this use case.
        # https://www.anthropic.com/news/fable-mythos-access
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": prompt}],
        )

        if response.stop_reason == "refusal":
            logger.warning("Fable 5 refused draft generation for trigger: %s", trigger_type)
            return None

        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        ).strip()

        return text if text else None

    except Exception as e:
        logger.warning("Draft generation failed for trigger %s: %s", trigger_type, e)
        return None


_DAILY_NOTIFICATION_BUDGET = 3
_BUDGET_EXEMPT_TRIGGERS = {"practice_assistant_transition"}


def _count_notifications_last_24h(firm_id: UUID, db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    return db.execute(
        select(func.count()).select_from(ConciergeNotification).where(
            ConciergeNotification.firm_id == firm_id,
            ConciergeNotification.created_at >= cutoff,
            ConciergeNotification.trigger_type.not_in(list(_BUDGET_EXEMPT_TRIGGERS)),
        )
    ).scalar() or 0


def run_trigger_check(firm_id: UUID, db: Session) -> int:
    triggers = evaluate_triggers(firm_id, db)

    # Sort triggers by urgency_rank so highest priority fire first when budget is tight.
    # Exempt triggers (rank 0) sort to the front regardless.
    triggers_sorted = sorted(triggers, key=lambda t: t.get("urgency_rank", 99))

    # Count how many non-exempt notifications already fired in the last 24 hours.
    notifications_today = _count_notifications_last_24h(firm_id, db)

    fired = 0
    for trigger in triggers_sorted:
        trigger_type = trigger["trigger_type"]

        # Exempt triggers always fire regardless of budget.
        is_exempt = trigger_type in _BUDGET_EXEMPT_TRIGGERS
        if not is_exempt and notifications_today + fired >= _DAILY_NOTIFICATION_BUDGET:
            logger.info(
                "trigger_check budget_gate firm=%s trigger=%s skipped (budget=%d reached)",
                firm_id, trigger_type, _DAILY_NOTIFICATION_BUDGET,
            )
            continue

        existing = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == False,
            )
        ).scalar_one_or_none()

        if existing is not None:
            continue
        recently_dismissed = db.execute(
            select(ConciergeNotification).where(
                ConciergeNotification.firm_id == firm_id,
                ConciergeNotification.trigger_type == trigger_type,
                ConciergeNotification.is_read == True,
                ConciergeNotification.dismissed_at >= datetime.now(timezone.utc) - timedelta(hours=48),
            )
        ).scalar_one_or_none()
        if recently_dismissed is not None:
            continue

        # Generate AI draft for eligible operational triggers
        draft_text = _generate_notification_draft(trigger_type)

        _metadata = trigger.get("metadata") or {}
        if draft_text:
            _metadata = {**_metadata, "draft": draft_text}

        notification = ConciergeNotification(
            firm_id=firm_id,
            trigger_type=trigger_type,
            message=trigger["message"],
            notification_metadata=_metadata if _metadata else None,
            created_at=datetime.now(timezone.utc),
            is_read=False,
        )
        db.add(notification)
        fired += 1

    db.commit()
    logger.info("trigger_check firm=%s fired=%d evaluated=%d budget_today=%d", firm_id, fired, len(triggers), notifications_today)
    return fired
