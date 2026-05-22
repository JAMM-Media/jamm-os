# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix filename mapping in mapDocument

**File to edit:** `frontend/src/lib/api/documents.ts`

In the `mapDocument` function, find:
```typescript
name: String(raw.file_name ?? raw.name ?? ''),
```

Replace with:
```typescript
name: String(raw.filename ?? raw.file_name ?? raw.name ?? ''),
```

The backend returns `filename` not `file_name`. This one-character difference is why the Name column is blank on every document row.

Run TypeScript check after.