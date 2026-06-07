# app/services/outlook_signals_service.py

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import msal
import requests as http_requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.integration import Integration
from app.services.behavioral_log import log_event
from app.services.token_encryption import decrypt_token, encrypt_token
from app.services.outlook_service import OUTLOOK_SCOPES

logger = logging.getLogger(__name__)


def get_fresh_outlook_credentials(integration: Integration) -> str:
    settings = get_settings()
    access_token = decrypt_token(integration.encrypted_access_token)

    now = datetime.now(timezone.utc)
    expiry_threshold = now + timedelta(minutes=5)
    needs_refresh = (
        integration.token_expires_at is None
        or integration.token_expires_at <= expiry_threshold
    )

    if needs_refresh:
        refresh_token = (
            decrypt_token(integration.encrypted_refresh_token)
            if integration.encrypted_refresh_token
            else None
        )
        if not refresh_token:
            raise ValueError("Token refresh failed: no refresh token available")

        app = msal.ConfidentialClientApplication(
            client_id=settings.MICROSOFT_CLIENT_ID,
            client_credential=settings.MICROSOFT_CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{settings.MICROSOFT_TENANT_ID}",
        )
        result = app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=OUTLOOK_SCOPES,
        )
        if "error" in result:
            raise ValueError("Token refresh failed")
        return result["access_token"]

    return access_token


def extract_outlook_signals(firm_id: UUID, db: Session) -> dict:
    errors: list[str] = []

    # 1. Load integration
    integration = (
        db.query(Integration)
        .filter(Integration.firm_id == firm_id, Integration.provider == "outlook")
        .first()
    )
    if not integration or integration.status != "connected":
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [],
        }

    # 2. Get fresh access token
    try:
        access_token = get_fresh_outlook_credentials(integration)
    except Exception as exc:
        logger.error(
            "outlook_signals: credential error firm %s: %s", firm_id, type(exc).__name__
        )
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [type(exc).__name__],
        }

    # 3. Fetch messages from last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    thirty_days_ago_iso = thirty_days_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        resp = http_requests.get(
            "https://graph.microsoft.com/v1.0/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={
                "$select": "id,conversationId,from,receivedDateTime,sender",
                "$filter": f"receivedDateTime ge {thirty_days_ago_iso}",
                "$top": "100",
            },
            timeout=30,
        )
        resp.raise_for_status()
        messages = resp.json().get("value", [])
    except Exception as exc:
        logger.error(
            "outlook_signals: message fetch error firm %s: %s", firm_id, type(exc).__name__
        )
        return {
            "firms_processed": 1,
            "clients_with_signals": 0,
            "threads_processed": 0,
            "errors": [type(exc).__name__],
        }

    firm_email = (integration.external_account_id or "").lower().strip()

    # 4. Group messages by conversationId
    conversations: dict[str, list[dict]] = defaultdict(list)
    for msg in messages:
        conv_id = msg.get("conversationId")
        if conv_id:
            conversations[conv_id].append(msg)

    # client_id -> list of per-conversation signal dicts
    client_threads: dict[UUID, list[dict]] = defaultdict(list)
    threads_processed = 0

    # 5. Process each conversation group
    for conv_id, conv_messages in conversations.items():
        try:
            # a. Extract from address and receivedDateTime per message
            msg_data: list[tuple[datetime, str]] = []
            for msg in conv_messages:
                raw_dt = msg.get("receivedDateTime", "")
                try:
                    ts = datetime.fromisoformat(raw_dt.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    continue
                from_addr = (
                    msg.get("from", {})
                    .get("emailAddress", {})
                    .get("address", "")
                    .lower()
                    .strip()
                )
                msg_data.append((ts, from_addr))

            if not msg_data:
                continue

            # b. Match to a client by email address scoped to firm_id
            all_from_addrs = {addr for _, addr in msg_data if addr}
            client_addrs = all_from_addrs - {firm_email} if firm_email else set(all_from_addrs)

            matched_client = None
            if client_addrs:
                matched_client = (
                    db.query(Client)
                    .filter(Client.email.in_(client_addrs), Client.firm_id == firm_id)
                    .first()
                )

            # c. If no client found: skip, discard addresses
            if not matched_client:
                del all_from_addrs, client_addrs, msg_data
                continue

            client_id = matched_client.id
            del all_from_addrs, client_addrs

            # d. Compute signals
            thread_depth = len(conv_messages)

            sorted_msgs = sorted(msg_data, key=lambda x: x[0])
            last_ts = sorted_msgs[-1][0] if sorted_msgs else None
            last_contact_date: Optional[str] = (
                last_ts.date().isoformat() if last_ts else None
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
                        thread_lag_values.append((ts_b - ts_a).total_seconds() / 3600.0)
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

        except Exception as exc:
            logger.error(
                "outlook_signals: conversation error firm %s conv %s: %s",
                firm_id,
                conv_id,
                type(exc).__name__,
            )
            errors.append(type(exc).__name__)
            continue

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

        log_event(
            event_type="outlook.signals_extracted",
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
                    "provider": "outlook",
                },
            )

        clients_with_signals += 1

    # 7. Return summary
    return {
        "firms_processed": 1,
        "clients_with_signals": clients_with_signals,
        "threads_processed": threads_processed,
        "errors": errors,
    }


def run_outlook_signals_for_all_firms() -> None:
    db = None
    try:
        db = SessionLocal()
        integrations = (
            db.query(Integration)
            .filter(Integration.provider == "outlook", Integration.status == "connected")
            .all()
        )

        total_firms = 0
        total_clients = 0
        total_threads = 0
        for integration in integrations:
            try:
                result = extract_outlook_signals(integration.firm_id, db)
                total_firms += result.get("firms_processed", 0)
                total_clients += result.get("clients_with_signals", 0)
                total_threads += result.get("threads_processed", 0)
            except Exception as exc:
                logger.error(
                    "outlook_signals: firm %s failed: %s",
                    integration.firm_id,
                    type(exc).__name__,
                )

        logger.info(
            "outlook_signals: done firms=%d clients_with_signals=%d threads_processed=%d",
            total_firms,
            total_clients,
            total_threads,
        )
    except Exception as exc:
        logger.error("outlook_signals: batch runner failed: %s", type(exc).__name__)
    finally:
        if db is not None:
            db.close()
