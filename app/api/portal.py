# app/api/portal.py

"""
Client Portal API.

Three endpoint groups:
  - /portal/auth/*       — unauthenticated (login, invite accept)
  - /portal/admin/*      — staff JWT required (invite generation, access revocation)
  - /portal/*            — portal JWT required (dashboard, engagements, notifications)
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter, check_email_rate_limit
from app.crud import portal_notification as crud_notification
from app.crud import portal_session as crud_portal_session
from app.crud import tax_organizer as crud_organizer
from app.schemas.tax_organizer import TaxOrganizerWithTemplate, PortalOrganizerSaveRequest
from app.crud.document import write_audit_log
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.portal import get_current_portal_client
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.portal_session import PortalSession
from app.models.signature_envelope import SignatureEnvelope
from app.models.user import User
from app.schemas.portal_auth import (
    PortalDashboardOut,
    PortalInviteAcceptRequest,
    PortalInviteRequest,
    PortalLoginRequest,
    PortalRequestMagicLinkRequest,
    PortalSetPasswordRequest,
    PortalTokenResponse,
)
from app.schemas.portal_notification import PortalNotificationCreate, PortalNotificationOut
from app.schemas.portal_session import PortalSessionCreate
from app.services.portal_auth import (
    authenticate_portal_client,
    create_portal_access_token,
    decode_portal_access_token,
    generate_invite_token,
    generate_refresh_token,
    hash_portal_password,
    hash_portal_password_bcrypt,
    hash_refresh_token,
    login_portal_with_password,
    verify_portal_password,
)
from app.core.config import get_settings
from app.schemas.portal import MagicLinkRequest, MagicLinkResponse, ClientMagicLinkRequest
from app.services import portal_magic_link
from app.services.behavioral_log import log_event

settings = get_settings()

router = APIRouter(prefix="/portal", tags=["portal"])

_bearer = HTTPBearer()


# ===========================================================================
# AUTH ENDPOINTS — no authentication required
# ===========================================================================

@router.post("/auth/login", response_model=PortalTokenResponse)
@limiter.limit("5/minute")
def portal_login(
    body: PortalLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Authenticate a client with email + password and issue a portal access token.
    If firm_slug is provided the client is scoped to that firm; otherwise looked up globally.
    """
    firm_id: Optional[UUID] = None
    if body.firm_slug:
        firm = db.execute(
            select(Firm).where(Firm.slug == body.firm_slug)
        ).scalar_one_or_none()
        if firm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Firm not found")
        firm_id = firm.id

    client, err = login_portal_with_password(db, body.email, body.password, firm_id)

    if err == "no_password":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No password set. Use a magic link to log in, then set a password in your account settings.",
        )
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    resolved_firm_id = client.firm_id

    # Issue access token
    jti = str(uuid.uuid4())
    access_token = create_portal_access_token(client.id, resolved_firm_id, jti)

    # Generate refresh token (store hash only — never plaintext)
    refresh_token = generate_refresh_token()
    refresh_token_hash = hash_refresh_token(refresh_token)

    # Persist session
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.PORTAL_SESSION_HARD_EXPIRE_DAYS)

    crud_portal_session.create_session(
        db,
        PortalSessionCreate(
            firm_id=resolved_firm_id,
            client_id=client.id,
            refresh_token_hash=refresh_token_hash,
            access_jti=jti,
            ip_address=ip,
            user_agent=user_agent,
            expires_at=expires_at,
        ),
    )

    client.portal_last_login_at = datetime.now(timezone.utc)
    db.commit()

    write_audit_log(
        db,
        firm_id=resolved_firm_id,
        action="portal_login",
        ip_address=ip,
    )

    return PortalTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/auth/request-magic-link")
