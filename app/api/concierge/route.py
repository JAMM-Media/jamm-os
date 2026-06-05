# app/api/concierge/route.py

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.client import Client
from app.models.user import User
from app.models.concierge_notification import ConciergeNotification
from app.api.concierge.prompts import get_system_prompt
from app.api.concierge.context import router as context_router
from app.api.concierge.cron import run_trigger_check

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/concierge", tags=["concierge"])
router.include_router(context_router)


class MessageItem(BaseModel):
    role: str
    content: str

    def validate_role(self) -> None:
        if self.role not in ("user", "assistant"):
            raise ValueError(f"Invalid message role: {self.role!r}")

class ChatRequest(BaseModel):
    messages: list[MessageItem]
    autopilot_enabled: bool = False


@router.post("/chat")
@limiter.limit("60/minute")
def concierge_chat(
    request: Request,
    body: ChatRequest,
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
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

    if not body.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Messages cannot be empty",
        )

    MAX_MESSAGE_LENGTH = 4000
    MAX_MESSAGES = 50
    INJECTION_PATTERNS = [
        "ignore previous instructions",
        "ignore all instructions",
        "ignore your instructions",
        "disregard previous",
        "disregard your instructions",
        "forget your instructions",
        "forget previous instructions",
        "you are now",
        "act as if you",
        "pretend you are",
        "pretend to be",
        "jailbreak",
        "dan mode",
        "developer mode",
        "ignore the above",
        "override instructions",
        "override your instructions",
        "new persona",
        "reveal your prompt",
        "show your instructions",
        "what are your instructions",
        "what does your system prompt",
        "repeat your system prompt",
        "print your system prompt",
        "tell me your system prompt",
    ]

    def sanitize_messages(messages: list[MessageItem]) -> list[dict]:
        if len(messages) > MAX_MESSAGES:
            messages = messages[-MAX_MESSAGES:]

        # Validate __OPEN__ sentinel -- only valid as sole message in first turn
        open_indices = [i for i, m in enumerate(messages) if m.content == "__OPEN__"]
        if open_indices:
            if len(messages) != 1 or open_indices[0] != 0:
                logger.warning(
                    f"Invalid __OPEN__ sentinel position for firm {current_firm.id}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message contains disallowed content.",
                )

        cleaned = []
        for msg in messages:
            if msg.role not in ("user", "assistant"):
                logger.warning(
                    f"Invalid message role for firm {current_firm.id}: {msg.role!r}"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Message contains disallowed content.",
                )
            content = msg.content
            if len(content) > MAX_MESSAGE_LENGTH:
                content = content[:MAX_MESSAGE_LENGTH]
            lower = " ".join(content.lower().split())
            for pattern in INJECTION_PATTERNS:
                if pattern in lower:
                    logger.error(
                        f"SECURITY: Prompt injection attempt detected -- "
                        f"firm={current_firm.id} pattern={pattern!r} "
                        f"content_preview={content[:100]!r}"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Message contains disallowed content.",
                    )
            cleaned.append({"role": msg.role, "content": content})
        return cleaned

    sanitized_messages = sanitize_messages(body.messages)

    import re

    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    EIN_PATTERN = re.compile(r'\b\d{2}-\d{7}\b')
    SYSTEM_PROMPT_LEAK_PHRASES = [
        "my instructions are",
        "my system prompt",
        "i was instructed to",
        "i am instructed to",
        "the system prompt says",
        "my prompt says",
        "i have been told to",
        "i have been configured",
        "as per my instructions",
        "according to my instructions",
    ]

    def filter_output(text: str) -> str:
        # Redact SSN patterns
        if SSN_PATTERN.search(text):
            logger.error(
                f"SECURITY: SSN pattern detected in output for firm {current_firm.id}"
            )
            text = SSN_PATTERN.sub("[REDACTED]", text)

        # Redact EIN patterns
        if EIN_PATTERN.search(text):
            logger.error(
                f"SECURITY: EIN pattern detected in output for firm {current_firm.id}"
            )
            text = EIN_PATTERN.sub("[REDACTED]", text)

        # Detect system prompt leakage attempts in output
        lower = text.lower()
        for phrase in SYSTEM_PROMPT_LEAK_PHRASES:
            if phrase in lower:
                logger.error(
                    f"SECURITY: Possible system prompt leakage in output "
                    f"for firm {current_firm.id}: phrase={phrase!r}"
                )
                return "I am JAMM Concierge. I am here to help you use JAMM PX."

        return text

    def generate():
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=get_system_prompt(autopilot_enabled=body.autopilot_enabled),
            messages=sanitized_messages,
        ) as stream:
            assembled = ""
            for text in stream.text_stream:
                assembled += text
                data_lines = "\n".join(f"data: {line}" for line in text.split("\n"))
                yield f"{data_lines}\n\n"
            # Run output filter on fully assembled response
            filtered = filter_output(assembled)
            if filtered != assembled:
                # If filter changed the response, send a replacement sentinel
                yield f"data: \n\n"
                yield f"data: [FILTERED]\n\n"
                yield f"data: {filtered}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/clients/resolve")
@limiter.limit("30/minute")
def resolve_client_by_name(
    request: Request,
    name: str,
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
    fired = run_trigger_check(firm_id=current_firm.id, db=db)
    return {"triggers_fired": fired}


@router.get("/notifications")
def list_notifications(
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.client_portal_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied.",
        )
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
