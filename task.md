# JAMM PX — Fee Schedule

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Backend: firm owner endpoint to update firm settings

**File to edit:** `app/api/users.py`

Add a new endpoint that allows a firm_owner to update their own firm's settings JSON blob. This is separate from the system_admin-only PATCH on /firms/{firm_id}.

Add this endpoint after the existing `GET /users/firm` endpoint:

```python
# -------------------------------------------------------------------
# PATCH /users/firm/settings — Firm owner updates their firm settings
# -------------------------------------------------------------------
@router.patch("/firm/settings", response_model=FirmOut)
def update_my_firm_settings(
    payload: dict,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    """
    Allows a firm_owner to update their firm's settings JSON blob.
    Merges the payload into the existing settings dict rather than
    replacing it entirely — so updating fee_schedule does not wipe
    other settings keys.
    """
    firm = crud_firm.get_firm(db, current_firm.id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found")

    # Merge into existing settings rather than replace
    current_settings = firm.settings or {}
    merged = {**current_settings, **payload}

    updated = crud_firm.update_firm(
        db,
        firm,
        FirmUpdate(settings=merged),
    )
    return updated
```

Check existing imports in users.py — `FirmOut`, `FirmUpdate`, `crud_firm`, `require_firm_owner` should already be imported. Add only what is missing.

---

## TASK 2 — Frontend: FeeScheduleTab component

**File to create:** `frontend/src/components/settings/FeeScheduleTab.tsx`

This is a new Settings tab component. Firm owners see and edit their standard fees per engagement type. The data is stored in `firm.settings.fee_schedule` as a flat object mapping engagement type strings to fee strings.

```tsx
// frontend/src/components/settings/FeeScheduleTab.tsx
'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import { toast } from 'sonner'

// All engagement types with human-readable labels grouped by category
const FEE_SCHEDULE_ITEMS = [
  { category: 'Tax Returns', items: [
    { key: 'tax_return_1040', label: '1040 — Individual' },
    { key: 'tax_return_1120', label: '1120 — C-Corporation' },
    { key: 'tax_return_1120s', label: '1120-S — S-Corporation' },
    { key: 'tax_return_1065', label: '1065 — Partnership' },
    { key: 'tax_return_1041', label: '1041 — Trust / Estate Income' },
    { key: 'tax_return_706', label: '706 — Estate Tax' },
    { key: 'amended_return_1040x', label: '1040-X — Amended Return' },
  ]},
  { category: 'Extensions', items: [
    { key: 'extension_4868', label: '4868 — Individual Extension' },
    { key: 'extension_7004', label: '7004 — Business Extension' },
    { key: 'extension_8868', label: '8868 — Exempt Org Extension' },
  ]},
  { category: 'Bookkeeping', items: [
    { key: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
    { key: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
  ]},
  { category: 'Payroll', items: [
    { key: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
  ]},
  { category: 'Other Services', items: [
    { key: 'tax_planning_advisory', label: 'Tax Planning / Advisory' },
    { key: 'audit_representation', label: 'Audit Representation' },
    { key: 'custom', label: 'Other / Custom' },
  ]},
]

interface FeeScheduleTabProps {
  firmSettings: Record<string, unknown> | null
  onSaved: () => void
}

export default function FeeScheduleTab({ firmSettings, onSaved }: FeeScheduleTabProps) {
  const [fees, setFees] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    const existing = (firmSettings?.fee_schedule as Record<string, string>) ?? {}
    setFees(existing)
    setDirty(false)
  }, [firmSettings])

  function handleChange(key: string, value: string) {
    setFees((prev) => ({ ...prev, [key]: value }))
    setDirty(true)
  }

  async function handleSave() {
    setSaving(true)
    try {
      await api.patch('/users/firm/settings', { fee_schedule: fees })
      toast.success('Fee schedule saved')
      setDirty(false)
      onSaved()
    } catch {
      toast.error('Failed to save fee schedule')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div>
        <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Fee Schedule</h2>
        <p className="text-[12px] text-[#6B7280] mt-0.5">
          Set your standard fees per engagement type. These auto-populate when sending engagement letters.
          Leave blank for types you don't offer or prefer to price individually.
        </p>
      </div>

      {FEE_SCHEDULE_ITEMS.map((group) => (
        <div key={group.category} className="flex flex-col gap-3">
          <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
            {group.category}
          </p>
          <div className="bg-surface-card dark:bg-dark-card rounded-[8px] overflow-hidden">
            {group.items.map((item, idx) => (
              <div
                key={item.key}
                className={`flex items-center justify-between px-4 py-3 gap-4 ${
                  idx < group.items.length - 1
                    ? 'border-b border-surface-border dark:border-dark-border'
                    : ''
                }`}
              >
                <span className="text-[13px] text-brand dark:text-[#EDEEF0] flex-1">
                  {item.label}
                </span>
                <div className="relative flex items-center">
                  <span className="absolute left-3 text-[13px] text-[#6B7280]">$</span>
                  <input
                    type="text"
                    inputMode="numeric"
                    value={fees[item.key] ?? ''}
                    onChange={(e) => handleChange(item.key, e.target.value)}
                    placeholder="—"
                    className="w-28 pl-6 pr-3 py-1.5 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] text-right"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="flex items-center justify-between pt-2">
        <p className="text-[11px] text-[#6B7280]">
          Fee amounts are stored per firm and used to pre-fill engagement letters.
          They are never shared with clients directly.
        </p>
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? 'Saving...' : 'Save Fee Schedule'}
        </button>
      </div>
    </div>
  )
}
```

