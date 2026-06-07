# app/api/inbox.py

import threading
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.firm import Firm
from app.models.integration import Integration
from app.models.user import User
from app.services.behavioral_log import log_event
from app.services.inbox_service import (
    get_gmail_inbox,
    get_gmail_thread,
    get_outlook_inbox,
    get_outlook_thread,
    match_emails_to_clients,
    send_gmail_compose,
    send_gmail_reply,
    send_outlook_compose,
    send_outlook_reply,
)

router = APIRouter(prefix="/inbox", tags=["inbox"])


def _get_integration(
    db: Session,
    firm_id,
    user_id,
    provider: str,
) -> Integration:
    integration = (
        db.query(Integration)
        .filter(
            Integration.firm_id == firm_id,
            Integration.user_id == user_id,
            Integration.provider == provider,
            Integration.status == "connected",
        )
        .first()
    )
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No connected email account. Connect Gmail or Outlook in My Integrations.",
        )
    return integration


def _collect_thread_emails(threads: list[dict]) -> list[str]:
    addrs = set()
    for t in threads:
        for field in ("from", "to"):
            val = t.get(field, "")
            if val:
                for part in val.split(","):
                    part = part.strip()
                    if "@" in part:
                        addrs.add(part.lower())
    return list(addrs)


def _attach_client_matches(threads: list[dict], matches: dict) -> list[dict]:
    result = []
    for t in threads:
        enriched = dict(t)
        addrs = set()
        for field in ("from", "to"):
            val = t.get(field, "")
            for part in val.split(","):
                part = part.strip().lower()
                if "@" in part:
                    addrs.add(part)
        match = None
        for addr in addrs:
            if addr in matches:
                match = matches[addr]
                break
        enriched["client_id"] = match["client_id"] if match else None
        enriched["client_name"] = match["client_name"] if match else None
        result.append(enriched)
    return result


def _mark_gmail_read_bg(integration: Integration, thread_id: str) -> None:
    try:
        from googleapiclient.discovery import build
        from app.services.gmail_signals_service import get_fresh_credentials
        credentials = get_fresh_credentials(integration)
        service = build("gmail", "v1", credentials=credentials)
        service.users().threads().modify(
            userId="me",
            id=thread_id,
            body={"removeLabelIds": ["UNREAD"]},
        ).execute()
    except Exception:
        pass


def _mark_outlook_read_bg(integration: Integration, message_ids: list[str]) -> None:
    try:
        import requests as http_requests
        from app.services.outlook_signals_service import get_fresh_outlook_credentials
        access_token = get_fresh_outlook_credentials(integration)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        for mid in message_ids:
            http_requests.patch(
                f"https://graph.microsoft.com/v1.0/me/messages/{mid}",
                headers=headers,
                json={"isRead": True},
                timeout=15,
            )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/threads")
def list_threads(
    provider: str = Query(default="gmail"),
    page_token: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    integration = _get_integration(db, current_firm.id, current_user.id, provider)

    if provider == "outlook":
        response = get_outlook_inbox(integration, page_token)
    else:
        response = get_gmail_inbox(integration, page_token)

    emails = _collect_thread_emails(response["threads"])
    matches = match_emails_to_clients(db, current_firm.id, emails)
    response["threads"] = _attach_client_matches(response["threads"], matches)
    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "email.inbox_viewed",
            "firm_id": current_firm.id,
            "actor_type": "staff",
            "actor_id": current_user.id,
            "metadata": {
                "provider": provider,
                "thread_count": len(response["threads"]),
                "client_matched_count": sum(1 for t in response["threads"] if t.get("client_id")),
                "unread_count": sum(1 for t in response["threads"] if t.get("unread")),
            },
        },
        daemon=True,
    ).start()
    return response


