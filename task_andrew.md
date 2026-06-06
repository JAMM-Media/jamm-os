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

# PHASE INSTRUCTIONS — PASSWORD POLICY + SESSION TIMEOUT — FRONTEND

## Context
No backend changes. Frontend only.
The SecurityTab already exists at:
frontend/src/components/settings/SecurityTab.tsx

It currently has one section: Staff login policy (radio buttons for password/magic link/either).
We are adding two new sections below it:
1. Password policy — min length, require uppercase, require number, require special char, max failed attempts
2. Session timeout — dropdown selecting token expiry duration

Both sections read from and write to PATCH /users/firm/settings using the existing
settingsApi pattern already used in the file.

The settings keys are:
- password_policy: { min_length, require_uppercase, require_number, require_special, max_failed_attempts }
- session_timeout_minutes: number

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before password policy frontend"

---

## VERIFY BEFORE STARTING
grep -n "settingsApi\|staff_auth_policy\|handleSave\|getMyFirm" frontend/src/components/settings/SecurityTab.tsx
Paste output before touching anything.

---

## Change 1: Rewrite SecurityTab.tsx to add two new sections

Read the full current SecurityTab.tsx before making any changes.
Keep the existing Staff login policy section exactly as it is.
Add two new sections below it separated by a divider line.

### New state to add
Add these state variables alongside the existing policy state:

  // Password policy
  const [minLength, setMinLength] = useState(8)
  const [requireUppercase, setRequireUppercase] = useState(false)
  const [requireNumber, setRequireNumber] = useState(false)
  const [requireSpecial, setRequireSpecial] = useState(false)
  const [maxFailedAttempts, setMaxFailedAttempts] = useState(5)
  const [savingPassword, setSavingPassword] = useState(false)

  // Session timeout
  const [sessionTimeout, setSessionTimeout] = useState(480)
  const [savingTimeout, setSavingTimeout] = useState(false)

### Update the useEffect that loads firm data
The existing useEffect calls settingsApi.getMyFirm() and reads staff_auth_policy.
Extend it to also read password_policy and session_timeout_minutes from the response:

  const passwordPolicy = data.settings?.password_policy || {}
  setMinLength(passwordPolicy.min_length ?? 8)
  setRequireUppercase(passwordPolicy.require_uppercase ?? false)
  setRequireNumber(passwordPolicy.require_number ?? false)
  setRequireSpecial(passwordPolicy.require_special ?? false)
  setMaxFailedAttempts(passwordPolicy.max_failed_attempts ?? 5)
  setSessionTimeout(data.settings?.session_timeout_minutes ?? 480)

Note: the firm settings are nested under data.settings in the API response.
Check how the existing code reads staff_auth_policy to confirm the exact
response shape before writing this — it may be at data.staff_auth_policy
not data.settings.staff_auth_policy.

### Save function for password policy
Add an async function handleSavePasswordPolicy():
  setSavingPassword(true)
  try {
    await settingsApi.updateFirmSettings({
      password_policy: {
        min_length: minLength,
        require_uppercase: requireUppercase,
        require_number: requireNumber,
        require_special: requireSpecial,
        max_failed_attempts: maxFailedAttempts,
      }
    })
    toast.success('Password policy saved.')
  } catch {
    toast.error('Could not save. Please try again.')
  } finally {
    setSavingPassword(false)
  }

### Save function for session timeout
Add an async function handleSaveSessionTimeout(minutes: number):
  setSessionTimeout(minutes)
  setSavingTimeout(true)
  try {
    await settingsApi.updateFirmSettings({ session_timeout_minutes: minutes })
    toast.success('Session timeout updated.')
  } catch {
    toast.error('Could not save. Please try again.')
  } finally {
    setSavingTimeout(false)
  }

### Check settingsApi for updateFirmSettings
The settingsApi may not have an updateFirmSettings method yet.
grep for it in frontend/src/lib/api/settingsApi.ts.
If it does not exist, add it:
  updateFirmSettings: (payload: Record<string, unknown>) =>
    api.patch('/users/firm/settings', payload),

### Section 2: Password Policy UI

Add a divider between sections:
  <div className="border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] my-6" />

Then add this section:

  <div>
    <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
      Password policy
    </p>
    <p className="text-[12px] text-[#6B7280] mb-4">
      Set requirements for staff passwords at your firm.
    </p>

    Minimum length row:
    Label "Minimum length" left, number input right (width 64px, value minLength,
    min=6 max=32, onChange sets minLength).

    Four toggle rows below it, each with label left and a toggle switch right:
    - "Require uppercase letter" — requireUppercase
    - "Require number" — requireNumber
    - "Require special character" — requireSpecial

    Max failed attempts row:
    Label "Lock account after N failed attempts" left,
    number input right (width 64px, value maxFailedAttempts, min=3 max=20).
    Muted helper text below: "Account is locked for 30 minutes after this many consecutive failed logins."

    Save button right-aligned below:
    "Save password policy" — brand blue background, white text, 32px height,
    disabled and showing spinner while savingPassword is true.
  </div>

Use the same toggle switch component pattern already in the file if one exists,
or use a simple checkbox-based toggle matching the design system.
All rows use consistent spacing: 12px padding, flex row, items-center, justify-between.

### Section 3: Session Timeout UI

Add another divider, then:

  <div>
    <p className="text-[13px] font-[500] text-brand dark:text-[#EDEEF0] mb-1">
      Session timeout
    </p>
    <p className="text-[12px] text-[#6B7280] mb-4">
      How long staff stay logged in before being asked to sign in again.
    </p>

    A set of radio-style option cards (same pattern as the existing login policy cards):
    Options:
    - value: 30,   label: "30 minutes",  description: "High security. Staff sign in frequently."
    - value: 60,   label: "1 hour",      description: "Recommended for shared workstations."
    - value: 120,  label: "2 hours",     description: "Balanced security for most firms."
    - value: 240,  label: "4 hours",     description: "Standard for dedicated work machines."
    - value: 480,  label: "8 hours",     description: "Default. One sign-in per workday."
    - value: 1440, label: "24 hours",    description: "Convenient for trusted devices."

    Selecting any option immediately calls handleSaveSessionTimeout(value).
    Show saving spinner next to selected option while savingTimeout is true.
    Amber note at bottom: "Changes take effect on the next login. Active sessions are not affected."
  </div>

---

## Verify after all changes
grep -n "handleSavePasswordPolicy\|handleSaveSessionTimeout\|minLength\|sessionTimeout" frontend/src/components/settings/SecurityTab.tsx
grep -n "updateFirmSettings" frontend/src/lib/api/settingsApi.ts
Both must return results.

Check TypeScript:
cd frontend
npx tsc --noEmit
Zero errors required before deploying.

---

## Deploy sequence
git add -A
git commit -m "password policy and session timeout frontend"
git push origin main
Frontend deploys automatically via Vercel.
No backend deploy needed.