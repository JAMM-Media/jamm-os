# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Add pending_signature to BadgeVariant type

**File to edit:** `frontend/src/components/ui/StatusBadge.tsx`

Read the file first. Find the `BadgeVariant` type definition and add `'pending_signature'` to it.

Also find the variant config object and add an entry for `pending_signature` if one doesn't already exist. It should look like:
```typescript
pending_signature: { bg: '#DBEAFE', text: '#1E40AF', label: 'Pending Signature' },
```

Also in `frontend/src/app/documents/[id]/page.tsx`, the `StatusBadge` is receiving `doc.status` which TypeScript now complains about. Find that line and cast it:
```tsx
<StatusBadge variant={doc.status as BadgeVariant} />
```

Run TypeScript check after.