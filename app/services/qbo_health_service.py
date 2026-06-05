# app/services/qbo_health_service.py

import logging
import threading
from datetime import datetime, timezone, timedelta
from uuid import UUID

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.services.token_encryption import decrypt_token
from app.services.quickbooks_service import QuickBooksService
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)

QB_PROVIDER = "quickbooks"
_CACHE: dict[str, tuple[dict, datetime]] = {}
_CACHE_TTL = timedelta(minutes=30)

_qb = QuickBooksService()


def _get_base_url() -> str:
    settings = get_settings()
    if settings.QUICKBOOKS_ENVIRONMENT == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return "https://quickbooks.api.intuit.com"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


# ----------------------------------------------------------------
# Report parsing helpers
# ----------------------------------------------------------------

def _cdc_has_changes(data: dict) -> bool:
    for cdc_entry in data.get("CDCResponse", []):
        for qr in cdc_entry.get("QueryResponse", []):
            for key, val in qr.items():
                if key not in ("startPosition", "maxResults", "totalCount") and isinstance(val, list) and val:
                    return True
    return False


def _find_group_value(rows: list, group: str) -> float | None:
    for row in rows:
        if row.get("group") == group:
            summary = row.get("Summary", {})
            col_data = summary.get("ColData", [])
            if col_data:
                try:
                    return float(col_data[0].get("value", 0) or 0)
                except (ValueError, TypeError):
                    return 0.0
        sub_rows = row.get("Rows", {}).get("Row", [])
        if sub_rows:
            result = _find_group_value(sub_rows, group)
            if result is not None:
                return result
    return None


def _count_data_rows(rows: list) -> int:
    count = 0
    for row in rows:
        if row.get("type") == "Data":
            count += 1
        sub = row.get("Rows", {}).get("Row", [])
        if sub:
            count += _count_data_rows(sub)
    return count


# ----------------------------------------------------------------
# Five signals
# ----------------------------------------------------------------

