# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix page scrolling: remove h-full and overflow-y-auto from page wrapper divs

**Problem:** The AppShell `<main>` element already has `overflow-y-auto` and handles scrolling. The page wrapper divs have `h-full` which constrains them to the viewport height, creating a nested scroll container conflict. The previous fix of adding `overflow-y-auto` to the page divs made it worse. The correct fix is removing `h-full` (and the `overflow-y-auto` we just added) from the page wrapper divs so the content flows naturally and `<main>` handles the scroll.

**In each file listed below**, find the div with className `"flex flex-col h-full p-6 gap-4 overflow-y-auto"` and change it to `"flex flex-col p-6 gap-4"` — removing both `h-full` and `overflow-y-auto`.

**Files to edit:**
1. `frontend/src/app/billing/page.tsx`
2. `frontend/src/app/billing/wip/page.tsx`
3. `frontend/src/app/calendar/page.tsx`
4. `frontend/src/app/clients/page.tsx`
5. `frontend/src/app/documents/page.tsx`
6. `frontend/src/app/engagements/page.tsx`
7. `frontend/src/app/tasks/page.tsx`

Make only this one className change in each file. Do not touch anything else.

---

## TASK 2 — Engagement creation modal: add category + form subtype dropdowns

**File to edit:** `frontend/src/components/engagements/NewEngagementModal.tsx`

**Problem:** The current Type dropdown sends a broad category string. It needs to work like the filter bar — a category dropdown that reveals a form subtype dropdown for types that have subtypes. The final `engagement_type` sent to the API should be the specific subtype value (e.g. `tax_return_1040`) not the broad category.

### Step 1 — Update form state

The form currently has `engagementType: string`. Split it into two fields:

```tsx
const [form, setForm] = useState({
  name: '',
  clientId: preselectedClientId ?? '',
  engagementCategory: '',
  engagementType: '',
  endDate: '',
})
```

Update `handleClose` and `handleChange` to reset `engagementType` when `engagementCategory` changes:

```tsx
function handleChange(field: string, value: string) {
  setForm((prev) => {
    const next = { ...prev, [field]: value }
    // Reset subtype when category changes
    if (field === 'engagementCategory') next.engagementType = ''
    return next
  })
  if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }))
}
```

### Step 2 — Update validation

The validate function currently checks `form.engagementType`. Update it so:
- If the selected category has subtypes, `engagementType` is required
- If the selected category has no subtypes, `engagementCategory` being set is sufficient

Categories with subtypes: `tax_return`, `bookkeeping`, `payroll`
Categories without subtypes: `advisory`, `audit`, `other`

```tsx
function validate(f: typeof form) {
  const errs: FormErrors = {}
  if (!f.clientId) errs.clientId = 'Please select a client.'
  if (!f.name.trim()) errs.name = 'Please enter a title.'
  if (!f.engagementCategory) errs.engagementCategory = 'Please select a type.'
  const needsSubtype = ['tax_return', 'bookkeeping', 'payroll'].includes(f.engagementCategory)
  if (needsSubtype && !f.engagementType) errs.engagementType = 'Please select a form or subtype.'
  return errs
}
```

### Step 3 — Compute the final engagement_type to send

In `handleSubmit`, compute the actual type to send:

```tsx
const finalType = form.engagementType || form.engagementCategory || undefined
```

Pass `finalType` as `engagement_type` in the API call.

### Step 4 — Update the JSX

Replace the single Type `<SelectInput>` with two conditional dropdowns.

**Remove** the existing Type FormField with its single SelectInput.

**Add** in its place:

```tsx
{/* Category */}
<FormField label="Type" required error={errors.engagementCategory}>
  <SelectInput
    value={form.engagementCategory}
    onChange={(e) => handleChange('engagementCategory', e.target.value)}
    placeholder="Select type"
    error={!!errors.engagementCategory}
    options={[
      { value: 'tax_return', label: 'Tax Return' },
      { value: 'bookkeeping', label: 'Bookkeeping' },
      { value: 'payroll', label: 'Payroll' },
      { value: 'advisory', label: 'Advisory' },
      { value: 'audit', label: 'Audit' },
      { value: 'other', label: 'Other' },
    ]}
  />
</FormField>

{/* Tax Return subtype */}
{form.engagementCategory === 'tax_return' && (
  <FormField label="Form" required error={errors.engagementType}>
    <SelectInput
      value={form.engagementType}
      onChange={(e) => handleChange('engagementType', e.target.value)}
      placeholder="Select form"
      error={!!errors.engagementType}
      options={[
        { value: 'tax_return_1040', label: '1040 — Individual' },
        { value: 'tax_return_1120', label: '1120 — C-Corporation' },
        { value: 'tax_return_1120s', label: '1120-S — S-Corporation' },
        { value: 'tax_return_1065', label: '1065 — Partnership' },
        { value: 'tax_return_1041', label: '1041 — Trust / Estate Income' },
        { value: 'tax_return_706', label: '706 — Estate Tax' },
        { value: 'amended_return_1040x', label: '1040-X — Amended Return' },
        { value: 'extension_4868', label: '4868 — Individual Extension' },
        { value: 'extension_7004', label: '7004 — Business Extension' },
        { value: 'extension_8868', label: '8868 — Exempt Org Extension' },
      ]}
    />
  </FormField>
)}

{/* Bookkeeping subtype */}
{form.engagementCategory === 'bookkeeping' && (
  <FormField label="Frequency" required error={errors.engagementType}>
    <SelectInput
      value={form.engagementType}
      onChange={(e) => handleChange('engagementType', e.target.value)}
      placeholder="Select frequency"
      error={!!errors.engagementType}
      options={[
        { value: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
        { value: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
      ]}
    />
  </FormField>
)}

{/* Payroll subtype */}
{form.engagementCategory === 'payroll' && (
  <FormField label="Form" required error={errors.engagementType}>
    <SelectInput
      value={form.engagementType}
      onChange={(e) => handleChange('engagementType', e.target.value)}
      placeholder="Select form"
      error={!!errors.engagementType}
      options={[
        { value: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
      ]}
    />
  </FormField>
)}
```

