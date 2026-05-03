# app/services/event_bus.py

import logging
from typing import Any, Dict

from fastapi import BackgroundTasks

from app.core.enums import TriggerEvent

logger = logging.getLogger(__name__)


async def emit_event(
    event: TriggerEvent,
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> None:
    logger.info(f"Event emitted: {event.value} | payload keys: {list(payload.keys())}")
    from app.services import automation_dispatcher
    background_tasks.add_task(
        automation_dispatcher.dispatch,
        event=event,
        payload=payload,
    )


def emit_event_sync(event: TriggerEvent, payload: dict) -> None:
    """
    Synchronous event emission for use outside FastAPI request context
    (e.g. scheduled jobs, background workers).
    Runs automation dispatch directly in the calling thread.
    """
    try:
        from app.services.automation_dispatcher import dispatch
        dispatch(event=event, payload=payload)
    except Exception:
        # Never let automation errors surface to the scheduler
        pass
