# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
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

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Phase 4B: Engagement Type Prefill

Three files. Do them in order. Do not move to the next file until the verify step passes.

---

## File 1: prompts.py

Task: Fix the new-engagement prefill example to include engagementType, and remove the stale `fields` reference.

VERIFY BEFORE ACT:
Run these and paste the full output:

```
grep -n "new-engagement\|fields" /home/corby/jamm-os/app/api/concierge/prompts.py
```

Paste before touching anything.

Make exactly two changes:

Change 1 — line 249, update the new-engagement example to include engagementType in prefill:
OLD:
```
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/[client-name-slug]","modal":"new-engagement","prefill":{"client":"[client name]"}}
```
NEW:
```
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/[client-name-slug]","modal":"new-engagement","prefill":{"client":"[client name]","engagementType":"[full type value e.g. tax_return_1040]"}}
```

Change 2 — line 357, replace the stale `fields` reference:
OLD:
```
CONCIERGE_ACTION:{"type":"...","route":"...","modal":"...","fields":{...}}
```
NEW:
```
CONCIERGE_ACTION:{"type":"...","route":"...","modal":"...","prefill":{...}}
```

Do not change anything else.

VERIFY AFTER ACT:
```
grep -n "new-engagement\|fields" /home/corby/jamm-os/app/api/concierge/prompts.py
```
Confirm: new-engagement example now shows engagementType in prefill. Confirm: no remaining `"fields":{` reference.

---

## File 2: NewEngagementModal.tsx

Task: Add initialEngagementType prop and apply it to the form on open.

VERIFY BEFORE ACT:
Run this and paste the full output:
```
grep -n "initialEngagementType\|preselectedClientId\|useEffect\|engagementCategory\|engagementType" /home/corby/jamm-os/frontend/src/components/engagements/NewEngagementModal.tsx
```

Paste before touching anything.

Make exactly three changes:

Change 1 — add initialEngagementType to the props interface:
OLD:
```
interface NewEngagementModalProps {
  open: boolean
  onClose: () => void
  onAdd: (engagement: Engagement) => void
  preselectedClientId?: string
}
```
NEW:
```
interface NewEngagementModalProps {
  open: boolean
  onClose: () => void
  onAdd: (engagement: Engagement) => void
  preselectedClientId?: string
  initialEngagementType?: string
}
```

Change 2 — destructure the new prop:
OLD:
```
export function NewEngagementModal({
  open,
  onClose,
  onAdd,
  preselectedClientId,
}: NewEngagementModalProps) {
```
NEW:
```
export function NewEngagementModal({
  open,
  onClose,
  onAdd,
  preselectedClientId,
  initialEngagementType,
}: NewEngagementModalProps) {
```

Change 3 — add a useEffect that applies initialEngagementType when the modal opens. The value may be a full subtype like `tax_return_1040` or a top-level category like `advisory`. Split on the second underscore only for known two-part categories (tax_return, bookkeeping, payroll). Add this useEffect immediately after the existing useState declarations, before the useFetch call:

OLD:
```
  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
```
NEW:
```
  useEffect(() => {
    if (!open || !initialEngagementType) return
    const knownCategories = ['tax_return', 'bookkeeping', 'payroll']
    const matched = knownCategories.find((cat) => initialEngagementType.startsWith(cat + '_'))
    if (matched) {
      setForm((prev) => ({ ...prev, engagementCategory: matched, engagementType: initialEngagementType }))
    } else {
      setForm((prev) => ({ ...prev, engagementCategory: initialEngagementType, engagementType: '' }))
    }
  }, [open, initialEngagementType])

  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
```

Also add `useEffect` to the import at the top of the file if it is not already imported:
OLD:
```
import { useState } from 'react'
```
NEW:
```
import { useState, useEffect } from 'react'
```

Do not change anything else.

VERIFY AFTER ACT:
1.
```
grep -n "initialEngagementType\|useEffect" /home/corby/jamm-os/frontend/src/components/engagements/NewEngagementModal.tsx
```
Confirm prop exists, useEffect exists.
2.
```
cd /home/corby/jamm-os/frontend
npm run build
```
Zero TypeScript errors.

---

## File 3: clients/[id]/page.tsx

Task: Read action.prefill.engagementType from both the sessionStorage useEffect and the onConciergeAction listener, and pass it to NewEngagementModal.

VERIFY BEFORE ACT:
Run this and paste the full output:
```
grep -n "initialEngagementType\|newEngagementOpen\|prefill\|onConciergeAction\|NewEngagementModal" /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```

Paste before touching anything.

Make exactly three changes:

Change 1 — add initialEngagementType state next to newEngagementOpen:
OLD:
```
  const [newEngagementOpen, setNewEngagementOpen] = useState(false)
```
NEW:
```
  const [newEngagementOpen, setNewEngagementOpen] = useState(false)
  const [initialEngagementType, setInitialEngagementType] = useState<string | undefined>()
```

Change 2 — update the sessionStorage useEffect to read prefill:
OLD:
```
      if (action.modal === 'new-engagement') {
        sessionStorage.removeItem('jamm_concierge_pending')
        setNewEngagementOpen(true)
      }
```
NEW:
```
      if (action.modal === 'new-engagement') {
        sessionStorage.removeItem('jamm_concierge_pending')
        if (action.prefill?.engagementType) setInitialEngagementType(action.prefill.engagementType)
        setNewEngagementOpen(true)
      }
```

Change 3 — update the onConciergeAction listener to read prefill:
OLD:
```
      if (action.modal === 'new-engagement') {
        setActiveTab('engagements')
        setNewEngagementOpen(true)
      }
```
NEW:
```
      if (action.modal === 'new-engagement') {
        setActiveTab('engagements')
        if (action.prefill?.engagementType) setInitialEngagementType(action.prefill.engagementType)
        setNewEngagementOpen(true)
      }
```

Change 4 — pass initialEngagementType to NewEngagementModal and clear it on close:
OLD:
```
      <NewEngagementModal
        open={newEngagementOpen}
        onClose={() => setNewEngagementOpen(false)}
        onAdd={(eng: Engagement) => {
          setNewEngagementOpen(false)
          // Refresh engagement list after creation
          void eng
        }}
        preselectedClientId={clientId}
      />
```
NEW:
```
      <NewEngagementModal
        open={newEngagementOpen}
        onClose={() => { setNewEngagementOpen(false); setInitialEngagementType(undefined) }}
        onAdd={(eng: Engagement) => {
          setNewEngagementOpen(false)
          setInitialEngagementType(undefined)
          void eng
        }}
        preselectedClientId={clientId}
        initialEngagementType={initialEngagementType}
      />
```

Do not change anything else.

VERIFY AFTER ACT:
1.
```
grep -n "initialEngagementType\|prefill" /home/corby/jamm-os/frontend/src/app/clients/\[id\]/page.tsx
```
Confirm four hits: state declaration, both reads of action.prefill.engagementType, and the prop on NewEngagementModal.
2.
```
cd /home/corby/jamm-os/frontend
npm run build
```
Zero TypeScript errors.
3. Test in browser: with autopilot on, say "create a tax return engagement for Patricia Nguyen". Confirm the drawer opens with Patricia pre-selected and Tax Return pre-selected in the Type field.