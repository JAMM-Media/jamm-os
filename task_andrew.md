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

# PHASE INSTRUCTIONS — PASSWORD POLICY + SESSION TIMEOUT — BACKEND

## Context
The User model is at app/models/user.py.
The authenticate_staff function is in app/api/auth.py (or similar — grep for it).
Firm settings are stored as a JSON blob on firm.settings.
The existing PATCH /users/firm/settings endpoint merges settings — no new endpoint needed.
Current alembic head: a72f5a2701c1

Security settings to add:
1. Password policy: minimum length (default 8), require uppercase (default false),
   require number (default false), require special character (default false),
   max failed attempts before lockout (default 5)
2. Session timeout: configurable token expiry in minutes (default 480 = 8 hours)
   Options: 30, 60, 120, 240, 480, 1440 (30min to 24hrs)
3. Account lockout: after N failed attempts, lock account for 30 minutes

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before password policy backend"

---

## VERIFY BEFORE STARTING
grep -n "def authenticate_staff\|failed_login\|locked_until" app/api/auth.py
grep -n "class User\b\|failed_login_count\|locked_until" app/models/user.py
grep -n "ACCESS_TOKEN_EXPIRE_MINUTES" app/core/config.py
Paste all three outputs before touching anything.
Note: authenticate_staff may be in a different file — if not found in app/api/auth.py,
run: grep -rn "def authenticate_staff" app/ to find the correct file.

---

## Change 1: Add two fields to User model in app/models/user.py

Find the User model. Add these two fields after the magic_link_expires_at field:

    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

Import Integer from sqlalchemy if not already imported.
Import Optional from typing if not already imported.

---

## Change 2: Run the migration

alembic revision --autogenerate -m "0043_user_login_lockout_fields"
Read the generated file before running upgrade.
It should contain exactly two operations:
- Add column failed_login_count to users table (integer, not null, server_default 0)
- Add column locked_until to users table (nullable timestamptz)
If it contains anything else, delete and write a clean manual migration.
alembic upgrade head
alembic current
Confirm head is 0043_user_login_lockout_fields.

---

## Change 3: Update authenticate_staff to enforce lockout and increment counter

Find the authenticate_staff function.
Add these checks in this exact order:

### Step 1 — Check lockout BEFORE password verification
After loading the user (if user exists), check:
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return None, "account_locked"

### Step 2 — On failed password verification, increment counter and check lockout
Find where the function currently handles invalid credentials.
After writing the audit log and behavioral event, add:

    # Get firm password policy from firm settings
    firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
    firm_settings = firm.settings or {} if firm else {}
    max_attempts = int(firm_settings.get("password_policy", {}).get("max_failed_attempts", 5))

    user.failed_login_count = (user.failed_login_count or 0) + 1
    if user.failed_login_count >= max_attempts:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=30)
        user.failed_login_count = 0
        db.commit()
        return None, "account_locked"
    db.commit()

### Step 3 — On successful login, reset the counter
Find where the function creates the access token on success.
Before creating the token, add:
    if user.failed_login_count > 0:
        user.failed_login_count = 0
        user.locked_until = None
        db.commit()

### Step 4 — Return account_locked error in the login endpoint
Find the login endpoint that calls authenticate_staff.
Find where it handles error codes returned from authenticate_staff.
Add handling for "account_locked":
    if error == "account_locked":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to too many failed login attempts. Try again in 30 minutes."
        )

---

## Change 4: Enforce password policy on password change endpoints

Find the password change endpoint(s) — grep for "new_password" in app/api/users.py
or wherever password changes are handled.

Add a helper function validate_password_policy(password: str, policy: dict) -> str | None:
- Returns None if password passes all checks
- Returns a plain English error message if it fails
- Checks: len(password) >= policy.get("min_length", 8)
- Checks: if policy.get("require_uppercase"): any(c.isupper() for c in password)
- Checks: if policy.get("require_number"): any(c.isdigit() for c in password)
- Checks: if policy.get("require_special"): any(not c.isalnum() for c in password)

In each password change endpoint, load the firm settings, extract password_policy,
call validate_password_policy, and raise HTTPException 400 with the error message if
validation fails.

---

## Change 5: Respect session_timeout_minutes in token creation

Find create_access_token in app/core/security.py.
The function currently uses settings.ACCESS_TOKEN_EXPIRE_MINUTES as the default expiry.
This stays as the system default.

In the authenticate_staff function, after loading firm settings, pass the timeout to
token creation:
    session_timeout = int(firm_settings.get("session_timeout_minutes", settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    access_token = create_access_token(
        data={...},
        expires_delta=timedelta(minutes=session_timeout)
    )

Verify create_access_token already accepts an expires_delta parameter.
If it does not, add it: def create_access_token(data: dict, expires_delta: timedelta | None = None)

---

## Verify after all changes
grep -n "failed_login_count\|locked_until" app/models/user.py
grep -n "account_locked\|failed_login_count\|locked_until" app/api/auth.py
grep -n "validate_password_policy\|min_length\|require_uppercase" app/api/users.py
python -m py_compile app/models/user.py
python -m py_compile app/api/auth.py
All compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "password policy and session timeout backend"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager