# app/services/qbo_budget_service.py

import logging
from datetime import datetime, timezone
from uuid import UUID

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crud import integration as crud_integration
from app.db.session import SessionLocal
from app.models.client import Client
from app.models.integration import Integration
from app.services.token_encryption import decrypt_token
from app.services.quickbooks_service import QuickBooksService
from app.core.enums import TriggerEvent
from app.services.automation_dispatcher import dispatch

logger = logging.getLogger(__name__)

QB_PROVIDER = "quickbooks"

_qb = QuickBooksService()


def _get_base_url() -> str:
    settings = get_settings()
    if settings.QUICKBOOKS_ENVIRONMENT == "sandbox":
        return "https://sandbox-quickbooks.api.intuit.com"
    return "https://quickbooks.api.intuit.com"


def _auth_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}


def _fetch_budget(base_url: str, realm_id: str, token: str) -> dict | None:
    """Return the most recent active Budget object, or None if none found."""
    try:
        url = f"{base_url}/v3/company/{realm_id}/query"
        resp = requests.get(
            url,
            headers=_auth_headers(token),
            params={"query": "SELECT * FROM Budget MAXRESULTS 10", "minorversion": "65"},
            timeout=8,
        )
        resp.raise_for_status()
        budgets = resp.json().get("QueryResponse", {}).get("Budget", [])
        if not budgets:
            return None
        return budgets[-1]
    except Exception:
        logger.warning("QBO budget: budget fetch failed realm=%s", realm_id)
        return None


def _parse_budget_for_month(budget: dict, year: int, month: int) -> dict[str, float]:
    """Build {account_name: budgeted_amount} for entries in the given year/month."""
    result: dict[str, float] = {}
    for detail in budget.get("BudgetDetail", []):
        budget_date_str = detail.get("BudgetDate", "")
        try:
            bd = datetime.strptime(budget_date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if bd.year != year or bd.month != month:
            continue
        account_name = detail.get("Account", {}).get("Name", "")
        amount = detail.get("Amount", 0)
        if account_name:
            try:
                result[account_name] = float(amount)
            except (ValueError, TypeError):
                pass
    return result


def _fetch_pl_actuals(base_url: str, realm_id: str, token: str) -> dict[str, float]:
    """Build {account_name: actual_amount} from the current month's P&L report."""
    try:
        url = f"{base_url}/v3/company/{realm_id}/reports/ProfitAndLoss"
        resp = requests.get(
            url,
            headers=_auth_headers(token),
            params={"minorversion": "65", "date_macro": "This Month"},
            timeout=8,
        )
        resp.raise_for_status()
        rows = resp.json().get("Rows", {}).get("Row", [])
        actuals: dict[str, float] = {}
        _walk_rows(rows, actuals)
        return actuals
    except Exception:
        logger.warning("QBO budget: P&L actuals fetch failed realm=%s", realm_id)
        return {}


def _walk_rows(rows: list, actuals: dict[str, float]) -> None:
    """Recursively walk report rows and extract Data row account values."""
    for row in rows:
        if row.get("type") == "Data":
            col_data = row.get("ColData", [])
            if len(col_data) >= 2:
                name = col_data[0].get("value", "").strip()
                try:
                    value = float(col_data[1].get("value", 0) or 0)
                except (ValueError, TypeError):
                    value = 0.0
                if name:
                    actuals[name] = value
        sub_rows = row.get("Rows", {}).get("Row", [])
        if sub_rows:
            _walk_rows(sub_rows, actuals)


def _calculate_variances(
    budget: dict[str, float], actuals: dict[str, float]
) -> list[dict]:
    flagged = []
    for account_name, budgeted in budget.items():
        if budgeted == 0:
            continue
        actual = actuals.get(account_name)
        if actual is None:
            continue
        variance_pct = (actual - budgeted) / abs(budgeted) * 100
        if abs(variance_pct) > 15:
            flagged.append({
                "account": account_name,
                "budgeted": budgeted,
                "actual": actual,
                "variance_pct": round(variance_pct, 2),
            })
    return flagged


def check_budget_variances_for_firm(firm_id: UUID, db: Session) -> None:
    integration = crud_integration.get_integration(db, firm_id=firm_id, provider=QB_PROVIDER)
    if not integration or not integration.encrypted_access_token:
        return

    try:
        integration = _qb.refresh_tokens_if_needed(integration, db)
    except Exception:
        logger.warning("QBO budget: token refresh failed firm=%s", firm_id)
        return

    access_token = decrypt_token(integration.encrypted_access_token)
    realm_id = integration.external_account_id
    base_url = _get_base_url()

    stmt = select(Client).where(
        Client.firm_id == firm_id,
        Client.quickbooks_customer_id.isnot(None),
    )
    clients = list(db.execute(stmt).scalars().all())

    now = datetime.now(timezone.utc)
    current_year = now.year
    current_month = now.month

    for client in clients:
        try:
            raw_budget = _fetch_budget(base_url, realm_id, access_token)
            if raw_budget is None:
                continue

            budget_map = _parse_budget_for_month(raw_budget, current_year, current_month)
            if not budget_map:
                continue

            actuals_map = _fetch_pl_actuals(base_url, realm_id, access_token)
            flagged_items = _calculate_variances(budget_map, actuals_map)

            if not flagged_items:
                continue

            dispatch(
                event=TriggerEvent.qbo_budget_variance,
                payload={
                    "firm_id": str(firm_id),
                    "client_id": str(client.id),
                    "client_name": client.name,
                    "variances": flagged_items,
                    "variance_count": len(flagged_items),
                    "checked_at": now.isoformat(),
                },
            )
        except Exception:
            logger.warning(
                "QBO budget: variance check failed for client=%s firm=%s",
                client.id,
                firm_id,
            )


def run_budget_variance_checks() -> None:
    db = SessionLocal()
    try:
        stmt = select(Integration).where(
            Integration.provider == QB_PROVIDER,
            Integration.status == "connected",
            Integration.encrypted_access_token.isnot(None),
        )
        integrations = list(db.execute(stmt).scalars().all())
        for integration in integrations:
            try:
                check_budget_variances_for_firm(integration.firm_id, db)
            except Exception:
                logger.warning(
                    "QBO budget: firm-level check failed firm=%s", integration.firm_id
                )
    except Exception:
        logger.exception("QBO budget: run_budget_variance_checks failed")
    finally:
        db.close()
