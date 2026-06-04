# app/api/concierge/route.py

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.client import Client
from app.models.concierge_notification import ConciergeNotification
from app.api.concierge.prompts import get_system_prompt
from app.api.concierge.context import router as context_router
from app.api.concierge.cron import run_trigger_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/concierge", tags=["concierge"])
router.include_router(context_router)


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    firm_id: str | None = None  # accepted but ignored; firm_id always comes from JWT
    autopilot_enabled: bool = False


@router.post("/chat")
def concierge_chat(
    body: ChatRequest,
    current_firm: Firm = Depends(get_current_firm),
):
    if not current_firm.concierge_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Concierge not activated for this firm",
        )

    settings = get_settings()
    api_key = settings.ANTHROPIC_CONCIERGE_KEY
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Concierge API key not configured",
        )

    client = anthropic.Anthropic(api_key=api_key)

    EMPTY_STATE_RESPONSE = """Welcome to JAMM Concierge. Here are three things I can help you with right now:

1. Walk me through importing my clients from TaxDome (or another platform)
2. Explain the difference between engagements and tasks in JAMM PX
3. What should I set up first after signing up?"""

    if not body.messages:
        def generate_empty():
            yield f"data: {EMPTY_STATE_RESPONSE}\n\n"
        return StreamingResponse(generate_empty(), media_type="text/event-stream")

    def generate():
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=get_system_prompt(autopilot_enabled=body.autopilot_enabled),
            messages=body.messages,
        ) as stream:
            for text in stream.text_stream:
                # SSE requires each data value line to start with "data:".
                # Newlines inside a text chunk must be sent as separate
                # "data:" lines; otherwise lines without the prefix are
                # silently dropped by the frontend reader.
                data_lines = "\n".join(f"data: {line}" for line in text.split("\n"))
                yield f"{data_lines}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/clients/resolve")
def resolve_client_by_name(
    name: str,
    current_firm: Firm = Depends(get_current_firm),
    db: Session = Depends(get_db),
):
    client = db.execute(
        select(Client).where(
            Client.firm_id == current_firm.id,
            func.lower(Client.name).like(f"%{name.lower()}%"),
        ).limit(1)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return {"id": str(client.id), "name": client.name}


@router.post("/trigger-check")
def trigger_check(
    current_firm: Firm = Depends(get_current_firm),
    db: Session = Depends(get_db),
):
    fired = run_trigger_check(firm_id=current_firm.id, db=db)
    return {"triggers_fired": fired}


@router.get("/notifications")
def list_notifications(
    current_firm: Firm = Depends(get_current_firm),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(ConciergeNotification)
        .where(
            ConciergeNotification.firm_id == current_firm.id,
            ConciergeNotification.is_read == False,
        )
        .order_by(ConciergeNotification.created_at.desc())
    ).scalars().all()

    return {
        "items": [
            {
                "id": str(n.id),
                "trigger_type": n.trigger_type,
                "message": n.message,
                "created_at": n.created_at.isoformat(),
            }
            for n in rows
        ],
        "total": len(rows),
    }


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: UUID,
    current_firm: Firm = Depends(get_current_firm),
    db: Session = Depends(get_db),
):
    notification = db.execute(
        select(ConciergeNotification).where(
            ConciergeNotification.id == notification_id,
            ConciergeNotification.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()

    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    notification.dismissed_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
