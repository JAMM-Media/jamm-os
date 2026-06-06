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

# PHASE INSTRUCTIONS — AUTOMATION RULE SIMULATOR UI

## Context
The backend simulate endpoint is fully built at:
POST /automation-rules/{rule_id}/simulate
It accepts a mock_payload dict and returns:
- would_trigger: bool
- conditions_evaluated: int
- conditions_passed: bool
- trigger_event: string
- actions_that_would_execute: list of {type, order}
- rule_is_enabled: bool

The AutomationsTab component is at:
frontend/src/components/settings/AutomationsTab.tsx

It already has:
- RuleCard component with Edit button and onEdit prop
- AutomationEditModal imported and used
- canEdit flag (firm_owner or manager only)

No backend changes. No migration. Frontend only.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before automation simulator UI"

---

## VERIFY BEFORE STARTING
grep -n "RuleCard\|onEdit\|AutomationEditModal\|canEdit" frontend/src/components/settings/AutomationsTab.tsx
Paste output before touching anything.

---

## Change 1: Create frontend/src/components/settings/AutomationSimulateModal.tsx

Create this file from scratch. Path comment at top.

This is a modal component that lets firm owners test an automation rule
against a mock payload and see whether it would trigger.

Props:
  rule: { id: string, name: string, trigger_event: string, is_enabled: boolean }
  onClose: () => void

State:
  result: the API response object or null
  loading: bool
  error: string or null

On mount: result is null, show the mock payload form.

### Mock payload form
The trigger_event string tells us what context this rule fires in.
Show a simple key-value pair form with 2-3 relevant fields pre-populated
based on the trigger_event value:

If trigger_event contains "engagement":
  Fields: status (text, default "completed"), engagement_type (text, default "tax_return_1040")

If trigger_event contains "invoice":
  Fields: status (text, default "overdue"), amount (text, default "500")

If trigger_event contains "document":
  Fields: status (text, default "completed"), item_count (text, default "3")

If trigger_event contains "client":
  Fields: entity_type (text, default "individual")

For all other trigger_event values:
  Show one generic field: event_type (text, pre-filled with the trigger_event value)

All fields are editable. Label each field clearly. This is a power-user feature
so plain text inputs are fine.

### Test button
"Test Rule" button at bottom of form.
Calls POST /automation-rules/{rule.id}/simulate with the form values as the payload.
Shows loading spinner while in flight.
On success: replace the form with the result view.
On error: show inline error message, keep form visible.

### Result view
Show clearly:
- Large green checkmark + "Would trigger" if would_trigger is true
- Large amber X + "Would not trigger" if would_trigger is false
- Rule enabled/disabled status in muted text
- If would_trigger is true: list the actions that would execute,
  each as a pill showing the action type
- If would_trigger is false and rule_is_enabled is false:
  add a note "This rule is currently disabled"
- "Test again" button that resets result to null and shows the form again

### Modal structure
Follow the existing modal pattern from the design system:
- Overlay: rgba(0,0,0,0.35)
- Modal background: #EDEEF0 light / #383838 dark
- Border-radius: 10px
- Header: rule name left, X close button right, border-bottom
- Body: form or result view
- Footer: Cancel button left, Test Rule button right (only shown on form view)
- Width: 480px fixed

---

## Change 2: Add simulate button to RuleCard in AutomationsTab.tsx

Find the RuleCard component.
Add two new props:
  onSimulate: (rule: AutomationRule) => void
  simulatingId: string | null

In the RuleCard JSX, find the flex row that contains the Edit button and toggle.
Add a "Test" button immediately before the Edit button:

  {canEdit && (
    <button
      onClick={() => onSimulate(rule)}
      className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] hover:text-brand dark:hover:text-[#4A7FA5] hover:underline focus:outline-none"
    >
      Test
    </button>
  )}

The Test button is muted by default, brand color on hover.
Visually secondary to the Edit button.

---

## Change 3: Wire simulate state into AutomationsTab

In AutomationsTab:
1. Add import: import AutomationSimulateModal from './AutomationSimulateModal'
2. Add state: const [simulatingRule, setSimulatingRule] = useState<AutomationRule | null>(null)
3. Pass onSimulate={setSimulatingRule} and simulatingId={simulatingRule?.id ?? null}
   to every RuleCard render (both enabled and disabled sections)
4. Add the modal at the bottom of the return, alongside AutomationEditModal:
   {simulatingRule && (
     <AutomationSimulateModal
       rule={simulatingRule}
       onClose={() => setSimulatingRule(null)}
     />
   )}

---

## Verify after all changes
grep -n "AutomationSimulateModal\|onSimulate\|simulatingRule" frontend/src/components/settings/AutomationsTab.tsx
grep -n "would_trigger\|Test Rule\|actions_that_would_execute" frontend/src/components/settings/AutomationSimulateModal.tsx
Both must return results before deploying.

Check TypeScript compiles:
cd frontend
npx tsc --noEmit
Zero errors required before deploying.

---

## Deploy sequence
git add -A
git commit -m "automation rule simulator UI restored"
git push origin main
Frontend deploys automatically via Vercel on push to main.
No backend deploy needed — no backend changes.