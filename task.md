# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix fee auto-populate and template dropdown in SendEngagementLetterModal

**File to edit:** `frontend/src/components/engagements/SendEngagementLetterModal.tsx`

### Fix 1 — Fee auto-populate: move logic inside the firm fetch callback

The current approach uses two separate useEffects which creates a race condition. The fee schedule fetch is async — by the time it resolves, the auto-populate useEffect has already run against an empty schedule.

Fix: move the fee auto-populate logic directly inside the firm fetch `.then()` callback so it runs with the actual data:

Find useEffect 1 (the firm/fee schedule fetch):
```tsx
useEffect(() => {
  if (!open) return
  api.get('/users/firm').then((res) => {
    const schedule = res.data?.settings?.fee_schedule ?? {}
    setFeeSchedule(schedule)
  }).catch(() => {})
}, [open])
```

Replace with:
```tsx
useEffect(() => {
  if (!open) return
  api.get('/users/firm').then((res) => {
    const schedule: Record<string, string> = res.data?.settings?.fee_schedule ?? {}
    setFeeSchedule(schedule)
    // Auto-populate fee immediately when schedule loads
    if (engagementType && schedule[engagementType]) {
      setFeeAmount((prev) => prev || `$${schedule[engagementType]}`)
    }
  }).catch(() => {})
}, [open, engagementType])
```

Then **delete** useEffect 2 entirely (the one with `[engagementType, feeSchedule]` dependency) — it's no longer needed since the logic moved into useEffect 1.

### Fix 2 — Template dropdown: remove the console.log and show all templates unfiltered

Remove the `console.log` line that was added for debugging.

Also change the template sort so the dropdown label makes it clear which template matches the engagement type. Instead of silently sorting, add a visual indicator. Find the `templateOptions` computation:

```tsx
const templateOptions = templates.map((t) => ({ value: t.id, label: t.name }))
```

Replace with:
```tsx
const templateOptions = templates.map((t) => ({
  value: t.id,
  label: t.engagement_type === engagementType
    ? `${t.name} ★`
    : t.name,
}))
```

This puts a ★ next to the template that matches the engagement type so staff can quickly see which one is the best match. All templates still appear.

Run TypeScript check after.