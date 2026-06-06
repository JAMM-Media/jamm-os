STANDING RULES — PERMANENT — DO NOT SKIP

Architecture rules:
- All models use UUID primary keys, firm_id FK, created_at and updated_at (timezone-aware)
- Every module has 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut
- Routers are thin — no business logic ever
- All list endpoints paginated using PaginatedResponse[T]
- RBAC enforced at every endpoint
- Tenant isolation absolute — every query scoped to firm_id without exception
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry
- Audit logging on every sensitive action
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment
- Background tasks that touch the database must create their own SessionLocal() in a try/finally block — never pass the request db session into a background task
- Never use native_enum=True for enums whose values contain dots or special characters — always use sa.Enum(MyEnum, native_enum=False)
- Behavioral event log: fire-and-forget only, never block the main operation, service layer only, own session, never inherit the request session
- Always use SQLAlchemy 2.0 Mapped[] syntax — never Column() style
- Always use Pydantic v2 — model_dump() and field_validator() only, never .dict() or @validator
- DATABASE_URL uses postgresql+psycopg:// dialect prefix — never plain postgresql://
- Never use && to chain commands in PowerShell — separate every command onto its own line
- Never use em dashes anywhere in any string, copy, or comment

---

MIGRATION PROCEDURE — FOLLOW EVERY TIME

1. alembic current -- confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full -- if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current -- confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

PHASE INSTRUCTIONS -- EMAIL INBOX SESSION 2
Inbox view, email threading to clients, reply and compose

This session builds the email inbox inside JAMM PX. Emails are fetched on demand from Gmail/Outlook APIs -- never stored in the database. Email body content is never written to PostgreSQL. Only metadata (thread IDs, subjects, sender addresses, timestamps) used for threading and display is kept in memory per request.

---

STEP 1 -- BACKEND: app/services/inbox_service.py (new file)

Create app/services/inbox_service.py

This service handles fetching emails from Gmail and Outlook for a specific user's integration. It is called by the API layer -- not a background cron.

The service has two providers. Read the existing gmail_signals_service.py and outlook_signals_service.py to understand the credential refresh pattern -- replicate it exactly.

-- Gmail inbox functions --

def get_gmail_inbox(integration: Integration, page_token: str | None = None) -> dict:
    """
    Fetch inbox threads for a connected Gmail account.
    Returns a paginated list of thread summaries.
    Never fetches email body content -- metadata only for the list view.
    Full message content is fetched separately in get_gmail_thread.
    """
    credentials = get_fresh_credentials(integration)  -- import from gmail_signals_service
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
    """
    Fetch full thread content including message bodies.
    Bodies are decoded from base64 but never stored in the database.
    """
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
    """
    Send a reply to a Gmail thread.
    """
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
    """
    Send a new email (not a reply).
    """
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


-- Outlook inbox functions --

Same four functions for Outlook: get_outlook_inbox, get_outlook_thread, send_outlook_reply, send_outlook_compose.

Use the get_fresh_outlook_credentials pattern from outlook_signals_service.py -- import it from there.

Outlook API calls use Microsoft Graph:
  Base URL: https://graph.microsoft.com/v1.0/me

get_outlook_inbox: GET /me/mailFolders/inbox/messages
  params: $top=20, $select=id,conversationId,subject,from,toRecipients,receivedDateTime,bodyPreview,isRead
  if page_token: $skip=page_token (integer offset)
  Group by conversationId for threading.
  Return same shape as Gmail: { threads, next_page_token, provider: "outlook" }

get_outlook_thread: GET /me/messages?$filter=conversationId eq '{conversation_id}'
  $select=id,subject,from,toRecipients,ccRecipients,receivedDateTime,body,isRead
  body.contentType is "text" or "html" -- return body.content
  Return same shape as Gmail thread.

send_outlook_reply: POST /me/messages/{message_id}/reply
  body: { comment: reply_text }

send_outlook_compose: POST /me/sendMail
  body: { message: { subject, body: { contentType: "Text", content: body }, toRecipients: [{ emailAddress: { address: to } }] } }

-- Client email matching --

Add a function match_emails_to_clients that takes a list of email addresses (from/to fields) and a firm_id and returns a dict mapping email address -> client_id + client_name.

def match_emails_to_clients(db: Session, firm_id: UUID, email_addresses: list[str]) -> dict[str, dict]:
    """
    Given a list of email addresses, find matching clients in this firm.
    Returns { email_address: { client_id, client_name } }
    Used to thread emails to client profiles.
    """
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

---

STEP 2 -- BACKEND: app/api/inbox.py (new file)

Create app/api/inbox.py with these endpoints. Router prefix: /inbox. Tag: inbox. All endpoints require get_current_user (any authenticated staff).

