# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Fix toolbar button visibility in dark mode

**File to edit:** `frontend/src/components/settings/LetterTemplatesTab.tsx`

In the `RichTextEditor` component, the formatting toolbar buttons use `text-[#374151]` for their inactive state — this is a dark gray that's invisible on dark backgrounds.

Find every instance of this pattern in the toolbar buttons:
```
text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page
```

Replace every instance with:
```
text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page
```

There are multiple buttons with this pattern — Bold, Italic, H2, Paragraph, Bullet list, Undo, Redo, Horizontal rule. Update all of them.

Also find the separator dividers between button groups:
```
className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1"
```
These are fine as-is.

Run TypeScript check after.