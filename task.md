# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed. Do not skip steps or reorder them.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix NewEngagementModal: wire handleSubmit to the API

**File to edit:** `frontend/src/components/engagements/NewEngagementModal.tsx`

**Problem:** `handleSubmit` builds a fake local engagement object with `id: \`e${Date.now()}\`` and calls `onAdd` immediately. It never calls `engagementsApi.create`. The engagement appears in the list momentarily with a garbage ID, fails when navigated to (422 — not a valid UUID), and disappears on the next data fetch.

**Fix:** Make `handleSubmit` async, call `engagementsApi.create` with the form data, and only call `onAdd` with the real server-returned engagement on success.

Find the `handleSubmit` function. It currently looks like:

```tsx
function handleSubmit() {
  const validation = validate(form)
  if (Object.keys(validation).length > 0) {
    setErrors(validation)
    return
  }

  const newEngagement: Engagement = {
    id: `e${Date.now()}`,
    name: form.name.trim(),
    description: null,
    status: 'not-started',
    startDate: null,
    endDate: form.endDate,
    filingDeadline: null,
    extendedDeadline: null,
    engagementType: form.engagementType,
    isActive: true,
    clientId: form.clientId,
    notes: null,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }

  onAdd(newEngagement)
  handleClose()
}
```

Replace it with:

```tsx
const [submitting, setSubmitting] = useState(false)

async function handleSubmit() {
  const validation = validate(form)
  if (Object.keys(validation).length > 0) {
    setErrors(validation)
    return
  }

  setSubmitting(true)
  try {
    const created = await engagementsApi.create({
      name: form.name.trim(),
      client_id: form.clientId,
      engagement_type: form.engagementType || undefined,
      end_date: form.endDate || undefined,
    })
    onAdd(created)
    handleClose()
  } catch {
    toast.error('Failed to create engagement. Please try again.')
  } finally {
    setSubmitting(false)
  }
}
```

Also update the Save button to disable and show a loading state while submitting. Find the Save button in the modal footer — it currently looks like:

```tsx
<button
  onClick={handleSubmit}
  className="h-9 px-4 rounded-[6px] bg-brand ..."
>
  Save
</button>
```

Update it to:

```tsx
<button
  onClick={handleSubmit}
  disabled={submitting}
  className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
>
  {submitting ? 'Saving...' : 'Save'}
</button>
```

Check the existing imports at the top of this file:
- `useState` — likely already imported, do not duplicate
- `engagementsApi` — check if already imported; if not, add it from `@/lib/api`
- `toast` — check if already imported; if not, add `import { toast } from 'sonner'`

Only add imports that are genuinely missing.

Also reset `submitting` in `handleClose`:
```tsx
function handleClose() {
  setForm({
    name: '',
    clientId: preselectedClientId ?? '',
    engagementType: '',
    endDate: '',
  })
  setErrors({})
  setSubmitting(false)
  onClose()
}
```

---

## EXECUTION ORDER

1. Task 1 — frontend only: NewEngagementModal.tsx

After the task: report every file modified and confirm no TypeScript errors.