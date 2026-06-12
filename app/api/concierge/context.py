# app/api/concierge/context.py

import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.irs_authorization import IrsAuthorization
from app.models.user import User
from datetime import datetime, timezone, timedelta
from app.models.behavioral_event import BehavioralEvent
from app.models.document_request import DocumentRequest
from app.dependencies.tenant import get_current_firm

router = APIRouter()

_context_cache: dict = {}
_CACHE_TTL = 60


def _cache_get(firm_id: uuid.UUID) -> Optional[dict]:
    entry = _context_cache.get(str(firm_id))
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _cache_set(firm_id: uuid.UUID, data: dict) -> None:
    _context_cache[str(firm_id)] = {"data": data, "ts": time.time()}


def get_firm_context(firm_id: uuid.UUID, db: Session) -> dict:
    cached = _cache_get(firm_id)
    if cached:
        return cached

    data = _run_queries(firm_id, db)
    _cache_set(firm_id, data)
    return data


def _run_queries(firm_id: uuid.UUID, db: Session) -> dict:
    client_stats = _query_client_stats(firm_id, db)
    import_log = _query_import_log(firm_id, db)
    onboarding_steps = _query_onboarding_steps(firm_id, db)
    engagement_summary = _query_engagement_summary(firm_id, db)
    staff_summary = _query_staff_summary(firm_id, db)
    portal_adoption = _query_portal_adoption(firm_id, db)
    irs_coverage = _query_irs_coverage(firm_id, db)
    upcoming_deadlines = _query_upcoming_deadlines(firm_id, db)
    overdue_document_requests = _query_overdue_document_requests(firm_id, db)
    stale_engagements = _query_stale_engagements(firm_id, db)
    firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()
    firm_type = firm.firm_type if firm else None
    return {
        "client_count": client_stats["total"],
        "clients_missing_email": client_stats["missing_email"],
        "clients_inactive": client_stats["inactive"],
        "import_log": import_log,
        "onboarding_steps": onboarding_steps,
        "engagement_summary": engagement_summary,
        "staff_summary": staff_summary,
        "portal_adoption": portal_adoption,
        "irs_coverage": irs_coverage,
        "upcoming_deadlines": upcoming_deadlines,
        "overdue_document_requests": overdue_document_requests,
        "stale_engagements": stale_engagements,
        "firm_type": firm_type,
    }


# ---------------------------------------------------------------------------
# Query 1 -- client stats
# ---------------------------------------------------------------------------
def _query_client_stats(firm_id: uuid.UUID, db: Session) -> dict:
    total = db.execute(
        select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
    ).scalar() or 0

    missing_email = db.execute(
        select(func.count()).select_from(Client).where(
            Client.firm_id == firm_id,
            (Client.email == None) | (Client.email == ""),
        )
    ).scalar() or 0

    inactive = db.execute(
        select(func.count()).select_from(Client).where(
            Client.firm_id == firm_id,
            Client.is_active == False,
        )
    ).scalar() or 0

    return {"total": total, "missing_email": missing_email, "inactive": inactive}


# ---------------------------------------------------------------------------
# Query 2 -- import log
# The app writes client.created events (one per client) when clients are
# added through the app. There is no import-batch event.
# ---------------------------------------------------------------------------
def _query_import_log(firm_id: uuid.UUID, db: Session) -> dict:
    app_created_count = db.execute(
        select(func.count()).select_from(BehavioralEvent).where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "client.created",
        )
    ).scalar() or 0

    recent_rows = db.execute(
        select(BehavioralEvent.event_type, BehavioralEvent.occurred_at)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "client.created",
        )
        .order_by(BehavioralEvent.occurred_at.desc())
        .limit(5)
    ).fetchall()

    recent = [
        {"event_type": r.event_type, "occurred_at": r.occurred_at.isoformat()}
        for r in recent_rows
    ]

    return {
        "app_created_count": app_created_count,
        "recent_client_events": recent,
        "note": (
            "Clients in this firm were added directly to the database, not through the app import flow."
            if app_created_count == 0
            else f"{app_created_count} client(s) added through the app."
        ),
    }


