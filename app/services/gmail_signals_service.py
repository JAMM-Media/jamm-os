# app/services/gmail_signals_service.py

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from typing import Optional
from uuid import UUID

import google.oauth2.credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.firm import Firm
from app.models.integration import Integration
from app.services.behavioral_log import log_event
from app.services.firm_settings import is_email_sync_enabled
from app.services.token_encryption import decrypt_token

logger = logging.getLogger(__name__)


def _extract_email_address(raw: str) -> str:
    _, addr = parseaddr(raw)
    return addr.lower().strip()


def get_fresh_credentials(integration: Integration) -> google.oauth2.credentials.Credentials:
    from app.core.config import get_settings
    settings = get_settings()

    access_token = decrypt_token(integration.encrypted_access_token)
    refresh_token = (
        decrypt_token(integration.encrypted_refresh_token)
        if integration.encrypted_refresh_token
        else None
    )

    credentials = google.oauth2.credentials.Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
    )

    now = datetime.now(timezone.utc)
    expiry_threshold = now + timedelta(minutes=5)
    needs_refresh = (
        integration.token_expires_at is None
        or integration.token_expires_at <= expiry_threshold
    )
    if needs_refresh and refresh_token:
        credentials.refresh(Request())

    return credentials


def extract_gmail_signals(firm_id: UUID, db: Session) -> dict:
    errors: list[str] = []

    # 0. Email sync is opt in and ships disabled. Gated here rather than in the
    # batch runner because this is the single entry point to the feature, so any
    # future caller inherits the gate instead of having to remember it.
    firm = db.query(Firm).filter(Firm.id == firm_id).first()
    if not is_email_sync_enabled(firm):
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [],
        }

    # 1. Load integration
    integration = (
        db.query(Integration)
        .filter(Integration.firm_id == firm_id, Integration.provider == "gmail")
        .first()
    )
    if not integration or integration.status != "connected":
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [],
        }

    # 2. Get fresh credentials
    try:
        credentials = get_fresh_credentials(integration)
    except Exception as exc:
        logger.error(
            "gmail_signals: credential error firm %s: %s", firm_id, type(exc).__name__
        )
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [type(exc).__name__],
        }

    # 3. Build Gmail API service
    service = build("gmail", "v1", credentials=credentials)

    # 4. List threads from last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    q_date = "after:" + thirty_days_ago.strftime("%Y/%m/%d")

    try:
        list_result = (
            service.users()
            .threads()
            .list(userId="me", maxResults=100, q=q_date)
            .execute()
        )
    except Exception as exc:
        logger.error(
            "gmail_signals: thread list error firm %s: %s", firm_id, type(exc).__name__
        )
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [type(exc).__name__],
        }

    threads = list_result.get("threads", [])
    firm_email = (integration.external_account_id or "").lower().strip()

    # client_id -> list of per-thread signal dicts
    client_threads: dict[UUID, list[dict]] = defaultdict(list)
    threads_processed = 0

    # 5. Process each thread
    for thread_stub in threads:
        thread_id = thread_stub["id"]
        try:
            thread_data = (
                service.users()
                .threads()
                .get(
                    userId="me",
                    id=thread_id,
                    format="metadata",
                    metadataHeaders=["From", "To", "Date"],
                )
                .execute()
            )
        except Exception as exc:
            logger.error(
                "gmail_signals: thread get error firm %s thread %s: %s",
                firm_id,
                thread_id,
                type(exc).__name__,
            )
            errors.append(type(exc).__name__)
            continue

        messages = thread_data.get("messages", [])
        if not messages:
            continue

        # c. Extract internalDate (seconds) and From address per message
        msg_data: list[tuple[float, str]] = []
        for msg in messages:
            internal_date_ms = int(msg.get("internalDate", 0))
            ts_seconds = internal_date_ms / 1000.0
            headers = {
                h["name"]: h["value"]
                for h in msg.get("payload", {}).get("headers", [])
            }
            from_addr = _extract_email_address(headers.get("From", ""))
            msg_data.append((ts_seconds, from_addr))

        # d. Match a client by From address
        all_from_addrs = {addr for _, addr in msg_data if addr}
        client_addrs = all_from_addrs - {firm_email} if firm_email else set(all_from_addrs)

        matched_client = None
        if client_addrs:
            matched_client = (
                db.query(Client)
                .filter(Client.email.in_(client_addrs), Client.firm_id == firm_id)
                .first()
            )

        if not matched_client:
            del all_from_addrs, client_addrs, msg_data
            continue

        client_id = matched_client.id
        del all_from_addrs, client_addrs

        # e. Compute signals
        thread_depth = len(messages)

        sorted_msgs = sorted(msg_data, key=lambda x: x[0])
        last_ts = sorted_msgs[-1][0] if sorted_msgs else None
        last_contact_date: Optional[str] = (
            datetime.fromtimestamp(last_ts, tz=timezone.utc).date().isoformat()
            if last_ts
            else None
        )

        first_sender_is_firm = bool(sorted_msgs) and sorted_msgs[0][1] == firm_email
        last_sender_is_client = bool(sorted_msgs) and sorted_msgs[-1][1] != firm_email
        had_any_reply = len(sorted_msgs) >= 2 and any(
            sorted_msgs[i][1] != sorted_msgs[i + 1][1]
            for i in range(len(sorted_msgs) - 1)
        )

        response_lag_hours: Optional[float] = None
        thread_lag_values: list[float] = []
        if len(sorted_msgs) >= 2:
            for i in range(len(sorted_msgs) - 1):
                ts_a, addr_a = sorted_msgs[i]
                ts_b, addr_b = sorted_msgs[i + 1]
                a_is_firm = addr_a == firm_email
                b_is_firm = addr_b == firm_email
                if a_is_firm != b_is_firm:
                    thread_lag_values.append((ts_b - ts_a) / 3600.0)
            if thread_lag_values:
                response_lag_hours = sum(thread_lag_values) / len(thread_lag_values)

        del msg_data

        client_threads[client_id].append(
            {
                "thread_depth": thread_depth,
                "last_contact_date": last_contact_date,
                "response_lag_hours": response_lag_hours,
                "lag_values": thread_lag_values,
                "first_sender_is_firm": first_sender_is_firm,
                "last_sender_is_client": last_sender_is_client,
                "had_any_reply": had_any_reply,
            }
        )
        threads_processed += 1

    # 6. Aggregate per client and fire behavioral events
    clients_with_signals = 0
    for client_id, thread_list in client_threads.items():
        contact_frequency = len(thread_list)

        lag_vals = [
            t["response_lag_hours"]
            for t in thread_list
            if t["response_lag_hours"] is not None
        ]
        avg_response_lag_hours: Optional[float] = (
            sum(lag_vals) / len(lag_vals) if lag_vals else None
        )

        date_vals = [
            t["last_contact_date"]
            for t in thread_list
            if t["last_contact_date"] is not None
        ]
        agg_last_contact: Optional[str] = max(date_vals) if date_vals else None

        all_lag_vals = [lag for t in thread_list for lag in t.get("lag_values", [])]
        max_response_lag_hours: Optional[float] = max(all_lag_vals) if all_lag_vals else None
        min_response_lag_hours: Optional[float] = min(all_lag_vals) if all_lag_vals else None

        firm_initiated_count = sum(1 for t in thread_list if t["first_sender_is_firm"])
        client_initiated_count = sum(1 for t in thread_list if not t["first_sender_is_firm"])
        unanswered_count = sum(1 for t in thread_list if t["last_sender_is_client"])
        threads_with_no_response = sum(1 for t in thread_list if not t["had_any_reply"])

        # 7. Fire one behavioral event per client via log_event (own session internally)
        log_event(
            event_type="gmail.signals_extracted",
            firm_id=firm_id,
            entity_type="client",
            entity_id=client_id,
            actor_type="system",
            metadata={
                "contact_frequency": contact_frequency,
                "avg_response_lag_hours": avg_response_lag_hours,
                "last_contact_date": agg_last_contact,
                "thread_count": contact_frequency,
                "firm_initiated_count": firm_initiated_count,
                "client_initiated_count": client_initiated_count,
                "unanswered_count": unanswered_count,
                "max_response_lag_hours": max_response_lag_hours,
                "min_response_lag_hours": min_response_lag_hours,
                "threads_with_no_response": threads_with_no_response,
            },
        )

        if unanswered_count > 0:
            unanswered_threads = [t for t in thread_list if t["last_sender_is_client"]]
            unanswered_dates = [
                t["last_contact_date"]
                for t in unanswered_threads
                if t["last_contact_date"] is not None
            ]
            last_client_message_date: Optional[str] = max(unanswered_dates) if unanswered_dates else None
            log_event(
                event_type="email.unanswered_client_thread",
                firm_id=firm_id,
                entity_type="client",
                entity_id=client_id,
                actor_type="system",
                metadata={
                    "thread_count": unanswered_count,
                    "last_client_message_date": last_client_message_date,
                    "provider": "gmail",
                },
            )

        clients_with_signals += 1

    # 8. Return summary
    return {
        "firms_processed": 1,
        "clients_with_signals": clients_with_signals,
        "threads_processed": threads_processed,
        "errors": errors,
    }


def run_gmail_signals_for_all_firms() -> None:
    db = None
    try:
        db = SessionLocal()
        integrations = (
            db.query(Integration)
            .filter(Integration.provider == "gmail", Integration.status == "connected")
            .all()
        )

        total_firms = 0
        total_clients = 0
        total_threads = 0
        for integration in integrations:
            try:
                result = extract_gmail_signals(integration.firm_id, db)
                total_firms += result.get("firms_processed", 0)
                total_clients += result.get("clients_with_signals", 0)
                total_threads += result.get("threads_processed", 0)
            except Exception as exc:
                logger.error(
                    "gmail_signals: firm %s failed: %s",
                    integration.firm_id,
                    type(exc).__name__,
                )

        logger.info(
            "gmail_signals: done firms=%d clients_with_signals=%d threads_processed=%d",
            total_firms,
            total_clients,
            total_threads,
        )
    except Exception as exc:
        logger.error("gmail_signals: batch runner failed: %s", type(exc).__name__)
    finally:
        if db is not None:
            db.close()
