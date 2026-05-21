# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix Modal prop name in SendEngagementLetterModal

**File to edit:** `frontend/src/components/engagements/SendEngagementLetterModal.tsx`

Find:
```tsx
<Modal
  isOpen={open}
```

Replace with:
```tsx
<Modal
  open={open}
```

That is the only change. Run TypeScript check after.