---

## TASK 3 — Frontend: add Fee Schedule tab to Settings page

**File to edit:** `frontend/src/app/settings/page.tsx`

### Step 1 — Import the component

Add to existing imports:
```tsx
import FeeScheduleTab from '@/components/settings/FeeScheduleTab'
```

### Step 2 — Add to TABS constant

Add after the `automations` entry, visible to firm_owner only:
```tsx
{ key: 'fee_schedule', label: 'Fee Schedule' },
```

### Step 3 — Add to tab filter

In the tab bar filter function:
```tsx
.filter((tab) => {
  if (tab.key === 'automations') return canSeeAutomations
  if (tab.key === 'security') return canSeeSecurity
  if (tab.key === 'fee_schedule') return isFirmOwner
  return true
})
```

### Step 4 — Add the tab content

The `firmData` fetch already loads `GET /users/firm`. The `FirmOut` schema includes `settings` as a JSON field. Update the `FirmDetails` interface in `settingsApi.ts` to include `settings`:

**File to edit:** `frontend/src/lib/api/settingsApi.ts`

Add `settings` to `FirmDetails`:
```tsx
export interface FirmDetails {
  id: string
  name: string
  slug: string
  subscription_tier: string
  is_active: boolean
  staff_auth_policy: string
  settings: Record<string, unknown> | null
  created_at: string
  updated_at: string
}
```

Also add a `updateFirmSettings` method to `settingsApi`:
```tsx
updateFirmSettings: (settings: Record<string, unknown>) =>
  api.patch('/users/firm/settings', settings),
```

Back in `settings/page.tsx`, add the fee schedule tab content alongside the other tab conditionals:
```tsx
{activeTab === 'fee_schedule' && (
  <FeeScheduleTab
    firmSettings={firmData?.settings ?? null}
    onSaved={() => { /* firmData will refetch on next focus */ }}
  />
)}
```

---

## TASK 4 — Frontend: auto-populate fee in SendEngagementLetterModal

**File to edit:** `frontend/src/components/engagements/SendEngagementLetterModal.tsx`

When a template is selected, look up the engagement type in the firm's fee schedule and pre-fill the fee amount field automatically.

### Step 1 — Add fee schedule fetch

Add a state variable and fetch alongside the existing template fetch:
```tsx
const [feeSchedule, setFeeSchedule] = useState<Record<string, string>>({})

useEffect(() => {
  if (!open) return
  api.get('/users/firm').then((res) => {
    const schedule = res.data?.settings?.fee_schedule ?? {}
    setFeeSchedule(schedule)
  }).catch(() => {})
}, [open])
```

### Step 2 — Auto-populate fee when engagement type matches

Add a `useEffect` that fires when `engagementType` or `feeSchedule` changes:
```tsx
useEffect(() => {
  if (!engagementType || !feeSchedule) return
  const scheduledFee = feeSchedule[engagementType]
  if (scheduledFee && !feeAmount) {
    setFeeAmount(`$${scheduledFee}`)
  }
}, [engagementType, feeSchedule])
```

This only pre-fills if the fee field is currently empty — it won't overwrite something the user already typed.

---

## EXECUTION ORDER

1. Task 1 — backend: app/api/users.py
2. Task 2 — frontend: create FeeScheduleTab component
3. Task 3 — frontend: settings/page.tsx and settingsApi.ts
4. Task 4 — frontend: SendEngagementLetterModal.tsx

After all tasks: report every file modified and confirm no TypeScript errors.