# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix engagements type filter dropdown: show human-readable labels

**File to edit:** `frontend/src/app/engagements/page.tsx`

**Problem 1:** The type filter dropdown shows raw backend enum values (`tax_return_1040`, `custom`, etc.) instead of formatted labels. It should show "Tax Return 1040", "Custom", etc.

**Problem 2:** The "All Types" option is not showing all engagements. Add a `console.log` to debug this, and also fix the display issue.

### Fix 1 — Import formatEngagementType

Check if `formatEngagementType` is already imported from `@/lib/utils`. If not, add it to the existing import line.

### Fix 2 — Add debug logging temporarily

Add this line immediately after the `filtered` computation (after line `return true })`):

```tsx
console.log('DEBUG allEngagements:', allEngagements.map(e => ({ id: e.id, name: e.name, type: e.engagementType, status: e.status })))
console.log('DEBUG filtered:', filtered.map(e => ({ id: e.id, name: e.name, type: e.engagementType })))
console.log('DEBUG typeFilter:', typeFilter, 'statusFilter:', statusFilter)
```

### Fix 3 — Fix the type filter dropdown labels

Find the type filter `<select>` dropdown. It currently renders options like:
```tsx
{uniqueTypes.map((t) => (
  <option key={t} value={t}>{t}</option>
))}
```

Change it to show formatted labels while keeping the raw value for filtering:
```tsx
{uniqueTypes.map((t) => (
  <option key={t} value={t}>{formatEngagementType(t)}</option>
))}
```

### Fix 4 — Add "Custom" to the status options display

The status filter dropdown hardcodes statuses. Verify it includes all statuses that engagements can have. The current options are: All Statuses, Planning, Active, In Review, Completed, Archived. If `not_started` or any other status is missing, add it.

---

## EXECUTION ORDER

1. Task 1 — frontend only: engagements/page.tsx

After the task: report every file modified and confirm no TypeScript errors.