# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix engagements type filter: "All Types" must show all engagements

**File to edit:** `frontend/src/app/engagements/page.tsx`

**Problem:** `uniqueTypes` is computed from `engagements` (the server-fetched array). Newly created engagements are added to `localEngagements` separately. When the type filter is set to "All Types" (`typeFilter === 'all'`), the filter logic should show everything — but there is a secondary issue: `uniqueTypes` only includes types from the server fetch, so any type that only exists in `localEngagements` won't appear in the dropdown. More critically, there may be a logic error where engagements with a type not in `uniqueTypes` are being excluded even when `typeFilter === 'all'`.

**Fix 1 — Compute `uniqueTypes` from the combined list:**

Find this line:
```tsx
const uniqueTypes = Array.from(new Set(engagements.map((e) => e.engagementType).filter(Boolean))) as string[]
```

Replace it with:
```tsx
const allEngagements = [...localEngagements, ...engagements]
const uniqueTypes = Array.from(new Set(allEngagements.map((e) => e.engagementType).filter(Boolean))) as string[]
```

**Fix 2 — Verify the filtered computation uses the combined list:**

Find the `filtered` computation. It should be filtering from `engagements` but needs to include `localEngagements` too. Check whether it currently reads from `engagements` or `allEngagements`. If it reads from `engagements`, update it to use `allEngagements` instead:

```tsx
const filtered = allEngagements.filter((e) => {
  if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
  if (statusFilter !== 'all' && e.status !== statusFilter) return false
  if (typeFilter !== 'all' && e.engagementType !== typeFilter) return false
  return true
})
```

**Fix 3 — Remove the duplicate `localEngagements` prepend:**

Currently `handleAdd` does `setLocalEngagements((prev) => [engagement, ...prev])` and the list renders from a combined `[...localEngagements, ...engagements]` or similar. Now that `filtered` uses `allEngagements` which already includes `localEngagements`, make sure the final rendered list uses `filtered` directly and doesn't double-add local engagements.

Read the current rendering logic carefully before making this change — find where `localEngagements` and `engagements` are combined for display and make sure `filtered` is the single source of truth for what gets rendered.

---

## EXECUTION ORDER

1. Task 1 — frontend only: engagements/page.tsx

After the task: report every file modified and confirm no TypeScript errors.