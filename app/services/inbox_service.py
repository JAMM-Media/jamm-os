# app/services/inbox_service.py

import logging
from uuid import UUID

import requests as http_requests
from googleapiclient.discovery import build
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.services.gmail_signals_service import get_fresh_credentials
from app.services.outlook_signals_service import get_fresh_outlook_credentials

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

def get_gmail_inbox(integration: Integration, page_token: str | None = None) -> dict:
    credentials = get_fresh_credentials(integration)
    service = build("gmail", "v1", credentials=credentials)

    params = {
        "userId": "me",
        "maxResults": 20,
        "labelIds": ["INBOX"],
    }
    if page_token:
        params["pageToken"] = page_token

    result = service.users().threads().list(**params).execute()
    threads = result.get("threads", [])
    next_page_token = result.get("nextPageToken")

    thread_summaries = []
    for thread_stub in threads:
        thread_id = thread_stub["id"]
        try:
            thread_data = service.users().threads().get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["From", "To", "Cc", "Subject", "Date"],
            ).execute()

            messages = thread_data.get("messages", [])
            if not messages:
                continue

            first_msg = messages[0]
            last_msg = messages[-1]

            def get_header(msg, name):
                for h in msg.get("payload", {}).get("headers", []):
                    if h["name"].lower() == name.lower():
                        return h["value"]
                return ""

            thread_summaries.append({
                "thread_id": thread_id,
                "subject": get_header(first_msg, "Subject") or "(no subject)",
                "from": get_header(last_msg, "From"),
                "to": get_header(first_msg, "To"),
                "date": get_header(last_msg, "Date"),
                "message_count": len(messages),
                "snippet": last_msg.get("snippet", ""),
                "unread": any(
                    "UNREAD" in m.get("labelIds", []) for m in messages
                ),
            })
        except Exception:
            continue

    return {
        "threads": thread_summaries,
        "next_page_token": next_page_token,
        "provider": "gmail",
    }


def get_gmail_thread(integration: Integration, thread_id: str) -> dict:
    import base64

    credentials = get_fresh_credentials(integration)
    service = build("gmail", "v1", credentials=credentials)

    thread_data = service.users().threads().get(
        userId="me",
        id=thread_id,
        format="full",
    ).execute()

    messages = []
    for msg in thread_data.get("messages", []):
        def get_header(name):
            for h in msg.get("payload", {}).get("headers", []):
                if h["name"].lower() == name.lower():
                    return h["value"]
            return ""

        def extract_body(payload):
            if payload.get("body", {}).get("data"):
                try:
                    return base64.urlsafe_b64decode(
                        payload["body"]["data"] + "=="
                    ).decode("utf-8", errors="replace")
                except Exception:
                    return ""
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        try:
                            return base64.urlsafe_b64decode(
                                data + "=="
                            ).decode("utf-8", errors="replace")
                        except Exception:
                            return ""
                if part.get("mimeType") == "text/html":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        try:
                            return base64.urlsafe_b64decode(
                                data + "=="
                            ).decode("utf-8", errors="replace")
                        except Exception:
                            return ""
            return ""

        body = extract_body(msg.get("payload", {}))

        messages.append({
            "message_id": msg["id"],
            "from": get_header("From"),
            "to": get_header("To"),
            "cc": get_header("Cc"),
            "subject": get_header("Subject"),
            "date": get_header("Date"),
            "body": body,
            "unread": "UNREAD" in msg.get("labelIds", []),
        })

    return {
        "thread_id": thread_id,
        "messages": messages,
        "provider": "gmail",
    }


def send_gmail_reply(integration: Integration, thread_id: str, to: str, subject: str, body: str) -> dict:
    import base64
    from email.mime.text import MIMEText

    credentials = get_fresh_credentials(integration)
    service = build("gmail", "v1", credentials=credentials)

    message = MIMEText(body, "plain")
    message["to"] = to
    message["subject"] = subject if subject.startswith("Re:") else f"Re: {subject}"

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = service.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()

    return {"message_id": result["id"], "thread_id": thread_id}


def send_gmail_compose(integration: Integration, to: str, subject: str, body: str) -> dict:
    import base64
    from email.mime.text import MIMEText

    credentials = get_fresh_credentials(integration)
    service = build("gmail", "v1", credentials=credentials)

    message = MIMEText(body, "plain")
    message["to"] = to
    message["subject"] = subject

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    return {"message_id": result["id"]}


# ---------------------------------------------------------------------------
# Outlook
# ---------------------------------------------------------------------------

_GRAPH_BASE = "https://graph.microsoft.com/v1.0/me"


