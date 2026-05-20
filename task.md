# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix engagements filter bar: remove broken status option, redesign type filter as category + form

**File to edit:** `frontend/src/app/engagements/page.tsx`

### Step 1 — Remove the debug console.log lines

Find and remove these three lines that were added for debugging:
```tsx
console.log('DEBUG allEngagements:', ...)
console.log('DEBUG filtered:', ...)
console.log('DEBUG typeFilter:', ...)
```

### Step 2 — Fix the status filter dropdown

Remove the "Not Started" option that was added. It has value `not-started` which does not match any real backend status and causes 0 results when selected. The valid backend status values are: `draft`, `active`, `in_review`, `completed`, `archived`. Engagements can also have `planning` stored from the frontend default.

Replace the entire status filter `<select>` options with:
```tsx
<option value="all">All Statuses</option>
<option value="draft">Draft</option>
<option value="planning">Planning</option>
<option value="active">Active</option>
<option value="in_review">In Review</option>
<option value="completed">Completed</option>
<option value="archived">Archived</option>
```

### Step 3 — Replace the single type filter with a category filter + form filter

**Remove** the existing `typeFilter` state and the single type `<select>` dropdown entirely.

**Add** two new state variables:
```tsx
const [categoryFilter, setCategoryFilter] = useState<string>('all')
const [formFilter, setFormFilter] = useState<string>('all')
```

**Remove** the existing `typeFilter` state declaration: `const [typeFilter, setTypeFilter] = useState<string>('all')`

**Add** a helper function that derives the broad category from a backend engagement type enum value. Add this before the component's return statement, after the state declarations:

```tsx
function getEngagementCategory(engagementType: string | null): string {
  if (!engagementType) return 'other'
  if (engagementType.startsWith('tax_return') || engagementType.startsWith('amended_return')) return 'tax_return'
  if (engagementType.startsWith('extension')) return 'tax_return'
  if (engagementType.startsWith('bookkeeping')) return 'bookkeeping'
  if (engagementType.startsWith('payroll')) return 'payroll'
  if (engagementType === 'tax_planning_advisory') return 'advisory'
  if (engagementType === 'audit_representation') return 'audit'
  return 'other'
}
```

**Update the filtered computation** to use `categoryFilter` and `formFilter` instead of `typeFilter`:
```tsx
const filtered = allEngagements.filter((e) => {
  if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
  if (statusFilter !== 'all' && e.status !== statusFilter) return false
  if (categoryFilter !== 'all' && getEngagementCategory(e.engagementType) !== categoryFilter) return false
  if (formFilter !== 'all' && e.engagementType !== formFilter) return false
  return true
})
```

**Remove** the `uniqueTypes` computation entirely — it's no longer needed.

**Replace the type filter `<select>`** in the JSX with two new controls:

```tsx
{/* Category filter */}
<select
  value={categoryFilter}
  onChange={(e) => {
    setCategoryFilter(e.target.value)
    setFormFilter('all') // reset form filter when category changes
  }}
  className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
>
  <option value="all">All Types</option>
  <option value="tax_return">Tax Return</option>
  <option value="bookkeeping">Bookkeeping</option>
  <option value="payroll">Payroll</option>
  <option value="advisory">Advisory</option>
  <option value="audit">Audit</option>
  <option value="other">Other</option>
</select>

{/* Form filter — only shown when category is tax_return */}
{categoryFilter === 'tax_return' && (
  <select
    value={formFilter}
    onChange={(e) => setFormFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Forms</option>
    <option value="tax_return_1040">1040</option>
    <option value="tax_return_1120">1120</option>
    <option value="tax_return_1120s">1120-S</option>
    <option value="tax_return_1065">1065</option>
    <option value="tax_return_1041">1041</option>
    <option value="tax_return_706">706</option>
    <option value="amended_return_1040x">1040-X Amended</option>
    <option value="extension_4868">4868 Extension</option>
    <option value="extension_7004">7004 Extension</option>
    <option value="extension_8868">8868 Extension</option>
  </select>
)}
```

**Update the "Clear filters" button** to reset all three filters:
```tsx
{(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all') && (
  <button
    onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); setFormFilter('all') }}
    className="text-[11px] text-[#6B7280] hover:text-brand underline"
  >
    Clear filters
  </button>
)}
```

**Update the count display** to show when any filter is active:
```tsx
{(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all') && (
  <span className="text-[11px] text-[#6B7280]">
    Showing {filtered.length} of {allEngagements.length} engagements
  </span>
)}
```

Also remove `formatEngagementType` from the import if it is no longer used anywhere in this file after removing `uniqueTypes`. Check all usages before removing.

---

## EXECUTION ORDER

1. Task 1 — frontend only: engagements/page.tsx

After the task: report every file modified and confirm no TypeScript errors.