### Step 5 — Update handleClose to reset both fields

```tsx
function handleClose() {
  setForm({
    name: '',
    clientId: preselectedClientId ?? '',
    engagementCategory: '',
    engagementType: '',
    endDate: '',
  })
  setErrors({})
  setSubmitting(false)
  onClose()
}
```

---

## TASK 3 — Update engagements filter: add subtypes for all categories

**File to edit:** `frontend/src/app/engagements/page.tsx`

Currently the form filter only appears for `tax_return`. Add subtype dropdowns for `bookkeeping` and `payroll` too, and update the `getEngagementCategory` helper to correctly map `advisory` and `other` types.

### Step 1 — Update getEngagementCategory

Find the existing `getEngagementCategory` function and replace it:

```tsx
function getEngagementCategory(engagementType: string | null): string {
  if (!engagementType) return 'other'
  if (engagementType.startsWith('tax_return') || engagementType.startsWith('amended_return') || engagementType.startsWith('extension')) return 'tax_return'
  if (engagementType.startsWith('bookkeeping')) return 'bookkeeping'
  if (engagementType.startsWith('payroll')) return 'payroll'
  if (engagementType === 'tax_planning_advisory') return 'advisory'
  if (engagementType === 'audit_representation') return 'audit'
  if (engagementType === 'other_advisory') return 'advisory'
  if (engagementType === 'custom') return 'other'
  return 'other'
}
```

### Step 2 — Add bookkeeping and payroll form filters

Find the existing tax_return form filter block:
```tsx
{categoryFilter === 'tax_return' && (
  <select ...>
```

After that block, add:

```tsx
{/* Bookkeeping subtype filter */}
{categoryFilter === 'bookkeeping' && (
  <select
    value={formFilter}
    onChange={(e) => setFormFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Frequencies</option>
    <option value="bookkeeping_monthly">Monthly</option>
    <option value="bookkeeping_quarterly">Quarterly</option>
  </select>
)}

{/* Payroll subtype filter */}
{categoryFilter === 'payroll' && (
  <select
    value={formFilter}
    onChange={(e) => setFormFilter(e.target.value)}
    className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
  >
    <option value="all">All Forms</option>
    <option value="payroll_tax_941">941 — Quarterly Payroll</option>
  </select>
)}
```

---

## TASK 4 — EngagementTable: improve Type column display

**File to edit:** `frontend/src/components/engagements/EngagementTable.tsx`

The Type column currently shows `formatEngagementType(eng.engagementType)` which produces strings like "Tax Return 1040s" (underscore removed, title cased). Improve the display to show the category and form separately in a cleaner format.

Add a helper function at the top of the file (after imports):

```tsx
function formatTypeDisplay(engagementType: string | null | undefined): string {
  if (!engagementType) return '—'
  const map: Record<string, string> = {
    tax_return_1040: 'Tax Return — 1040',
    tax_return_1120: 'Tax Return — 1120',
    tax_return_1120s: 'Tax Return — 1120-S',
    tax_return_1065: 'Tax Return — 1065',
    tax_return_1041: 'Tax Return — 1041',
    tax_return_706: 'Tax Return — 706',
    amended_return_1040x: 'Amended — 1040-X',
    extension_4868: 'Extension — 4868',
    extension_7004: 'Extension — 7004',
    extension_8868: 'Extension — 8868',
    payroll_tax_941: 'Payroll — 941',
    tax_planning_advisory: 'Advisory',
    bookkeeping_monthly: 'Bookkeeping — Monthly',
    bookkeeping_quarterly: 'Bookkeeping — Quarterly',
    audit_representation: 'Audit',
    other_advisory: 'Advisory',
    custom: 'Other',
  }
  return map[engagementType] ?? engagementType.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
```

Then replace the Type cell:
```tsx
{formatEngagementType(eng.engagementType ?? '')}
```
With:
```tsx
{formatTypeDisplay(eng.engagementType)}
```

Remove the `formatEngagementType` import if it's no longer used in this file after the change.

---

## EXECUTION ORDER

1. Task 1 — all seven page files (scroll fix)
2. Task 2 — NewEngagementModal.tsx
3. Task 3 — engagements/page.tsx
4. Task 4 — EngagementTable.tsx

After all tasks: report every file modified and confirm no TypeScript errors.