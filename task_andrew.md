# STANDING RULES — PERMANENT, NEVER OVERWRITE THIS BLOCK
- All models use UUID primary keys, firm_id FK, created_at and updated_at (timezone-aware)
- Every module has 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut
- Routers are thin — no business logic ever
- All list endpoints paginated using PaginatedResponse[T]
- RBAC enforced at every endpoint
- Tenant isolation absolute — every query scoped to firm_id without exception
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry
- Audit logging on every sensitive action
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment
- Background tasks that touch the database must create their own SessionLocal() in a try/finally block — never pass the request db session into a background task
- Never use native_enum=True for enums whose values contain dots or special characters — always use sa.Enum(MyEnum, native_enum=False)
- Behavioral event log: fire-and-forget only, never block the main operation, service layer only, own session, never inherit the request session
- Always use SQLAlchemy 2.0 Mapped[] syntax — never Column() style
- Always use Pydantic v2 — model_dump() and field_validator() only, never .dict() or @validator
- DATABASE_URL uses postgresql+psycopg:// dialect prefix — never plain postgresql://
- Never use && to chain commands in PowerShell — separate every command onto its own line
- Never use em dashes anywhere in any string, copy, or comment

---

# MIGRATION PROCEDURE — FOLLOW EVERY TIME
1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

# PHASE INSTRUCTIONS — FAILED LOGIN EMAIL ALERT

## Context
When a staff login attempt fails, the event is already logged to the audit log
and behavioral event log in app/services/auth_service.py.
This build adds one thing: send an email alert to the firm owner.

No migration. No frontend changes. One targeted edit to auth_service.py only.

Rules:
- Fire-and-forget only — never block the login response
- Use a background thread exactly like other fire-and-forget email patterns
- Never send the alert if the firm owner cannot be found
- Never surface email errors to the user
- The alert goes to the firm owner email, not the user who failed to log in

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before failed login alert"

---

## VERIFY BEFORE STARTING
grep -n "login_failed\|write_audit_log\|log_event\|failed_login_count" app/services/auth_service.py
Paste output before touching anything.

---

## Change 1: Add failed login email alert to auth_service.py

Find the block in authenticate_staff that handles invalid credentials.
It currently:
1. Calls write_audit_log with action="user.login_failed"
2. Calls log_event with event_type="user.login_failed"
3. Loads firm settings and increments failed_login_count

After step 2 (after the log_event call, before the firm settings load),
add a fire-and-forget email alert in a background thread:

```python
# Fire-and-forget failed login alert to firm owner
def _send_failed_login_alert(firm_id, user_email: str) -> None:
    try:
        from app.db.session import SessionLocal
        from app.models.user import User
        from app.core.enums import UserRole
        from app.models.firm import Firm
        from app.services.email_service import EmailService
        _db = SessionLocal()
        try:
            firm_owner = _db.query(User).filter(
                User.firm_id == firm_id,
                User.role == UserRole.firm_owner,
                User.is_active == True,
            ).first()
            if not firm_owner:
                return
            firm = _db.query(Firm).filter(Firm.id == firm_id).first()
            firm_name = firm.name if firm else "Your firm"
            EmailService.send_notification_email(
                to_email=firm_owner.email,
                firm_name=firm_name,
                recipient_name=firm_owner.full_name or "Firm Owner",
                title="Failed login attempt",
                body=f"A failed login attempt was made for the account {user_email}. If this was not you or a member of your team, review your firm security settings.",
                app_url="https://app.jammpx.com/settings?tab=security",
            )
        finally:
            _db.close()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed login alert email error: %s", type(exc).__name__)
```

Define this function at the module level in auth_service.py
(not inside authenticate_staff).

Then inside the invalid credentials block, after the log_event call,
add:
```python
import threading
threading.Thread(
    target=_send_failed_login_alert,
    kwargs={"firm_id": user.firm_id, "user_email": user.email},
    daemon=True,
).start()
```

Important: only fire this when user is not None (we already know the
email exists but the password was wrong). Do not fire it when user
is None (unknown email) to avoid leaking account existence.

---

## Verify after changes
grep -n "_send_failed_login_alert\|Failed login alert\|threading.Thread" app/services/auth_service.py
All three must appear.
python -m py_compile app/services/auth_service.py
Must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "failed login email alert to firm owner"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager