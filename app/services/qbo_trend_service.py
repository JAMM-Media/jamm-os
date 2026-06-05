# app/services/qbo_trend_service.py

import logging
import threading
from calendar import monthrange
from datetime import datetime, timezone, timedelta, date
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


def _month_windows() -> list[tuple[date, date, str]]:
    today = date.today()
    windows = []
    for offset in range(3):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        label = date(year, month, 1).strftime("%b %Y")
        if offset == 0:
            start = date(year, month, 1)
            end = today
        else:
            start = date(year, month, 1)
            end = date(year, month, monthrange(year, month)[1])
        windows.append((start, end, label))
    return windows


def _fetch_pl_month(base_url: str, realm_id: str, token: str, start: date, end: date) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/ProfitAndLoss"
        resp = requests.get(url, headers=_auth_headers(token), params={
            "minorversion": "65",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])
        income = _find_group_value(rows, "TotalIncome")
        expenses = _find_group_value(rows, "TotalExpenses")
        net = None if (income is None or expenses is None) else income - expenses
        return {"total_income": income, "total_expenses": expenses, "net_income": net}
    except Exception:
        logger.warning("QBO trends: P&L fetch failed realm=%s start=%s", realm_id, start)
        return {"total_income": None, "total_expenses": None, "net_income": None}


def _fetch_bs_month(base_url: str, realm_id: str, token: str, start: date, end: date) -> dict:
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/BalanceSheet"
        resp = requests.get(url, headers=_auth_headers(token), params={
            "minorversion": "65",
            "accounting_method": "Accrual",
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
        }, timeout=8)
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])
        return {
            "total_assets": _find_group_value(rows, "TotalAssets"),
            "total_liabilities": _find_group_value(rows, "TotalLiabilities"),
            "total_equity": _find_group_value(rows, "Equity"),
        }
    except Exception:
        logger.warning("QBO trends: BalanceSheet fetch failed realm=%s start=%s", realm_id, start)
        return {"total_assets": None, "total_liabilities": None, "total_equity": None}


def _direction(current: float | None, prior: float | None) -> str:
    if current is None or prior is None:
        return "unavailable"
    if prior == 0:
        return "up" if current > 0 else "flat"
    pct_change = (current - prior) / abs(prior)
    if pct_change > 0.05:
        return "up"
    if pct_change < -0.05:
        return "down"
    return "flat"


_UNAVAILABLE: dict = {
    "connected": False,
    "months": [],
    "trends": {},
    "checked_at": None,
}


def get_pl_and_bs_trends(client, firm_id: UUID, db: Session) -> dict:
    if not client.quickbooks_customer_id:
        return _UNAVAILABLE

    cache_key = f"trends:{firm_id}:{client.id}"
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
        logger.warning("QBO trends: token refresh failed firm=%s", firm_id)
        return _UNAVAILABLE

    access_token = decrypt_token(integration.encrypted_access_token)
    realm_id = integration.external_account_id
    base_url = _get_base_url()

    windows = _month_windows()
    months = []
    for start, end, label in windows:
        pl = _fetch_pl_month(base_url, realm_id, access_token, start, end)
        bs = _fetch_bs_month(base_url, realm_id, access_token, start, end)
        months.append({
            "label": label,
            "total_income": pl["total_income"],
            "total_expenses": pl["total_expenses"],
            "net_income": pl["net_income"],
            "total_assets": bs["total_assets"],
            "total_liabilities": bs["total_liabilities"],
            "total_equity": bs["total_equity"],
        })

    m0, m1 = months[0], months[1]
    trends = {
        "income": _direction(m0["total_income"], m1["total_income"]),
        "expenses": _direction(m0["total_expenses"], m1["total_expenses"]),
        "net_income": _direction(m0["net_income"], m1["net_income"]),
        "assets": _direction(m0["total_assets"], m1["total_assets"]),
        "equity": _direction(m0["total_equity"], m1["total_equity"]),
    }

    result = {
        "connected": True,
        "months": months,
        "trends": trends,
        "checked_at": now,
    }

    _CACHE[cache_key] = (result, now)

    threading.Thread(
        target=log_event,
        kwargs={
            "event_type": "integration.qbo_trends_viewed",
            "firm_id": firm_id,
            "entity_type": "client",
            "entity_id": client.id,
            "metadata": {"months_returned": len(months)},
        },
        daemon=True,
    ).start()

    return result
