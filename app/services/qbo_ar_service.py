# app/services/qbo_ar_service.py

import logging
from datetime import datetime, timezone, timedelta, date
from uuid import UUID

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.services.token_encryption import decrypt_token

logger = logging.getLogger(__name__)

QB_PROVIDER = "quickbooks"
_CACHE: dict[str, tuple[dict, datetime]] = {}
_CACHE_TTL = timedelta(minutes=15)


def _get_base_url() -> str:
    settings = get_settings()
    if settings.QUICKBOOKS_ENVIRONMENT == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return "https://quickbooks.api.intuit.com"


def _parse_ar_report(data: dict) -> tuple[float, date | None]:
    """Parse AgedReceivableDetail report. Returns (total_open_balance, latest_date)."""
    try:
        columns = data.get("Columns", {}).get("Column", [])
        col_titles = [c.get("ColTitle", "") for c in columns]

        balance_idx: int | None = None
        date_idx: int | None = None

        for i, title in enumerate(col_titles):
            if "Open Balance" in title and balance_idx is None:
                balance_idx = i
            if title in ("Date", "Txn Date") and date_idx is None:
                date_idx = i

        total_balance = 0.0
        latest_date: date | None = None

        def process_rows(rows: list) -> None:
            nonlocal total_balance, latest_date
            for row in rows:
                row_type = row.get("type", "")
                if row_type == "Data":
                    col_data = row.get("ColData", [])
                    if balance_idx is not None and balance_idx < len(col_data):
                        try:
                            val = col_data[balance_idx].get("value", "")
                            if val:
                                total_balance += float(val)
                        except (ValueError, TypeError):
                            pass
                    if date_idx is not None and date_idx < len(col_data):
                        try:
                            val = col_data[date_idx].get("value", "")
                            if val:
                                d = date.fromisoformat(val)
                                if latest_date is None or d > latest_date:
                                    latest_date = d
                        except (ValueError, TypeError):
                            pass
                elif row_type == "Section":
                    sub_rows = row.get("Rows", {}).get("Row", [])
                    if sub_rows:
                        process_rows(sub_rows)

        top_rows = data.get("Rows", {}).get("Row", [])
        process_rows(top_rows)

        return round(total_balance, 2), latest_date

    except Exception:
        return 0.0, None


def get_qbo_ar_balance(firm_id: UUID, qb_customer_id: str, db: Session) -> dict:
    """Fetch AR balance for a customer from QBO. Fails silently with zeros."""
    cache_key = f"{firm_id}:{qb_customer_id}"
    now = datetime.now(timezone.utc)

    if cache_key in _CACHE:
        cached_result, cached_at = _CACHE[cache_key]
        if now - cached_at < _CACHE_TTL:
            return cached_result

    default = {"connected": True, "outstanding_balance": 0.0, "last_payment_date": None}

    try:
        integration = crud_integration.get_integration(db, firm_id=firm_id, provider=QB_PROVIDER)
        if not integration or not integration.encrypted_access_token:
            _CACHE[cache_key] = (default, now)
            return default

        access_token = decrypt_token(integration.encrypted_access_token)
        realm_id = integration.external_account_id
        base_url = _get_base_url()

        url = f"{base_url}/v3/company/{realm_id}/reports/AgedReceivableDetail"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        params = {"customer": qb_customer_id}

        resp = requests.get(url, headers=headers, params=params, timeout=5)
        resp.raise_for_status()

        balance, last_payment_date = _parse_ar_report(resp.json())
        result = {
            "connected": True,
            "outstanding_balance": balance,
            "last_payment_date": last_payment_date,
        }
        _CACHE[cache_key] = (result, now)
        return result

    except requests.exceptions.Timeout:
        logger.warning("QBO AR request timed out for firm %s", firm_id)
        return {"connected": True, "outstanding_balance": 0.0, "last_payment_date": None}
    except Exception:
        logger.warning("QBO AR fetch failed for firm=%s customer=%s", firm_id, qb_customer_id)
        _CACHE[cache_key] = (default, now)
        return default