def get_outlook_inbox(integration: Integration, page_token: str | None = None) -> dict:
    access_token = get_fresh_outlook_credentials(integration)
    headers = {"Authorization": f"Bearer {access_token}"}

    params: dict = {
        "$top": "20",
        "$select": "id,conversationId,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead",
        "$orderby": "receivedDateTime desc",
    }
    if page_token:
        params["$skip"] = page_token

    resp = http_requests.get(
        f"{_GRAPH_BASE}/mailFolders/inbox/messages",
        headers=headers,
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    messages = data.get("value", [])

    conversations: dict[str, list[dict]] = {}
    for msg in messages:
        conv_id = msg.get("conversationId") or msg["id"]
        if conv_id not in conversations:
            conversations[conv_id] = []
        conversations[conv_id].append(msg)

    thread_summaries = []
    for conv_id, conv_msgs in conversations.items():
        sorted_msgs = sorted(conv_msgs, key=lambda m: m.get("receivedDateTime", ""))
        first = sorted_msgs[0]
        last = sorted_msgs[-1]
        from_addr = (
            last.get("from", {}).get("emailAddress", {}).get("address", "")
        )
        to_addrs = ", ".join(
            r.get("emailAddress", {}).get("address", "")
            for r in first.get("toRecipients", [])
        )
        thread_summaries.append({
            "thread_id": conv_id,
            "subject": first.get("subject") or "(no subject)",
            "from": from_addr,
            "to": to_addrs,
            "date": last.get("receivedDateTime", ""),
            "message_count": len(conv_msgs),
            "snippet": last.get("bodyPreview", ""),
            "unread": any(not m.get("isRead", True) for m in conv_msgs),
        })

    next_skip = None
    if len(messages) == 20:
        skip_val = int(page_token or 0) + 20
        next_skip = str(skip_val)

    return {
        "threads": thread_summaries,
        "next_page_token": next_skip,
        "provider": "outlook",
    }


def get_outlook_thread(integration: Integration, conversation_id: str) -> dict:
    access_token = get_fresh_outlook_credentials(integration)
    headers = {"Authorization": f"Bearer {access_token}"}

    resp = http_requests.get(
        f"{_GRAPH_BASE}/messages",
        headers=headers,
        params={
            "$filter": f"conversationId eq '{conversation_id}'",
            "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,isRead",
            "$orderby": "receivedDateTime asc",
        },
        timeout=30,
    )
    resp.raise_for_status()
    raw_messages = resp.json().get("value", [])

    messages = []
    for msg in raw_messages:
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        to_addrs = ", ".join(
            r.get("emailAddress", {}).get("address", "")
            for r in msg.get("toRecipients", [])
        )
        cc_addrs = ", ".join(
            r.get("emailAddress", {}).get("address", "")
            for r in msg.get("ccRecipients", [])
        )
        messages.append({
            "message_id": msg["id"],
            "from": from_addr,
            "to": to_addrs,
            "cc": cc_addrs,
            "subject": msg.get("subject", ""),
            "date": msg.get("receivedDateTime", ""),
            "body": msg.get("body", {}).get("content", ""),
            "unread": not msg.get("isRead", True),
        })

    return {
        "thread_id": conversation_id,
        "messages": messages,
        "provider": "outlook",
    }


def send_outlook_reply(integration: Integration, thread_id: str, to: str, subject: str, body: str) -> dict:
    access_token = get_fresh_outlook_credentials(integration)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    resp = http_requests.post(
        f"{_GRAPH_BASE}/messages/{thread_id}/reply",
        headers=headers,
        json={"comment": body},
        timeout=30,
    )
    resp.raise_for_status()
    return {"message_id": thread_id, "thread_id": thread_id}


def send_outlook_compose(integration: Integration, to: str, subject: str, body: str) -> dict:
    access_token = get_fresh_outlook_credentials(integration)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        }
    }

    resp = http_requests.post(
        f"{_GRAPH_BASE}/sendMail",
        headers=headers,
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    return {"message_id": None}


# ---------------------------------------------------------------------------
# Client matching
# ---------------------------------------------------------------------------

def match_emails_to_clients(db: Session, firm_id: UUID, email_addresses: list[str]) -> dict[str, dict]:
    from app.models.client import Client

    normalized = [e.lower().strip() for e in email_addresses if e]
    if not normalized:
        return {}
    clients = db.execute(
        select(Client.id, Client.name, Client.email).where(
            Client.firm_id == firm_id,
            func.lower(Client.email).in_(normalized),
        )
    ).all()
    return {
        row[2].lower(): {"client_id": str(row[0]), "client_name": row[1]}
        for row in clients
        if row[2]
    }