@limiter.limit("3/15minutes")
def portal_request_magic_link(
    body: PortalRequestMagicLinkRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Client self-service: request a magic link by email.
    Always returns the same response to prevent user enumeration.
    Rate limited: 3/15min per IP and 3/15min per email.
    """
    email_allowed = check_email_rate_limit(body.email, max_requests=3, window_seconds=900)
    if not email_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a few minutes.",
        )

    client = db.execute(
        select(Client).where(
            Client.email == body.email,
            Client.portal_access_enabled.is_(True),
        )
    ).scalar_one_or_none()

    if client is not None:
        try:
            portal_magic_link.generate_magic_link(
                client_id=client.id,
                firm_id=client.firm_id,
                expiry_hours=24,
                db=db,
            )
        except Exception:
            pass

    return {"message": "If that email is registered, a link is on its way."}


@router.post("/auth/invite/accept")
def portal_invite_accept(
    body: PortalInviteAcceptRequest,
    db: Session = Depends(get_db),
):
    """
    Accept a portal invite and set a password to activate portal access.
    Invite tokens expire after 72 hours.
    """
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=settings.PORTAL_INVITE_TOKEN_EXPIRE_HOURS
    )
    stmt = select(Client).where(
        Client.portal_invite_token == body.token,
        Client.portal_invite_sent_at > cutoff,
    )
    client = db.execute(stmt).scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    client.portal_password_hash = hash_portal_password(body.new_password)
    client.portal_invite_token = None
    client.portal_access_enabled = True
    db.commit()

    return {"message": "Portal access activated"}


@router.post("/auth/logout")
def portal_logout(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Revoke the current portal session."""
    # Decode token to get the jti — already validated by the dependency
    payload = decode_portal_access_token(credentials.credentials)
    jti = payload.get("jti")
    firm_id = UUID(payload.get("firm_id"))

    session = crud_portal_session.get_session_by_jti(db, jti, firm_id)
    if session and not session.is_revoked:
        crud_portal_session.revoke_session(db, session, revoked_by="client")

    return {"message": "Logged out"}


# ===========================================================================
# STAFF ADMIN ENDPOINTS — requires staff JWT
# ===========================================================================

@router.post("/admin/invite")
def portal_admin_invite(
    body: PortalInviteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Generate a portal invite token for a client.
    If send_email=True, the email service will be called (Phase 9).
    Returns the token so staff can share the link during development.
    """
    client = db.execute(
        select(Client).where(
            Client.id == body.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    token = generate_invite_token()
    client.portal_invite_token = token
    client.portal_invite_sent_at = datetime.now(timezone.utc)
    db.commit()

    expires_at = client.portal_invite_sent_at + timedelta(hours=settings.PORTAL_INVITE_TOKEN_EXPIRE_HOURS)

    if body.send_email:
        # TODO: Call email service here when Phase 9 is built
        pass

    return {"invite_token": token, "expires_at": expires_at}


@router.post("/admin/revoke/{client_id}")
def portal_admin_revoke(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """Revoke all active portal sessions and disable portal access for a client."""
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    count = crud_portal_session.revoke_all_client_sessions(db, client_id, current_firm.id)
    client.portal_access_enabled = False
    db.commit()

    return {"message": "Portal access revoked", "sessions_revoked": count}


# ===========================================================================
# MAGIC LINK ENDPOINTS
# ===========================================================================

@router.post("/magic-link", response_model=MagicLinkResponse, status_code=status.HTTP_201_CREATED)
def send_portal_magic_link(
    body: MagicLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Generate and email a magic link for passwordless client portal access.
    Auth: firm_owner or manager only.
    """
    result, _ = portal_magic_link.generate_magic_link(
        client_id=body.client_id,
        firm_id=current_firm.id,
        expiry_hours=body.expiry_hours,
        db=db,
    )
    return result


@router.get("/admin/portal-access/{client_id}")
def staff_portal_access(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Generate a magic link token for a client and return the raw
    portal URL directly to the staff member — no email sent.
    Staff use this to preview exactly what the client sees.
    Auth: firm_owner, manager, staff.
    """
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if not client.portal_access_enabled:
        client.portal_access_enabled = True
        db.commit()

    _, raw_token = portal_magic_link.generate_magic_link(
        client_id=client_id,
        firm_id=current_firm.id,
        expiry_hours=2,
        db=db,
    )
    return {"portal_url": f"{settings.FRONTEND_URL}/portal/auth?token={raw_token}"}


@router.post("/request-magic-link")
def portal_client_request_magic_link(
    body: ClientMagicLinkRequest,
    db: Session = Depends(get_db),
):
    """
    Client self-service: request a magic link by email.
    Always returns 200 — never reveals whether the email exists or is rate limited.
    Rate limited: max 3 requests per 15 minutes per email address.
    """
    _MSG = "If a portal account exists for that email, a login link has been sent."

    if not check_email_rate_limit(body.email, max_requests=3, window_seconds=900):
        return {"message": _MSG}

    client = db.execute(
        select(Client).where(Client.email == body.email)
    ).scalar_one_or_none()

    if client is not None:
        try:
            portal_magic_link.generate_magic_link(
                client_id=client.id,
                firm_id=client.firm_id,
                expiry_hours=48,
                db=db,
            )
        except Exception:
            pass

    return {"message": _MSG}


@router.get("/auth")
def portal_auth_exchange(
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Exchange a magic link token for a portal JWT.
    Public endpoint — no authentication required.
    """
    jwt_string = portal_magic_link.exchange_magic_link(token=token, db=db)
    return {"access_token": jwt_string, "token_type": "bearer"}


# ===========================================================================
# PORTAL CLIENT ENDPOINTS — requires portal JWT
# ===========================================================================

@router.post("/account/set-password")
def portal_set_password(
    body: PortalSetPasswordRequest,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Client sets or changes their portal password.
    If a password is already set, current_password is required and verified.
    Uses bcrypt for new password hashes.
    """
    import bcrypt as _bcrypt

    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters.",
        )
    if body.new_password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Passwords don't match.",
        )

    if current_client.portal_password_hash:
        if not body.current_password:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Current password is required to change your password.",
            )
        if not verify_portal_password(body.current_password, current_client.portal_password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password is incorrect.",
            )

    current_client.portal_password_hash = hash_portal_password_bcrypt(body.new_password)
    db.commit()
    return {"success": True}


@router.get("/dashboard", response_model=PortalDashboardOut)
def portal_dashboard(
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Portal dashboard — summarises the client's current state.

    Never exposes: internal notes, full staff assignment details,
    firm financial data, or any other client's data.
    """
    firm_id = current_client.firm_id
    client_id = current_client.id

    # Active engagements (not archived)
    engagements = db.execute(
        select(Engagement).where(
            Engagement.client_id == client_id,
            Engagement.firm_id == firm_id,
            Engagement.status != "archived",
        )
    ).scalars().all()

    active_engagements = [
        {
            "id": str(e.id),
            "name": e.name,
            "status": e.status,
        }
        for e in engagements
    ]

    # Pending signatures
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

    # TODO: populate when Phase 4 DocumentRequest model is built
    pending_document_requests: list[dict] = []

    # Notifications
    unread_count = crud_notification.get_unread_count(db, client_id, firm_id)
    recent = crud_notification.get_notifications_for_client(db, client_id, firm_id, skip=0, limit=5)

    return PortalDashboardOut(
        active_engagements=active_engagements,
        pending_document_requests=pending_document_requests,
        pending_signatures=pending_signatures,
        unread_notification_count=unread_count,
        recent_notifications=[PortalNotificationOut.model_validate(n) for n in recent],
    )


@router.get("/me")
def portal_me(
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Return identity info for the authenticated portal client."""
    firm = db.execute(select(Firm).where(Firm.id == current_client.firm_id)).scalar_one_or_none()
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
        "text_primary": "#1F3148",
        "text_muted": "#6B7280",
    }

    if portal_mode == "light":
        defaults = light_defaults
        colors = {**light_defaults, **(settings.get("portal_colors_light") or {})}
    else:
        defaults = dark_defaults
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


@router.get("/engagements")
def portal_list_engagements(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Return paginated list of the client's non-archived engagements."""
    stmt = (
        select(Engagement)
        .where(
            Engagement.client_id == current_client.id,
            Engagement.firm_id == current_client.firm_id,
            Engagement.status != "archived",
        )
        .offset(skip)
        .limit(limit)
    )
    engagements = db.execute(stmt).scalars().all()
    return [
        {
            "id": str(e.id),
            "name": e.name,
            "status": e.status,
        }
        for e in engagements
    ]


@router.get("/engagements/{engagement_id}")
def portal_get_engagement(
    engagement_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Return a single engagement.

    Exposes only client-safe fields. Never includes:
    notes_internal, staff financial data, or other clients' data.
    """
    stmt = select(Engagement).where(
        Engagement.id == engagement_id,
        Engagement.client_id == current_client.id,
        Engagement.firm_id == current_client.firm_id,
    )
    engagement = db.execute(stmt).scalar_one_or_none()
    if engagement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")

    return {
        "id": str(engagement.id),
        "name": engagement.name,
        "status": engagement.status,
        "notes_client_visible": engagement.notes_client_visible,
        # notes (internal staff notes) is intentionally excluded
    }


@router.get("/documents")
def portal_list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Return client-visible documents for the authenticated portal client."""
    from app.models.document import Document
    docs = db.execute(
        select(Document)
        .where(
            Document.firm_id == current_client.firm_id,
            Document.client_id == current_client.id,
            Document.visibility == "client_visible",
        )
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).scalars().all()
    return [
        {
            "id": str(d.id),
            "name": d.filename,
            "uploaded_at": d.created_at.isoformat(),
            "file_type": d.content_type.split("/")[-1].upper() if d.content_type else "FILE",
            "file_size_kb": max(1, d.size_bytes // 1024),
            "uploaded_by": "firm",
        }
        for d in docs
    ]


@router.get("/notifications", response_model=list[PortalNotificationOut])
def portal_list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Return paginated notifications for the current client."""
    return crud_notification.get_notifications_for_client(
        db,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
        skip=skip,
        limit=limit,
        unread_only=unread_only,
    )


@router.patch("/notifications/{notification_id}/read", response_model=PortalNotificationOut)
def portal_mark_notification_read(
    notification_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Mark a single notification as read."""
    notification = crud_notification.mark_as_read(
        db,
        notification_id=notification_id,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return notification


@router.post("/notifications/read-all")
def portal_mark_all_notifications_read(
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for the current client."""
    count = crud_notification.mark_all_as_read(
        db,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    return {"marked_read": count}


# ===========================================================================
# PORTAL BILLING ENDPOINTS — requires portal JWT
# ===========================================================================

import io

from starlette.responses import StreamingResponse

from app.crud.invoice import (
    get_portal_invoices,
    get_portal_invoices_count,
    get_portal_invoice,
    set_payment_intent,
)
from app.crud.stripe_connection import get_connection_by_firm
from app.services import stripe_service
from app.services.invoice_renderer import render_invoice_to_pdf
from app.schemas.invoice import PortalInvoiceOut
from app.schemas.pagination import PaginatedResponse
from app.core.enums import InvoiceStatus


@router.get("/invoices", response_model=PaginatedResponse[PortalInvoiceOut])
def portal_list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    items = get_portal_invoices(
        db,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
        skip=skip,
        limit=limit,
    )
    total = get_portal_invoices_count(
        db,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


@router.get("/invoices/{invoice_id}", response_model=PortalInvoiceOut)
def portal_get_invoice(
    invoice_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    invoice = get_portal_invoice(
        db,
        invoice_id=invoice_id,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    log_event(
        firm_id=current_client.firm_id,
        event_type="portal.invoice_viewed",
        entity_type="invoice",
        entity_id=invoice_id,
        actor_type="client",
        actor_id=None,
        metadata={
            "invoice_amount": float(invoice.total_amount) if hasattr(invoice, 'total_amount') else None,
            "invoice_status": str(invoice.status) if hasattr(invoice, 'status') else None,
            "days_since_sent": (
                (datetime.now(timezone.utc) - invoice.sent_at).days
                if hasattr(invoice, 'sent_at') and invoice.sent_at
                else None
            ),
        }
    )
    return invoice


@router.get("/invoices/{invoice_id}/pdf")
def portal_get_invoice_pdf(
    invoice_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    invoice = get_portal_invoice(
        db,
        invoice_id=invoice_id,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    firm = db.execute(select(Firm).where(Firm.id == current_client.firm_id)).scalar_one_or_none()
    client = db.execute(select(Client).where(Client.id == current_client.id)).scalar_one_or_none()

    pdf_bytes = render_invoice_to_pdf(invoice, firm, client)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=invoice-{invoice.invoice_number}.pdf"
        },
    )


# ===========================================================================
# STAFF PREVIEW ENDPOINT — requires staff JWT (firm_owner, manager, or staff)
# ===========================================================================

from app.schemas.portal_preview import PortalPreviewOut
from app.services import portal_preview_service


@router.get("/preview/{client_id}", response_model=PortalPreviewOut)
def portal_preview(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Return a read-only snapshot of exactly what a client would see in their
    portal: document requests, documents, invoices, and unread message count.

    Auth: firm_owner, manager, staff only — not client_portal_user.
    This endpoint is staff-facing. The client never knows it exists.
    """
    return portal_preview_service.get_portal_preview(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
    )


# ===========================================================================
# PORTAL MESSAGING ENDPOINTS — requires portal JWT
# ===========================================================================

from app.schemas.message import ClientMessageCreate, ClientMessageOut, UnreadCountOut
from app.services import message_service as msg_service
from app.crud import message as crud_message



@router.get("/clients/{client_id}/messages", response_model=list[ClientMessageOut])
def portal_get_messages(
    client_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Return message thread for the client.
    Marks messages as read from the client's perspective.
    Auth: client_portal_user only.
    Tenant isolation: client_id must belong to the same firm as the portal user.
    """
    if client_id != current_client.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    raw_messages = crud_message.get_messages_for_client(
        db, firm_id=current_client.firm_id, client_id=client_id
    )

    result = []
    for msg in raw_messages:
        msg_out = ClientMessageOut.model_validate(msg)
        if msg.sender_role == "staff" and msg.sender_id is not None:
            sender = db.execute(
                select(User).where(User.id == msg.sender_id)
            ).scalar_one_or_none()
            if sender and sender.full_name:
                msg_out.sender_name = sender.full_name
        elif msg.sender_role == "client":
            msg_out.sender_name = current_client.name
        result.append(msg_out)

    # Mark messages as read by the client (reader_id=None, reader_role="client")
    crud_message.mark_messages_read(
        db,
        firm_id=current_client.firm_id,
        client_id=client_id,
        reader_id=None,
        reader_role="client",
    )

    return result


@router.post(
    "/clients/{client_id}/messages",
    response_model=ClientMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def portal_send_message(
    client_id: UUID,
    data: ClientMessageCreate,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Send a message from the client portal.
    Auth: client_portal_user only.
    """
    if client_id != current_client.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    result = msg_service.send_message_client(
        db,
        firm_id=current_client.firm_id,
        client_id=client_id,
        data=data,
    )
    log_event(
        firm_id=current_client.firm_id,
        event_type="portal.message_sent",
        entity_type="client",
        entity_id=current_client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "time_of_day": datetime.now(timezone.utc).hour,
            "day_of_week": datetime.now(timezone.utc).weekday(),
        }
    )
    return result


@router.get("/clients/{client_id}/messages/unread-count", response_model=UnreadCountOut)
def portal_get_unread_count(
    client_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    """
    Return unread message count for the client.
    Auth: client_portal_user only.
    """
    if client_id != current_client.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return msg_service.get_portal_unread_count(
        db,
        firm_id=current_client.firm_id,
        client_id=client_id,
    )


@router.post("/invoices/{invoice_id}/pay")
def portal_pay_invoice(
    invoice_id: UUID,
    current_client: Client = Depends(get_current_portal_client),
    db: Session = Depends(get_db),
):
    invoice = get_portal_invoice(
        db,
        invoice_id=invoice_id,
        client_id=current_client.id,
        firm_id=current_client.firm_id,
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    if invoice.status != InvoiceStatus.sent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invoice is not available for payment",
        )

    if invoice.stripe_payment_intent_id is not None:
        connection = get_connection_by_firm(db, current_client.firm_id)
        if not connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment not available for this invoice",
            )
        return stripe_service.retrieve_payment_intent(
            invoice.stripe_payment_intent_id,
            connection.stripe_account_id,
        )

    connection = get_connection_by_firm(db, current_client.firm_id)
    if not connection or not connection.charges_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment not available for this invoice",
        )

    amount_cents = int(invoice.total_amount * 100)
    idempotency_key = f"portal-invoice-{invoice_id}-payment-intent"

    result = stripe_service.create_payment_intent(
        amount_cents=amount_cents,
        currency=connection.default_currency or "usd",
        stripe_account_id=connection.stripe_account_id,
        invoice_id=str(invoice_id),
        idempotency_key=idempotency_key,
    )
    set_payment_intent(db, invoice, result["payment_intent_id"])
    log_event(
        firm_id=current_client.firm_id,
        event_type="portal.invoice_paid",
        entity_type="invoice",
        entity_id=invoice_id,
        actor_type="client",
        actor_id=None,
        metadata={
            "payment_method": "stripe",
            "time_of_day": datetime.now(timezone.utc).hour,
        }
    )
    return result


# ===========================================================================
# TAX ORGANIZER PORTAL ENDPOINTS
# ===========================================================================

@router.get("/organizers", response_model=list)
def portal_list_organizers(
    db: Session = Depends(get_db),
    portal_client: Client = Depends(get_current_portal_client),
):
    """
    List all tax organizers for the authenticated portal client.
    Returns organizers in all statuses (sent, in_progress, submitted).
    """
    organizers = crud_organizer.list_organizers_for_client(
        db=db,
        client_id=portal_client.id,
        firm_id=portal_client.firm_id,
    )
    return [
        {
            "id": str(o.id),
            "tax_year": o.tax_year,
            "status": o.status,
            "engagement_id": str(o.engagement_id),
            "template_id": str(o.template_id),
            "submitted_at": o.submitted_at.isoformat() if o.submitted_at else None,
            "client_message": o.client_message,
            "created_at": o.created_at.isoformat(),
        }
        for o in organizers
    ]


@router.get("/organizers/{organizer_id}")
def portal_get_organizer(
    organizer_id: UUID,
    db: Session = Depends(get_db),
    portal_client: Client = Depends(get_current_portal_client),
):
    """
    Get a tax organizer with its template sections for rendering.
    Client only sees their own organizers — double-scoped by client_id + firm_id.
    """
    organizer = crud_organizer.get_organizer_for_client(
        db=db,
        organizer_id=organizer_id,
        client_id=portal_client.id,
        firm_id=portal_client.firm_id,
    )
    if not organizer:
        raise HTTPException(status_code=404, detail="Organizer not found")

    template = organizer.template
    return {
        "id": str(organizer.id),
        "tax_year": organizer.tax_year,
        "status": organizer.status,
        "responses": organizer.responses,
        "submitted_at": organizer.submitted_at.isoformat() if organizer.submitted_at else None,
        "client_message": organizer.client_message,
        "template": {
            "id": str(template.id),
            "name": template.name,
            "organizer_type": template.organizer_type,
            "sections": template.sections,
        },
    }


@router.post("/organizers/{organizer_id}/save")
def portal_save_organizer(
    organizer_id: UUID,
    payload: PortalOrganizerSaveRequest,
    db: Session = Depends(get_db),
    portal_client: Client = Depends(get_current_portal_client),
):
    """
    Save client responses to their tax organizer.

    Supports partial saves — client can save progress and return later.
    New responses are merged into existing ones, not replaced.
    Set submit=true to mark the organizer as submitted.
    Once submitted, the organizer becomes read-only.
    """
    organizer = crud_organizer.get_organizer_for_client(
        db=db,
        organizer_id=organizer_id,
        client_id=portal_client.id,
        firm_id=portal_client.firm_id,
    )
    if not organizer:
        raise HTTPException(status_code=404, detail="Organizer not found")

    if organizer.status == "submitted":
        raise HTTPException(
            status_code=400,
            detail="This organizer has already been submitted and cannot be modified.",
        )

    updated = crud_organizer.save_organizer_responses(
        db=db,
        organizer=organizer,
        responses=payload.responses,
        submit=payload.submit,
    )

    if payload.submit and updated.status == "submitted":
        log_event(
            firm_id=portal_client.firm_id,
            event_type="portal.organizer_submitted",
            entity_type="tax_organizer",
            entity_id=updated.id,
            actor_type="client",
            actor_id=portal_client.id,
            metadata={
                "tax_year": updated.tax_year,
                "engagement_id": str(updated.engagement_id) if updated.engagement_id else None,
            }
        )

    return {
        "id": str(updated.id),
        "status": updated.status,
        "submitted_at": updated.submitted_at.isoformat() if updated.submitted_at else None,
        "message": "Submitted successfully" if payload.submit else "Progress saved",
    }
