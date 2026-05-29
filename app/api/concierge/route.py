# app/api/concierge/route.py
import logging
import uuid
from typing import Any
import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse
from app.core.config import get_settings
from app.db.session import get_db
from app.dependencies.tenant import get_current_user_and_firm
from app.models.firm import Firm
from app.models.user import User
from app.api.concierge.prompts import get_system_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/concierge", tags=["concierge"])


class ChatRequest(BaseModel):
    messages: list[dict[str, Any]]
    firm_id: str | None = None


def _log_concierge_conversation(
    db: Session,
    firm: Firm,
    user: User,
    messages: list[dict[str, Any]],
    response: str,
) -> None:
    try:
        from sqlalchemy import text
        db.execute(
            text("""
                INSERT INTO audit_logs (id, firm_id, actor_id, actor_type, action, entity_type, metadata, created_at)
                VALUES (:id, :firm_id, :actor_id, :actor_type, :action, :entity_type, CAST(:metadata AS json), now())
            """),
            {
                "id": str(uuid.uuid4()),
                "firm_id": str(firm.id),
                "actor_id": str(user.id),
                "actor_type": "user",
                "action": "concierge_conversation",
                "entity_type": "concierge",
                "metadata": __import__("json").dumps({
                    "messages": messages,
                    "response": response,
                }),
            }
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to log concierge conversation: {e}")


@router.post("/chat")
def concierge_chat(
    body: ChatRequest,
    current_user_and_firm: tuple[User, Firm] = Depends(get_current_user_and_firm),
    db: Session = Depends(get_db),
):
    current_user, current_firm = current_user_and_firm

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
        full_response = ""
        with client.messages.stream(
            model="claude-sonnet-4-5",
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": get_system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=body.messages,
            extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
        ) as stream:
            for text in stream.text_stream:
                full_response += text
                yield f"data: {text}\n\n"
        _log_concierge_conversation(
            db=db,
            firm=current_firm,
            user=current_user,
            messages=body.messages,
            response=full_response,
        )

    return StreamingResponse(generate(), media_type="text/event-stream")
