# JAMM PX — Quick Fix

Read every instruction in this file before writing a single line of code.

---

## TASK 1 — Replace undo/redo text labels with icons, fix dark mode visibility

**File to edit:** `frontend/src/components/settings/LetterTemplatesTab.tsx`

### Step 1 — Add icon import

At the top of the file, add to the existing imports:
```tsx
import { Undo2, Redo2 } from 'lucide-react'
```

### Step 2 — Replace Undo button content

Find the Undo button. It currently shows `↩ Undo` as text. Replace the button content with the icon:
```tsx
<Undo2 className="h-3.5 w-3.5" />
```

Remove the text label entirely. The button should still have `title="Undo (Ctrl+Z)"`.

### Step 3 — Replace Redo button content

Find the Redo button. It currently shows `↪ Redo` as text. Replace with:
```tsx
<Redo2 className="h-3.5 w-3.5" />
```

Remove the text label. Keep `title="Redo (Ctrl+Shift+Z)"`.

### Step 4 — Fix dark mode text colors on ALL toolbar buttons

Find every instance of `text-[#374151]` in the toolbar buttons and add `dark:text-[#EDEEF0]` alongside it. This affects Bold, Italic, H2, Paragraph, Bullet list, Undo, Redo, and Horizontal rule buttons.

The inactive state class string currently reads something like:
```
text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page
```

Change to:
```
text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page
```

Apply to every toolbar button that has this pattern. Do not change the active state classes (those already use `bg-brand text-white`).

Run TypeScript check after.