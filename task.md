# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix undo/redo icon color to match other toolbar buttons

**File to edit:** `frontend/src/components/settings/LetterTemplatesTab.tsx`

Find the Undo button and Redo button. They currently have a className that includes `text-[#374151]` but is missing `dark:text-[#EDEEF0]`. 

Find both buttons and update their className to match the other toolbar buttons exactly:

For the Undo button, find:
```tsx
className="h-7 w-7 rounded flex items-center justify-center text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
```

Replace with:
```tsx
className="h-7 w-7 rounded flex items-center justify-center text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
```

Apply the same change to the Redo button.

Run TypeScript check after.