# ---------------------------------------------------------------------------
# Query 3 -- onboarding steps
# client_import: clients table count (works regardless of how clients arrived)
# staff_invited: users table count > 1 (no behavioral event is written)
# portal_magic_link_sent: event_type = 'client.portal_invited'
# automation_enabled: event_type = 'firm.automation_enabled'
# engagement_created: event_type = 'engagement.created'
# ---------------------------------------------------------------------------
def _query_onboarding_steps(firm_id: uuid.UUID, db: Session) -> dict:
    def _has_event(event_type: str) -> bool:
        return (
            db.execute(
                select(func.count()).select_from(BehavioralEvent).where(
                    BehavioralEvent.firm_id == firm_id,
                    BehavioralEvent.event_type == event_type,
                )
            ).scalar()
            or 0
        ) > 0

    client_imported = (
        db.execute(
            select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
        ).scalar()
        or 0
    ) > 0

    engagement_created = _has_event("engagement.created")

    total_staff = (
        db.execute(
            select(func.count()).select_from(User).where(User.firm_id == firm_id)
        ).scalar()
        or 0
    )
    staff_invited = total_staff > 1

    portal_magic_link_sent = _has_event("client.portal_invited")
    automation_enabled = _has_event("firm.automation_enabled")

    step_results = [
        ("client_import", client_imported),
        ("engagement_created", engagement_created),
        ("staff_invited", staff_invited),
        ("portal_magic_link_sent", portal_magic_link_sent),
        ("automation_enabled", automation_enabled),
    ]

    completed = [step for step, done in step_results if done]
    incomplete = [step for step, done in step_results if not done]

    return {
        "completed": completed,
        "incomplete": incomplete,
        "all_complete": len(incomplete) == 0,
    }


# ---------------------------------------------------------------------------
# Query 4 -- engagement summary
# ---------------------------------------------------------------------------
def _query_engagement_summary(firm_id: uuid.UUID, db: Session) -> dict:
    rows = db.execute(
        select(Engagement.status, func.count())
        .where(Engagement.firm_id == firm_id)
        .group_by(Engagement.status)
    ).fetchall()

    by_status = {str(r[0]): r[1] for r in rows}
    total = sum(by_status.values())

    clients_with_no_engagement = db.execute(
        select(func.count()).select_from(Client).where(
            Client.firm_id == firm_id,
            ~Client.id.in_(
                select(Engagement.client_id).where(Engagement.firm_id == firm_id)
            ),
        )
    ).scalar() or 0

    return {
        "total": total,
        "by_status": by_status,
        "clients_with_no_engagement": clients_with_no_engagement,
    }


# ---------------------------------------------------------------------------
# Query 5 -- staff summary
# ---------------------------------------------------------------------------
def _query_staff_summary(firm_id: uuid.UUID, db: Session) -> dict:
    total = db.execute(
        select(func.count()).select_from(User).where(User.firm_id == firm_id)
    ).scalar() or 0

    return {"total": total}


# ---------------------------------------------------------------------------
# Query 6 -- portal adoption
# ---------------------------------------------------------------------------
def _query_portal_adoption(firm_id: uuid.UUID, db: Session) -> dict:
    total_clients = db.execute(
        select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
    ).scalar() or 0

    logged_in = db.execute(
        select(func.count(func.distinct(BehavioralEvent.entity_id))).where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "portal.first_login",
        )
    ).scalar() or 0

    access_enabled = db.execute(
        select(func.count()).select_from(Client).where(
            Client.firm_id == firm_id,
            Client.portal_access_enabled == True,
        )
    ).scalar() or 0

    return {
        "logged_in": logged_in,
        "access_enabled": access_enabled,
        "total_clients": total_clients,
    }


