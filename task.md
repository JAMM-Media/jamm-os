# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix SendEngagementLetterModal not fetching templates

**File to edit:** `frontend/src/components/engagements/SendEngagementLetterModal.tsx`

The useEffect that fetches templates depends on `[open, engagementType]`. When `engagementType` is null (which it is for "custom" type engagements after mapping), the dependency array changes cause React to skip or re-run the effect unexpectedly.

Remove `engagementType` from the dependency array of the template fetch useEffect so it only fires when `open` changes. The sorting by engagement type still happens inside the `.then()` callback using the current value of `engagementType` via closure — removing it from deps is safe here because we want to fetch ALL templates every time the modal opens, regardless of type.

Find the template fetch useEffect:
```tsx
}, [open, engagementType])
```

Change to:
```tsx
}, [open])
```

Also add a temporary console.log inside the useEffect immediately after `if (!open) return` to confirm it's firing:
```tsx
useEffect(() => {
  if (!open) return
  console.log('SendEngagementLetterModal: fetching templates, open=', open)
  setFetching(true)
  api.get('/esign/templates?limit=50')
  ...
}, [open])
```

Run TypeScript check after.