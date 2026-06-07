# app/services/morning_briefing_service.py

from datetime import datetime, timedelta, timezone, date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.engagement import Engagement


def get_morning_briefing_signals(firm_id: UUID, db: Session) -> dict:
    """
    Reads behavioral event history to produce actionable signals for the morning briefing.
    Returns a dict of signal categories, each with a list of items sorted by urgency.
    This function is read-only -- it never writes to the database.
    """
    today = date.today()
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)
    seven_days_ago = now - timedelta(days=7)
    week_from_now = today + timedelta(days=7)

    # --- clients_going_cold ---
    signal_events = db.execute(
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type.in_(["gmail.signals_extracted", "outlook.signals_extracted"]),
            BehavioralEvent.entity_type == "client",
            BehavioralEvent.occurred_at >= thirty_days_ago,
        )
        .order_by(BehavioralEvent.occurred_at.desc())
    ).scalars().all()

    seen_signal_clients: set[UUID] = set()
    deduped_signals: list[BehavioralEvent] = []
    for ev in signal_events:
        if ev.entity_id and ev.entity_id not in seen_signal_clients:
            seen_signal_clients.add(ev.entity_id)
            deduped_signals.append(ev)

    clients_going_cold = []
    for ev in deduped_signals:
        meta = ev.extra_metadata or {}
        last_contact = meta.get("last_contact_date")
        if not last_contact:
            continue
        try:
            lc_date = date.fromisoformat(last_contact)
        except (ValueError, TypeError):
            continue
        days_since = (today - lc_date).days
        if days_since >= 30 and ev.entity_id:
            client = db.get(Client, ev.entity_id)
            if not client or client.firm_id != firm_id:
                continue
            clients_going_cold.append({
                "client_id": str(ev.entity_id),
                "client_name": client.name,
                "last_contact_date": last_contact,
                "days_since_contact": days_since,
            })

    clients_going_cold.sort(key=lambda x: x["days_since_contact"], reverse=True)
    clients_going_cold = clients_going_cold[:10]

    # --- unanswered_client_messages ---
    unanswered_events = db.execute(
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "email.unanswered_client_thread",
            BehavioralEvent.entity_type == "client",
            BehavioralEvent.occurred_at >= seven_days_ago,
        )
        .order_by(BehavioralEvent.occurred_at.desc())
    ).scalars().all()

    unanswered_by_client: dict[UUID, BehavioralEvent] = {}
    for ev in unanswered_events:
        if ev.entity_id and ev.entity_id not in unanswered_by_client:
            unanswered_by_client[ev.entity_id] = ev

    unanswered_client_messages = []
    for client_uuid, ev in unanswered_by_client.items():
        client = db.get(Client, client_uuid)
        if not client or client.firm_id != firm_id:
            continue
        meta = ev.extra_metadata or {}
        unanswered_client_messages.append({
            "client_id": str(client_uuid),
            "client_name": client.name,
            "unanswered_count": meta.get("thread_count", 0),
            "last_client_message_date": meta.get("last_client_message_date"),
        })

    unanswered_client_messages.sort(key=lambda x: (x["last_client_message_date"] or ""))
    unanswered_client_messages = unanswered_client_messages[:10]

    # --- slow_response_clients ---
    gmail_signal_events = db.execute(
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "gmail.signals_extracted",
            BehavioralEvent.entity_type == "client",
            BehavioralEvent.occurred_at >= thirty_days_ago,
        )
        .order_by(BehavioralEvent.occurred_at.desc())
    ).scalars().all()

    gmail_by_client: dict[UUID, BehavioralEvent] = {}
    for ev in gmail_signal_events:
        if ev.entity_id and ev.entity_id not in gmail_by_client:
            gmail_by_client[ev.entity_id] = ev

    lag_hours_list: list[float] = []
    for ev in gmail_by_client.values():
        meta = ev.extra_metadata or {}
        lag = meta.get("avg_response_lag_hours")
        if lag is not None:
            try:
                lag_hours_list.append(float(lag))
            except (TypeError, ValueError):
                pass

    firm_avg = sum(lag_hours_list) / len(lag_hours_list) if lag_hours_list else 0.0

    slow_response_clients = []
    for client_uuid, ev in gmail_by_client.items():
        meta = ev.extra_metadata or {}
        lag = meta.get("avg_response_lag_hours")
        if lag is None:
            continue
        try:
            lag_f = float(lag)
        except (TypeError, ValueError):
            continue
        if lag_f > firm_avg:
            client = db.get(Client, client_uuid)
            if not client or client.firm_id != firm_id:
                continue
            slow_response_clients.append({
                "client_id": str(client_uuid),
                "client_name": client.name,
                "avg_response_lag_hours": lag_f,
                "firm_average_hours": firm_avg,
            })

    slow_response_clients.sort(key=lambda x: x["avg_response_lag_hours"], reverse=True)
    slow_response_clients = slow_response_clients[:5]

    # --- engagement deadlines ---
    eng_rows = db.execute(
        select(Engagement, Client.name.label("client_name"))
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.is_active == True,
        )
    ).all()

    engagement_deadlines_today = []
    engagement_deadlines_this_week = []

    for row in eng_rows:
        eng: Engagement = row[0]
        client_name: str = row[1]
        effective_deadline: Optional[date] = eng.extended_deadline or eng.filing_deadline
        if not effective_deadline:
            continue
        deadline_type = "extended" if eng.extended_deadline else "filing"
        item = {
            "engagement_id": str(eng.id),
            "engagement_name": eng.name,
            "client_name": client_name,
            "deadline_type": deadline_type,
        }
        if effective_deadline == today:
            engagement_deadlines_today.append(item)
        elif today < effective_deadline <= week_from_now:
            engagement_deadlines_this_week.append(item)

    engagement_deadlines_this_week = engagement_deadlines_this_week[:10]

    # --- staff_email_activity ---
    activity_events = db.execute(
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type.in_(["email.reply_sent", "email.composed_sent"]),
            BehavioralEvent.occurred_at >= seven_days_ago,
        )
    ).scalars().all()

    total_replies_sent = sum(1 for ev in activity_events if ev.event_type == "email.reply_sent")
    total_composed_sent = sum(1 for ev in activity_events if ev.event_type == "email.composed_sent")
    active_staff_count = len({ev.actor_id for ev in activity_events if ev.actor_id})

    return {
        "clients_going_cold": clients_going_cold,
        "unanswered_client_messages": unanswered_client_messages,
        "slow_response_clients": slow_response_clients,
        "engagement_deadlines_today": engagement_deadlines_today,
        "engagement_deadlines_this_week": engagement_deadlines_this_week,
        "staff_email_activity": {
            "total_replies_sent": total_replies_sent,
            "total_composed_sent": total_composed_sent,
            "active_staff_count": active_staff_count,
        },
    }
