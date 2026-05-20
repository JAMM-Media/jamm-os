# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Make Due Date optional in NewEngagementModal

**File to edit:** `frontend/src/components/engagements/NewEngagementModal.tsx`

In the `validate` function, remove the Due Date validation entirely. The backend auto-sets `filing_deadline` for tax return types so a manual due date is not required.

Find and remove this line from `validate`:
```tsx
if (!f.endDate) errs.endDate = 'Due date is required.'
```

Also update the Due Date `<FormField>` label to remove the `required` prop:

Find:
```tsx
<FormField label="Due Date" required error={errors.endDate}>
```

Change to:
```tsx
<FormField label="Due Date" error={errors.endDate}>
```

No other changes to this file.

---

## TASK 2 — Due Date column: show filing deadline with fallback

**File to edit:** `frontend/src/components/engagements/EngagementTable.tsx`

The Due Date column currently shows `eng.endDate ?? '—'`. It should show the auto-set IRS filing deadline first (`filingDeadline`), fall back to `extendedDeadline` if an extension was filed, then fall back to `endDate` if manually set, then `—`.

Also format the date to be human-readable (e.g. "Apr 15, 2026") instead of the raw ISO string.

Add a helper function near the top of the file (after `formatTypeDisplay`):

```tsx
function formatDeadline(eng: Engagement): string {
  const raw = eng.extendedDeadline ?? eng.filingDeadline ?? eng.endDate
  if (!raw) return '—'
  try {
    return new Date(raw).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  } catch {
    return raw
  }
}
```

Then find the Due Date cell in the table row. It currently reads:
```tsx
<span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
  {eng.endDate ?? '—'}
</span>
```

Replace with:
```tsx
<span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
  {formatDeadline(eng)}
</span>
```

---

## EXECUTION ORDER

1. Task 1 — NewEngagementModal.tsx
2. Task 2 — EngagementTable.tsx

After all tasks: report every file modified and confirm no TypeScript errors.