def _signal_reconciliation(base_url: str, realm_id: str, token: str) -> dict:
    try:
        now = datetime.now(timezone.utc)
        url = f"{base_url}/v3/company/{realm_id}/cdc"
        hdrs = _auth_headers(token)

        resp = requests.get(url, headers=hdrs, params={
            "entities": "Bill,Payment,Deposit",
            "changedSince": (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, timeout=8)
        resp.raise_for_status()
        if _cdc_has_changes(resp.json()):
            return {"status": "green", "finding": "Transaction activity detected in the last 30 days. Books appear current."}

        resp60 = requests.get(url, headers=hdrs, params={
            "entities": "Bill,Payment,Deposit",
            "changedSince": (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }, timeout=8)
        resp60.raise_for_status()
        if _cdc_has_changes(resp60.json()):
            return {"status": "amber", "finding": "No activity in the last 30 days, but activity found within 60 days. Books may be falling behind."}
        return {"status": "red", "finding": "No transaction activity detected in the last 60 days. Books are likely stale."}
    except Exception:
        logger.warning("QBO health: reconciliation signal failed realm=%s", realm_id)
        return {"status": "amber", "finding": "Could not retrieve reconciliation data from QuickBooks."}


def _signal_balance_sheet(base_url: str, realm_id: str, token: str) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/BalanceSheet"
        resp = requests.get(url, headers=_auth_headers(token), params={
            "minorversion": "65", "accounting_method": "Accrual",
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])

        assets = _find_group_value(rows, "TotalAssets")
        liabilities = _find_group_value(rows, "TotalLiabilities")
        equity = _find_group_value(rows, "Equity")

        zeros = sum(1 for v in (assets, liabilities, equity) if not v)
        if zeros == 0:
            return {"status": "green", "finding": "Assets, liabilities, and equity all present. Balance sheet appears complete."}
        if zeros == 1:
            return {"status": "amber", "finding": "One balance sheet component is missing or zero. May indicate incomplete data."}
        return {"status": "red", "finding": "Multiple balance sheet components are missing. Books may be incomplete or misconfigured."}
    except Exception:
        logger.warning("QBO health: balance sheet signal failed realm=%s", realm_id)
        return {"status": "amber", "finding": "Could not retrieve balance sheet data from QuickBooks."}


def _signal_pl_activity(base_url: str, realm_id: str, token: str) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/ProfitAndLoss"
        hdrs = _auth_headers(token)

        def _get_pl(date_macro: str) -> tuple[float, float]:
            r = requests.get(url, headers=hdrs, params={
                "minorversion": "65", "date_macro": date_macro,
            }, timeout=8)
            r.raise_for_status()
            rows = r.json().get("Rows", {}).get("Row", [])
            income = _find_group_value(rows, "TotalIncome") or 0.0
            expenses = _find_group_value(rows, "TotalExpenses") or 0.0
            return income, expenses

        this_income, this_expenses = _get_pl("This Month")
        if this_income or this_expenses:
            return {"status": "green", "finding": "Income or expenses recorded this month. P&L activity looks normal."}

        last_income, last_expenses = _get_pl("Last Month")
        if last_income or last_expenses:
            return {"status": "amber", "finding": "No activity this month, but last month had entries. Worth monitoring."}

        return {"status": "red", "finding": "No income or expenses recorded this month or last month. P&L appears inactive."}
    except Exception:
        logger.warning("QBO health: P&L signal failed realm=%s", realm_id)
        return {"status": "amber", "finding": "Could not retrieve P&L data from QuickBooks."}


def _signal_transaction_recency(base_url: str, realm_id: str, token: str) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/TransactionList"
        resp = requests.get(url, headers=_auth_headers(token), params={
            "minorversion": "65", "date_macro": "Last 30 Days",
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])
        count = _count_data_rows(rows)
        if count >= 5:
            return {"status": "green", "finding": f"{count} transactions recorded in the last 30 days. Activity level looks healthy."}
        if count >= 1:
            return {"status": "amber", "finding": f"Only {count} transaction(s) recorded in the last 30 days. Activity is lower than expected."}
        return {"status": "red", "finding": "No transactions recorded in the last 30 days. Books may not be up to date."}
    except Exception:
        logger.warning("QBO health: transaction recency signal failed realm=%s", realm_id)
        return {"status": "amber", "finding": "Could not retrieve transaction data from QuickBooks."}


def _signal_gl_recency(base_url: str, realm_id: str, token: str) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/GeneralLedger"
        resp = requests.get(url, headers=_auth_headers(token), params={
            "minorversion": "65",
            "date_macro": "Last 30 Days",
            "columns": "tx_date,account_name,amount",
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])
        if _count_data_rows(rows) > 0:
            return {"status": "green", "finding": "General ledger entries found in the last 30 days. Ledger appears current."}
        return {"status": "red", "finding": "No general ledger entries in the last 30 days. Ledger may be stale."}
    except Exception:
        logger.warning("QBO health: GL recency signal failed realm=%s", realm_id)
        return {"status": "amber", "finding": "Could not retrieve general ledger data from QuickBooks."}


# ----------------------------------------------------------------
# Composite scoring
# ----------------------------------------------------------------

def _composite_status(signals: dict) -> str:
    if any(v["status"] == "red" for v in signals.values()):
        return "red"
    if any(v["status"] == "amber" for v in signals.values()):
        return "amber"
    return "green"


# ----------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------

_UNAVAILABLE: dict = {
    "connected": False,
    "status": "unavailable",
    "signals": {},
    "checked_at": None,
}


def get_bookkeeping_health(client, firm_id: UUID, db: Session) -> dict:
    if not client.quickbooks_customer_id:
        return _UNAVAILABLE

    cache_key = f"{firm_id}:{client.id}"
    now = datetime.now(timezone.utc)

    if cache_key in _CACHE:
        cached_result, cached_at = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_result

    integration = crud_integration.get_integration(db, firm_id=firm_id, provider=QB_PROVIDER)
    if not integration or not integration.encrypted_access_token:
        return _UNAVAILABLE

    try:
        integration = _qb.refresh_tokens_if_needed(integration, db)
    except Exception:
        logger.warning("QBO health: token refresh failed firm=%s", firm_id)
        return _UNAVAILABLE

    access_token = decrypt_token(integration.encrypted_access_token)
    realm_id = integration.external_account_id
    base_url = _get_base_url()

    signals = {
        "reconciliation": _signal_reconciliation(base_url, realm_id, access_token),
        "balance_sheet": _signal_balance_sheet(base_url, realm_id, access_token),
        "pl_activity": _signal_pl_activity(base_url, realm_id, access_token),
        "transaction_recency": _signal_transaction_recency(base_url, realm_id, access_token),
        "gl_recency": _signal_gl_recency(base_url, realm_id, access_token),
    }

    overall = _composite_status(signals)
    result = {
        "connected": True,
        "status": overall,
        "signals": signals,
        "checked_at": now,
    }

    _CACHE[cache_key] = (result, now)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "integration.qbo_health_checked",
            "firm_id": firm_id,
            "entity_type": "client",
            "entity_id": client.id,
            "metadata": {"status": overall},
        },
        daemon=True,
    ).start()

    return result
