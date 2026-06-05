# app/services/qbo_income_cashflow_service.py

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


def _find_summary_row_value(rows: list) -> float | None:
    """Fall back for flat CustomerIncome reports: read the last Summary row's first numeric ColData value."""
    last_value = None
    for row in rows:
        if row.get("type") == "Summary":
            col_data = row.get("ColData", [])
            if col_data:
                try:
                    last_value = float(col_data[0].get("value", 0) or 0)
                except (ValueError, TypeError):
                    pass
        sub_rows = row.get("Rows", {}).get("Row", [])
        if sub_rows:
            sub_val = _find_summary_row_value(sub_rows)
            if sub_val is not None:
                last_value = sub_val
    return last_value


_INCOME_UNAVAILABLE: dict = {
    "connected": False,
    "period": None,
    "total_income": None,
    "checked_at": None,
}

_CASHFLOW_UNAVAILABLE: dict = {
    "connected": False,
    "period": None,
    "operating": None,
    "investing": None,
    "financing": None,
    "net_change": None,
    "checked_at": None,
}


def _get_integration(firm_id: UUID, db: Session):
    integration = crud_integration.get_integration(db, firm_id=firm_id, provider=QB_PROVIDER)
    if not integration or not integration.encrypted_access_token:
        return None
    try:
        integration = _qb.refresh_tokens_if_needed(integration, db)
    except Exception:
        logger.warning("QBO income/cashflow: token refresh failed firm=%s", firm_id)
        return None
    return integration


def get_customer_income(client, firm_id: UUID, db: Session) -> dict:
    if not client.quickbooks_customer_id:
        return _INCOME_UNAVAILABLE

    cache_key = f"income:{firm_id}:{client.id}"
    now = datetime.now(timezone.utc)

    if cache_key in _CACHE:
        cached_result, cached_at = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_result

    integration = _get_integration(firm_id, db)
    if not integration:
        return _INCOME_UNAVAILABLE

    access_token = decrypt_token(integration.encrypted_access_token)
    realm_id = integration.external_account_id
    base_url = _get_base_url()
    period = "This Fiscal Year"

    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/CustomerIncome"
        resp = requests.get(url, headers=_auth_headers(access_token), params={
            "minorversion": "65",
            "customer": client.quickbooks_customer_id,
            "date_macro": period,
        }, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("Rows", {}).get("Row", [])

        total_income = _find_group_value(rows, "TotalIncome")
        if total_income is None:
            total_income = _find_summary_row_value(rows)

        result = {
            "connected": True,
            "period": period,
            "total_income": total_income,
            "checked_at": now,
        }
    except Exception:
        logger.warning("QBO income: CustomerIncome fetch failed realm=%s client=%s", realm_id, client.id)
        return _INCOME_UNAVAILABLE

    _CACHE[cache_key] = (result, now)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "integration.qbo_customer_income_viewed",
            "firm_id": firm_id,
            "entity_type": "client",
            "entity_id": client.id,
            "metadata": {},
        },
        daemon=True,
    ).start()

    return result


def get_cash_flow(client, firm_id: UUID, db: Session) -> dict:
    if not client.quickbooks_customer_id:
        return _CASHFLOW_UNAVAILABLE

    cache_key = f"cashflow:{firm_id}:{client.id}"
    now = datetime.now(timezone.utc)

    if cache_key in _CACHE:
        cached_result, cached_at = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_result

    integration = _get_integration(firm_id, db)
    if not integration:
        return _CASHFLOW_UNAVAILABLE

    access_token = decrypt_token(integration.encrypted_access_token)
    realm_id = integration.external_account_id
    base_url = _get_base_url()
    period = "Last 3 Months"

    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/CashFlow"
        resp = requests.get(url, headers=_auth_headers(access_token), params={
            "minorversion": "65",
            "date_macro": period,
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])

        operating = (
            _find_group_value(rows, "NetCashOperatingActivities")
            or _find_group_value(rows, "Operating Activities")
        )
        investing = (
            _find_group_value(rows, "NetCashInvestingActivities")
            or _find_group_value(rows, "Investing Activities")
        )
        financing = (
            _find_group_value(rows, "NetCashFinancingActivities")
            or _find_group_value(rows, "Financing Activities")
        )

        net_change = None
        if operating is not None and investing is not None and financing is not None:
            net_change = operating + investing + financing

        result = {
            "connected": True,
            "period": period,
            "operating": operating,
            "investing": investing,
            "financing": financing,
            "net_change": net_change,
            "checked_at": now,
        }
    except Exception:
        logger.warning("QBO cashflow: CashFlow fetch failed realm=%s client=%s", realm_id, client.id)
        return _CASHFLOW_UNAVAILABLE

    _CACHE[cache_key] = (result, now)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "integration.qbo_cash_flow_viewed",
            "firm_id": firm_id,
            "entity_type": "client",
            "entity_id": client.id,
            "metadata": {},
        },
        daemon=True,
    ).start()

    return result
