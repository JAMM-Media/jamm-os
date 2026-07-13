# app/services/calendar_service.py

from app.services.behavioral_log import log_event


def record_external_events_synced(*, firm_id, current_user_id, provider, events) -> None:
    log_event(
        event_type="calendar.external_events_synced",
        firm_id=firm_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "provider": provider,
            "event_count": len(events),
            "has_join_links": sum(
                1 for ev in events if any(
                    p in (ev.get("description", "") + " " + ev.get("location", ""))
                    for p in ["zoom.us", "meet.google.com", "teams.microsoft.com"]
                )
            ),
        },
    )
