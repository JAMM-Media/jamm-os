# app/api/portal_preview.py

"""
Read-only portal preview router for staff-initiated branding previews.

All endpoints here accept scope="portal_staff_preview" tokens (issued by
POST /portal-preview/token) via the get_current_preview_client dependency.
This scope is DISTINCT from scope="client_portal" used by real client sessions,
so preview tokens are automatically rejected by all regular portal write endpoints.

The preview router provides enough data to render the portal shell + To-do tab:
  POST /portal-preview/token   -- generate a 10-minute preview token (staff auth)
  GET  /portal-preview/me      -- branding and identity data
  GET  /portal-preview/dashboard -- To-do items and document requests

No write endpoints are included. A preview token cannot send messages, pay invoices,
upload documents, or take any action on behalf of the client.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import document_request as crud_dr
from app.crud import portal_notification as crud_notification
from app.db.session import get_db
from app.dependencies.portal_preview import get_current_preview_client
from app.dependencies.roles import require_firm_owner
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.signature_envelope import SignatureEnvelope
from app.models.user import User
from app.services.portal_auth import create_preview_access_token

router = APIRouter(prefix="/portal-preview", tags=["portal_preview"])


# ---------------------------------------------------------------------------
# Token generation (staff-authenticated)
# ---------------------------------------------------------------------------

@router.post("/token")
def create_portal_preview_token(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    """
    Generate a short-lived preview token for the staff member's own firm.

    Selects the most recently created portal-enabled client for this firm.
    Returns a 10-minute JWT with scope="portal_staff_preview" that can be used
    on GET /portal-preview/... endpoints but is rejected by all write endpoints.

    Auth: firm_owner only (branding preview is a firm-owner workflow).
    """
    client = db.execute(
        select(Client)
        .where(
            Client.firm_id == current_user.firm_id,
            Client.portal_access_enabled.is_(True),
        )
        .order_by(Client.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No portal-enabled clients found for this firm. "
                "Invite and enable portal access for at least one client before previewing."
            ),
        )

    token = create_preview_access_token(client.id, current_user.firm_id)

    return {
        "preview_token": token,
        "client_id": str(client.id),
        "client_name": client.name,
        "expires_in": 600,
    }


# ---------------------------------------------------------------------------
# Read-only portal data (preview-authenticated)
# ---------------------------------------------------------------------------

@router.get("/me")
def preview_me(
    current_client: Client = Depends(get_current_preview_client),
    db: Session = Depends(get_db),
):
    """Return branding and identity data for the previewed client's firm."""
    firm = db.execute(
        select(Firm).where(Firm.id == current_client.firm_id)
    ).scalar_one_or_none()
    settings = firm.settings or {} if firm else {}
    firm_id_str = str(current_client.firm_id)
    has_logo = bool(settings.get("portal_logo_s3_key"))
    portal_mode = settings.get("portal_mode", "dark")

    dark_defaults = {
        "top_bar": "#1A2535",
        "page": "#2D2D2D",
        "tab_bar": "#252525",
        "accent": "#4A7FA5",
        "avatar": "#3A6A94",
        "subtitle": "#7DA3C4",
        "card": "#383838",
        "text_primary": "#EDEEF0",
        "text_muted": "#9CA3AF",
    }
    light_defaults = {
        "top_bar": "#1F3148",
        "page": "#E4E6EA",
        "tab_bar": "#EDEEF0",
        "accent": "#1F3148",
        "avatar": "#1F3148",
        "subtitle": "#7DA3C4",
        "card": "#EDEEF0",
        "text_primary": "#111111",
        "text_muted": "#6B7280",
    }

    if portal_mode == "light":
        colors = {**light_defaults, **(settings.get("portal_colors_light") or {})}
    else:
        colors = {**dark_defaults, **(settings.get("portal_colors_dark") or {})}

    return {
        "client_id": str(current_client.id),
        "client_name": current_client.name,
        "firm_name": firm.name if firm else "",
        "portal_display_name": settings.get("portal_display_name") or (firm.name if firm else ""),
        "portal_logo_url": f"/firms/logo/{firm_id_str}" if has_logo else None,
        "portal_mode": portal_mode,
        "portal_top_bar_color": colors["top_bar"],
        "portal_page_color": colors["page"],
        "portal_tab_bar_color": colors["tab_bar"],
        "portal_accent_color": colors["accent"],
        "portal_avatar_color": colors["avatar"],
        "portal_subtitle_color": colors["subtitle"],
        "portal_card_color": colors["card"],
        "portal_text_primary": colors["text_primary"],
        "portal_text_muted": colors["text_muted"],
    }


@router.get("/dashboard")
def preview_dashboard(
    current_client: Client = Depends(get_current_preview_client),
    db: Session = Depends(get_db),
):
    """Return To-do dashboard data for the previewed client (read-only)."""
    client_id = current_client.id
    firm_id = current_client.firm_id

    open_requests = crud_dr.get_pending_for_client(db, client_id=client_id, firm_id=firm_id)
    completed_requests = crud_dr.get_recently_completed_for_client(
        db, client_id=client_id, firm_id=firm_id
    )
    pending_document_requests = [
        {
            "id": str(dr.id),
            "title": dr.title,
            "due_date": dr.due_date.isoformat() if dr.due_date else None,
            "status": dr.status,
        }
        for dr in [*open_requests, *completed_requests]
    ]

    envelopes = db.execute(
        select(SignatureEnvelope).where(
            SignatureEnvelope.client_id == client_id,
            SignatureEnvelope.firm_id == firm_id,
            SignatureEnvelope.status.in_(["sent", "viewed"]),
        )
    ).scalars().all()

    pending_signatures = [
        {
            "id": str(env.id),
            "engagement_id": str(env.engagement_id) if env.engagement_id else None,
            "status": env.status,
            "sent_at": env.sent_at.isoformat() if env.sent_at else None,
        }
        for env in envelopes
    ]

    unread_count = crud_notification.get_unread_count(db, client_id, firm_id)

    return {
        "active_engagements": [],
        "pending_document_requests": pending_document_requests,
        "pending_signatures": pending_signatures,
        "unread_notification_count": unread_count,
        "recent_notifications": [],
    }