@router.get("/threads/{thread_id}")
def get_thread(
    thread_id: str,
    provider: str = Query(default="gmail"),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    integration = _get_integration(db, current_firm.id, current_user.id, provider)

    if provider == "outlook":
        thread = get_outlook_thread(integration, thread_id)
        message_ids = [m["message_id"] for m in thread.get("messages", [])]
        t = threading.Thread(
            target=_mark_outlook_read_bg,
            args=(integration, message_ids),
            daemon=True,
        )
        t.start()
    else:
        thread = get_gmail_thread(integration, thread_id)
        t = threading.Thread(
            target=_mark_gmail_read_bg,
            args=(integration, thread_id),
            daemon=True,
        )
        t.start()

    emails = []
    for msg in thread.get("messages", []):
        for field in ("from", "to", "cc"):
            val = msg.get(field, "")
            for part in val.split(","):
                part = part.strip().lower()
                if "@" in part:
                    emails.append(part)

    matches = match_emails_to_clients(db, current_firm.id, list(set(emails)))
    match = None
    for addr in set(emails):
        if addr in matches:
            match = matches[addr]
            break

    thread["client_id"] = match["client_id"] if match else None
    thread["client_name"] = match["client_name"] if match else None

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "email.thread_opened",
            "firm_id": current_firm.id,
            "actor_type": "staff",
            "actor_id": current_user.id,
            "entity_type": "client" if match else None,
            "entity_id": UUID(str(match["client_id"])) if match else None,
            "metadata": {
                "provider": provider,
                "thread_id": thread_id,
                "message_count": len(thread.get("messages", [])),
                "client_matched": bool(match),
                "client_id": match["client_id"] if match else None,
            },
        },
        daemon=True,
    ).start()

    if match:
        messages_list = thread.get("messages", [])
        firm_email_addr = (integration.external_account_id or "").lower().strip()
        if messages_list and firm_email_addr:
            last_msg = messages_list[-1]
            last_msg_from = last_msg.get("from", "").lower()
            if firm_email_addr not in last_msg_from:
                threading.Thread(
                    target=log_event,
                    kwargs={
                        "event_type": "email.awaiting_firm_reply",
                        "firm_id": current_firm.id,
                        "actor_type": "staff",
                        "actor_id": current_user.id,
                        "entity_type": "client",
                        "entity_id": UUID(str(match["client_id"])),
                        "metadata": {
                            "provider": provider,
                            "thread_id": thread_id,
                            "client_id": match["client_id"],
                            "last_client_message_date": last_msg.get("date"),
                            "message_count": len(messages_list),
                        },
                    },
                    daemon=True,
                ).start()

    return thread


class ReplyBody(BaseModel):
    thread_id: str
    to: str
    subject: str
    body: str
    provider: str = "gmail"


@router.post("/reply")
def reply_thread(
    data: ReplyBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    integration = _get_integration(db, current_firm.id, current_user.id, data.provider)

    if data.provider == "outlook":
        result = send_outlook_reply(integration, data.thread_id, data.to, data.subject, data.body)
    else:
        result = send_gmail_reply(integration, data.thread_id, data.to, data.subject, data.body)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "email.reply_sent",
            "firm_id": current_firm.id,
            "actor_type": "staff",
            "actor_id": current_user.id,
            "metadata": {
                "provider": data.provider,
                "thread_id": data.thread_id,
                "to_address_domain": data.to.split("@")[-1] if "@" in data.to else None,
            },
        },
        daemon=True,
    ).start()
    return result


class ComposeBody(BaseModel):
    to: str
    subject: str
    body: str
    provider: str = "gmail"


@router.post("/compose")
def compose_email(
    data: ComposeBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    integration = _get_integration(db, current_firm.id, current_user.id, data.provider)

    if data.provider == "outlook":
        result = send_outlook_compose(integration, data.to, data.subject, data.body)
    else:
        result = send_gmail_compose(integration, data.to, data.subject, data.body)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "email.composed_sent",
            "firm_id": current_firm.id,
            "actor_type": "staff",
            "actor_id": current_user.id,
            "metadata": {
                "provider": data.provider,
                "to_address_domain": data.to.split("@")[-1] if "@" in data.to else None,
            },
        },
        daemon=True,
    ).start()
    return result


class FrontendEventBody(BaseModel):
    event_type: str
    client_id: Optional[str] = None
    thread_id: Optional[str] = None
    provider: Optional[str] = None


@router.post("/events")
def receive_frontend_event(
    body: FrontendEventBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    if not (body.event_type.startswith("client.") or body.event_type.startswith("email.")):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid event_type prefix",
        )
    meta: dict = {}
    if body.client_id is not None:
        meta["client_id"] = body.client_id
    if body.thread_id is not None:
        meta["thread_id"] = body.thread_id
    if body.provider is not None:
        meta["provider"] = body.provider

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": body.event_type,
            "firm_id": current_firm.id,
            "actor_type": "staff",
            "actor_id": current_user.id,
            "metadata": meta or None,
        },
        daemon=True,
    ).start()
    return {"ok": True}
