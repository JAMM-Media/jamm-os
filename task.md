 STANDING RULES
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK — run before touching anything
git add -A
git commit -m "checkpoint before autopilot 3B fixes"
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.

---

# Standing verification rules — apply to every step in this task:
- Never report a file as created without running ls -la on it and including the output
- Never report a fix as working without running grep to confirm the change landed and including the output
- If any verification fails, fix it before moving to the next step
- After all steps, run: python3 -c "from app.api.concierge.route import router; print('OK')"
- Include all verification output in your final summary

---

# POST-TASK — run after task completes
find app/api/concierge/ -name "*.py" | sort
ls migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Section 3: Task to perform

Task: Create frontend/src/lib/events/conciergeEvents.ts

Create the directory if it does not exist: frontend/src/lib/events/

Create the file frontend/src/lib/events/conciergeEvents.ts with exactly this content:

// frontend/src/lib/events/conciergeEvents.ts

const CONCIERGE_ACTION_EVENT = 'jamm:concierge-action'

export interface ConciergeAction {
  type: 'navigate' | 'open-modal' | 'navigate-and-open'
  route?: string
  modal?: string
  prefill?: Record<string, string>
}

export function emitConciergeAction(action: ConciergeAction) {
  window.dispatchEvent(new CustomEvent(CONCIERGE_ACTION_EVENT, { detail: action }))
}

export function onConciergeAction(handler: (action: ConciergeAction) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<ConciergeAction>).detail)
  window.addEventListener(CONCIERGE_ACTION_EVENT, listener)
  return () => window.removeEventListener(CONCIERGE_ACTION_EVENT, listener)
}

export function setFormDirty(dirty: boolean) {
  window.dispatchEvent(new CustomEvent('jamm:form-dirty', { detail: { dirty } }))
}

After creating the file:
1. ls -la frontend/src/lib/events/conciergeEvents.ts
2. cat frontend/src/lib/events/conciergeEvents.ts
3. npm run build from frontend directory — zero TypeScript errors
4. Report the exact output of all three commands