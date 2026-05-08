## STANDING RULES
- Never use native_enum=True for enums with dots or special characters
- Background tasks must create their own SessionLocal() session in try/finally
- Routers are thin — no business logic
- Every file starts with a path comment
- Do not run migrations unless explicitly told to

## TASK A: Fix EmailService._send_raw missing method

File: app/services/email_service.py

Add this static method to the EmailService class, directly after the 
existing _send() method:

    @staticmethod
    def _send_raw(to_email: str, subject: str, html_body: str, from_name: str) -> None:
        """Direct HTML send — used by magic link and portal invite flows."""
        EmailService._send(to_email, subject, html_body, from_name)

No other changes to this file.

---

## TASK B: Fix "View Client Portal" button — redirect staff directly into portal

Currently the View Client Portal button on the client detail page opens 
a blank page. It should generate a magic link for the client and open 
the portal directly in a new tab, bypassing the email flow entirely.

This is a staff-only shortcut. The client never sees this happen.

### Backend change

File: app/api/portal.py

Add a new endpoint after the existing /portal/magic-link endpoint:

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
        from app.services import portal_magic_link
        from sqlalchemy import select

        client = db.execute(
            select(Client).where(
                Client.id == client_id,
                Client.firm_id == current_firm.id,
            )
        ).scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        # Enable portal access temporarily if not already enabled
        # so the magic link exchange works
        if not client.portal_access_enabled:
            client.portal_access_enabled = True
            db.commit()

        result = portal_magic_link.generate_magic_link(
            client_id=client_id,
            firm_id=current_firm.id,
            expiry_hours=2,
            db=db,
        )

        from app.core.config import get_settings
        settings = get_settings()
        portal_url = f"{settings.FRONTEND_URL}/portal/auth?token="

        # We need the raw token — generate it directly instead of 
        # going through generate_magic_link which doesn't return it.
        # Re-implement inline:
        import hashlib, secrets
        from datetime import datetime, timedelta, timezone
        from app.models.portal_session import PortalSession

        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=2)

        session = db.execute(
            select(PortalSession).where(
                PortalSession.client_id == client_id,
                PortalSession.firm_id == current_firm.id,
                PortalSession.is_revoked.is_(False),
            )
        ).scalar_one_or_none()

        import uuid as _uuid
        if session is None:
            import hashlib as _hl, secrets as _sec
            session = PortalSession(
                firm_id=current_firm.id,
                client_id=client_id,
                refresh_token_hash=_hl.sha256(_sec.token_hex(32).encode()).hexdigest(),
                access_jti=str(_uuid.uuid4()),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(session)
            db.flush()

        session.magic_link_token_hash = token_hash
        session.magic_link_expires_at = expires_at
        db.commit()

        return {
            "portal_url": f"{settings.FRONTEND_URL}/portal/auth?token={raw_token}"
        }

Wait — that approach duplicates logic from generate_magic_link. 
Do it cleanly instead:

Modify app/services/portal_magic_link.py:

Change generate_magic_link() to also return the raw_token in its 
response alongside the MagicLinkResponse. Specifically:

1. Change the return type to a tuple: return both the MagicLinkResponse 
   and the raw_token string
2. Return: return MagicLinkResponse(sent=True, expires_at=expires_at), raw_token

Then in the existing /portal/magic-link endpoint (POST), update the 
call to unpack the tuple and only use the MagicLinkResponse:
    result, _ = portal_magic_link.generate_magic_link(...)
    return result

Then the new /admin/portal-access/{client_id} endpoint unpacks both:
    result, raw_token = portal_magic_link.generate_magic_link(...)
    return {"portal_url": f"{settings.FRONTEND_URL}/portal/auth?token={raw_token}"}

### Frontend change

File: frontend/src/app/clients/[id]/page.tsx (or wherever the 
View Client Portal button lives — find it first)

Change the View Client Portal button's onClick handler to:
1. Call GET /api/backend/portal/admin/portal-access/{clientId} 
   with the staff JWT (use the existing api axios instance)
2. On success, open the returned portal_url in a new tab: 
   window.open(data.portal_url, '_blank')
3. Show a loading state on the button while the request is in flight
4. Show a toast error if the request fails

The button should say "View Client Portal" and open the portal 
in a new tab — not navigate the current tab away from the client page.

---

## VERIFICATION

After both changes:
1. Run: npx tsc --noEmit in the frontend directory
2. Confirm no TypeScript errors
3. Report every file modified