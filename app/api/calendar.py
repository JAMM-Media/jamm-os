# app/api/calendar.py

import re
import threading
from datetime import date, timedelta, timezone, datetime
from typing import Optional

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_firm_owner
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.integration import Integration
from app.models.user import User
from app.services.behavioral_log import log_event

router = APIRouter(prefix="/calendar", tags=["calendar"])

DEFAULT_EVENT_COLORS = {
    "deadline": "#EF4444",
    "extension": "#F97316",
    "task": "#3B82F6",
    "call": "#22C55E",
    "holiday": "#9CA3AF",
}
DEFAULT_CUSTOM_CATEGORIES: list = []

HEX_RE = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')


def _is_valid_hex(color: str) -> bool:
    return bool(HEX_RE.match(color))


def _get_user_integration(db: Session, firm_id, user_id, provider: str) -> Optional[Integration]:
    return (
        db.query(Integration)
        .filter(
            Integration.firm_id == firm_id,
            Integration.user_id == user_id,
            Integration.provider == provider,
            Integration.status == "connected",
        )
        .first()
    )


# ---------------------------------------------------------------------------
# GET /calendar/staff-colors
# ---------------------------------------------------------------------------

@router.get("/staff-colors")
def get_staff_colors(
    current_firm: Firm = Depends(get_current_firm),
):
    colors = current_firm.staff_calendar_colors or {}
    return {"colors": colors}


# ---------------------------------------------------------------------------
# PATCH /calendar/staff-colors
# ---------------------------------------------------------------------------

class StaffColorBody(BaseModel):
    user_id: str
    color: str


@router.patch("/staff-colors")
def patch_staff_colors(
    body: StaffColorBody,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_firm_owner),
):
    if not _is_valid_hex(body.color):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="color must be a valid hex string starting with # (4 or 7 chars total)",
        )
    existing = dict(current_firm.staff_calendar_colors or {})
    existing[body.user_id] = body.color
    current_firm.staff_calendar_colors = existing
    db.add(current_firm)
    db.commit()
    db.refresh(current_firm)
    return {"colors": current_firm.staff_calendar_colors}


# ---------------------------------------------------------------------------
# GET /calendar/my-settings
# ---------------------------------------------------------------------------

@router.get("/my-settings")
def get_my_settings(
    current_user: User = Depends(get_current_user),
):
    if not current_user.calendar_settings:
        return {
            "colors": DEFAULT_EVENT_COLORS,
            "custom_categories": DEFAULT_CUSTOM_CATEGORIES,
        }
    settings = current_user.calendar_settings
    colors = {**DEFAULT_EVENT_COLORS, **(settings.get("colors") or {})}
    custom_categories = settings.get("custom_categories") or []
    return {"colors": colors, "custom_categories": custom_categories}


# ---------------------------------------------------------------------------
# PATCH /calendar/my-settings
# ---------------------------------------------------------------------------

class MySettingsBody(BaseModel):
    colors: Optional[dict] = None
    custom_categories: Optional[list] = None


@router.patch("/my-settings")
def patch_my_settings(
    body: MySettingsBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = dict(current_user.calendar_settings or {})
    if body.colors is not None:
        existing["colors"] = {**(existing.get("colors") or {}), **body.colors}
    if body.custom_categories is not None:
        existing["custom_categories"] = body.custom_categories
    current_user.calendar_settings = existing
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    settings = current_user.calendar_settings or {}
    colors = {**DEFAULT_EVENT_COLORS, **(settings.get("colors") or {})}
    return {"colors": colors, "custom_categories": settings.get("custom_categories") or []}


# ---------------------------------------------------------------------------
# GET /calendar/external-events
# ---------------------------------------------------------------------------

@router.get("/external-events")
def get_external_events(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    window_end = today + timedelta(days=180)

    gmail_integration = _get_user_integration(db, current_firm.id, current_user.id, "gmail")
    outlook_integration = _get_user_integration(db, current_firm.id, current_user.id, "outlook")

    if gmail_integration:
        scopes = gmail_integration.scopes or ""
        if "calendar.readonly" not in scopes:
            return {"events": [], "provider": None, "needs_reconnect": True}
        try:
            from app.services.gmail_signals_service import get_fresh_credentials
            creds = get_fresh_credentials(gmail_integration)
            headers = {"Authorization": f"Bearer {creds.token}"}
            params = {
                "timeMin": datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat(),
                "timeMax": datetime.combine(window_end, datetime.min.time()).replace(tzinfo=timezone.utc).isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 100,
            }
            resp = http_requests.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            raw_events = resp.json().get("items", [])
            events = []
            for ev in raw_events:
                start_obj = ev.get("start", {})
                end_obj = ev.get("end", {})
                events.append({
                    "id": ev.get("id", ""),
                    "title": ev.get("summary", ""),
                    "start": start_obj.get("dateTime") or start_obj.get("date", ""),
                    "end": end_obj.get("dateTime") or end_obj.get("date", ""),
                    "description": ev.get("description", ""),
                    "location": ev.get("location", ""),
                    "type": "call",
                })
            result = {"events": events, "provider": "gmail"}
            threading.Thread(
                target=log_event,
                kwargs={
                    "event_type": "calendar.external_events_synced",
                    "firm_id": current_firm.id,
                    "actor_type": "staff",
                    "actor_id": current_user.id,
                    "metadata": {
                        "provider": result["provider"],
                        "event_count": len(result["events"]),
                        "has_join_links": sum(
                            1 for ev in result["events"] if any(
                                p in (ev.get("description", "") + " " + ev.get("location", ""))
                                for p in ["zoom.us", "meet.google.com", "teams.microsoft.com"]
                            )
                        ),
                    },
                },
                daemon=True,
            ).start()
            return result
        except Exception:
            return {"events": [], "provider": "gmail"}

    if outlook_integration:
        scopes = outlook_integration.scopes or ""
        if "Calendars.Read" not in scopes:
            return {"events": [], "provider": None, "needs_reconnect": True}
        try:
            from app.services.outlook_signals_service import get_fresh_outlook_credentials
            access_token = get_fresh_outlook_credentials(outlook_integration)
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {
                "startDateTime": today.isoformat(),
                "endDateTime": window_end.isoformat(),
                "$select": "id,subject,start,end,bodyPreview,location",
                "$top": 100,
            }
            resp = http_requests.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                headers=headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            raw_events = resp.json().get("value", [])
            events = []
            for ev in raw_events:
                start_obj = ev.get("start", {})
                end_obj = ev.get("end", {})
                events.append({
                    "id": ev.get("id", ""),
                    "title": ev.get("subject", ""),
                    "start": start_obj.get("dateTime", ""),
                    "end": end_obj.get("dateTime", ""),
                    "description": ev.get("bodyPreview", ""),
                    "location": ev.get("location", {}).get("displayName", ""),
                    "type": "call",
                })
            result = {"events": events, "provider": "outlook"}
            threading.Thread(
                target=log_event,
                kwargs={
                    "event_type": "calendar.external_events_synced",
                    "firm_id": current_firm.id,
                    "actor_type": "staff",
                    "actor_id": current_user.id,
                    "metadata": {
                        "provider": result["provider"],
                        "event_count": len(result["events"]),
                        "has_join_links": sum(
                            1 for ev in result["events"] if any(
                                p in (ev.get("description", "") + " " + ev.get("location", ""))
                                for p in ["zoom.us", "meet.google.com", "teams.microsoft.com"]
                            )
                        ),
                    },
                },
                daemon=True,
            ).start()
            return result
        except Exception:
            return {"events": [], "provider": "outlook"}

    return {"events": [], "provider": None}