All endpoints look up the current user's integration by firm_id + user_id + provider. If no connected integration exists, return 404 "No connected email account. Connect Gmail or Outlook in My Integrations."

-- GET /inbox/threads?provider=gmail&page_token= --

Query params: provider (gmail or outlook, default gmail), page_token (optional)

Finds the user's integration for that provider. Calls get_gmail_inbox or get_outlook_inbox. For each thread summary, calls match_emails_to_clients to find if any thread participants match a client in the firm. Adds client_id and client_name to each thread summary if a match is found.

Returns the full response from the inbox service plus the client matches.

-- GET /inbox/threads/{thread_id}?provider=gmail --

Fetches full thread content. Calls get_gmail_thread or get_outlook_thread. Adds client match to the response. Marks the thread as read via a fire-and-forget background thread (call Gmail/Outlook API to mark as read -- do not block the response).

Return the thread with messages.

-- POST /inbox/reply --

Body: { thread_id: str, to: str, subject: str, body: str, provider: str }

Calls send_gmail_reply or send_outlook_reply. Returns the sent message info.

-- POST /inbox/compose --

Body: { to: str, subject: str, body: str, provider: str }

Calls send_gmail_compose or send_outlook_compose. Returns the sent message info.

Register in app/main.py:
  from app.api.inbox import router as inbox_router
  app.include_router(inbox_router, prefix="/api/v1")

---

STEP 3 -- FRONTEND: Inbox page

Create frontend/src/app/(dashboard)/inbox/page.tsx

This is a two-panel layout matching the firm chat page structure exactly -- left panel is thread list, right panel is open thread content. Use the firm chat page as a visual and structural reference.

The page has:
- A provider toggle at the top of the left panel: Gmail / Outlook buttons. Switching provider reloads the thread list.
- A "Compose" button in the left panel header.
- Thread list on the left (scrollable, 280px wide)
- Thread detail on the right (fills remaining width)

-- Thread list item --
Each thread shows:
- Unread indicator: 6px filled brand blue dot on the left if unread
- From address (bold if unread, normal if read)
- Subject (truncated)
- Snippet (12px muted, truncated to one line)
- Date (right-aligned, muted)
- Client badge: if thread has a client match, show a small pill with the client name in brand blue

On click: fetch GET /api/v1/inbox/threads/{thread_id}?provider={provider} and show in right panel.

-- Thread detail (right panel) --
Header: subject, client badge if matched (clickable -- navigates to /clients/{client_id})
Messages listed oldest to newest, each showing:
- From / To / Date header row
- Body content (plain text, preserve line breaks, render as pre-wrap)
- Horizontal divider between messages

At the bottom: reply compose box. Textarea + Send button. On send: POST /api/v1/inbox/reply.

-- Compose modal --
Triggered by Compose button. Simple modal with To, Subject, Body fields. Send button calls POST /api/v1/inbox/compose.

-- Empty states --
No integration connected: show message "Connect Gmail or Outlook in Settings to see your inbox." with a link to /settings?tab=my_integrations
No threads: "Your inbox is empty."
No thread selected: "Select a conversation to read it."

-- Loading states --
Thread list: animate-pulse skeleton rows while fetching
Thread detail: skeleton while fetching

Style: match firm chat page exactly -- same two-column layout, same left panel background, same message item sizing, same compose box pinned to bottom.

---

STEP 4 -- SIDEBAR: Add Inbox to navigation

In frontend/src/components/layout/Sidebar.tsx, add Inbox to the main navigation items list. Use the Mail icon from lucide-react.

Place it between Billing and Firm Chat in the nav order:
Dashboard / Clients / Engagements / Tasks / Documents / Billing / Inbox / Firm Chat / [divider] / Settings

---

STEP 5 -- CLIENT PROFILE: Email thread preview

In frontend/src/app/clients/[id]/page.tsx, add an Emails tab to the client detail tab row alongside Overview, Engagements, Documents, Billing.

The Emails tab shows threads where this client's email address appears. On tab mount: fetch GET /api/v1/inbox/threads?provider=gmail (and outlook if connected) then filter client-matched threads where client_id matches.

Show a simplified thread list (no compose, no full detail view -- clicking a thread navigates to /inbox with that thread pre-selected via URL param ?thread_id=X&provider=Y).

If neither Gmail nor Outlook is connected: show "Connect your email in My Integrations to see client email threads." with link to settings.

---

NO MIGRATIONS required. No new database tables. Email content is never stored.

After completing confirm:
- app/services/inbox_service.py exists with 8 functions (4 Gmail, 4 Outlook including match_emails_to_clients)
- app/api/inbox.py exists with 4 endpoints registered in main.py
- frontend/src/app/(dashboard)/inbox/page.tsx exists with two-panel layout
- Inbox added to sidebar between Billing and Firm Chat
- Client profile has Emails tab