# ---------------------------------------------------------------------------
# Query 7 -- IRS authorization coverage
# ---------------------------------------------------------------------------
def _query_irs_coverage(firm_id: uuid.UUID, db: Session) -> dict:
    total_clients = db.execute(
        select(func.count()).select_from(Client).where(Client.firm_id == firm_id)
    ).scalar() or 0

    with_auth = db.execute(
        select(func.count(func.distinct(IrsAuthorization.client_id))).where(
            IrsAuthorization.firm_id == firm_id
        )
    ).scalar() or 0

    return {"with_auth": with_auth, "total_clients": total_clients}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# GET /concierge/context
# ---------------------------------------------------------------------------
@router.get("/context")
def get_context_endpoint(
    current_firm=Depends(get_current_firm),
    db: Session = Depends(get_db),
):
    return get_firm_context(firm_id=current_firm.id, db=db)


# ---------------------------------------------------------------------------
# Query: upcoming_deadlines
# ---------------------------------------------------------------------------
def _query_upcoming_deadlines(firm_id: uuid.UUID, db: Session) -> list:
    now = datetime.now(timezone.utc).date()
    rows = db.execute(
        select(
            Engagement.name.label('engagement_name'),
            Client.name.label('client_name'),
            Engagement.filing_deadline,
            Engagement.status,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.filing_deadline.isnot(None),
            Engagement.status.notin_(['completed', 'archived', 'cancelled']),
        )
        .order_by(Engagement.filing_deadline.asc())
        .limit(5)
    ).all()
    return [
        {
            "name": r.engagement_name,
            "client_name": r.client_name,
            "due_date": r.filing_deadline.isoformat() if r.filing_deadline else None,
            "status": str(r.status),
            "is_past_due": r.filing_deadline < now if r.filing_deadline else False,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Query: all_engagements (unfiltered, for detail briefing)
# ---------------------------------------------------------------------------
def _query_all_engagements(firm_id: uuid.UUID, db: Session) -> list:
    rows = db.execute(
        select(
            Engagement.name.label("engagement_name"),
            Client.name.label("client_name"),
            Engagement.status,
            Engagement.updated_at,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(Engagement.firm_id == firm_id)
        .order_by(Engagement.updated_at.desc())
    ).all()
    now = datetime.now(timezone.utc)
    return [
        {
            "name": r.engagement_name,
            "client_name": r.client_name,
            "status": r.status,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "days_since_update": (now - r.updated_at).days if r.updated_at else None,
        }
        for r in rows
    ]


def get_firm_context_detail(firm_id: uuid.UUID, db: Session) -> dict:
    data = get_firm_context(firm_id, db)
    data = dict(data)
    data["all_engagements_with_staleness"] = _query_all_engagements(firm_id, db)
    data.pop("stale_engagements", None)
    return data


# ---------------------------------------------------------------------------
# Query: overdue_document_requests
# ---------------------------------------------------------------------------
def _query_overdue_document_requests(firm_id: uuid.UUID, db: Session) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=5)
    rows = db.execute(
        select(DocumentRequest.title, Client.name)
        .join(Client, DocumentRequest.client_id == Client.id)
        .where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status != 'complete',
            DocumentRequest.created_at <= cutoff,
        )
        .order_by(DocumentRequest.created_at.asc())
        .limit(10)
    ).all()
    return [
        {"title": r.title, "client_name": r.name}
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Query: stale_engagements
# ---------------------------------------------------------------------------
def _query_stale_engagements(firm_id: uuid.UUID, db: Session) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    rows = db.execute(
        select(
            Engagement.name.label('engagement_name'),
            Client.name.label('client_name'),
            Engagement.status,
            Engagement.updated_at,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.updated_at <= cutoff,
            Engagement.status.notin_(['complete', 'cancelled']),
        )
        .order_by(Engagement.updated_at.asc())
        .limit(10)
    ).all()
    now = datetime.now(timezone.utc)
    return [
        {
            "name": r.engagement_name,
            "client_name": r.client_name,
            "status": r.status,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "days_since_update": (now - r.updated_at).days if r.updated_at else None,
        }
        for r in rows
    ]
