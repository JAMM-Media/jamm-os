# JAMM PX — Rich Text Template Editor (TipTap)

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.

---

## TASK 1 — Install TipTap packages

Run in the frontend directory:

```
cd frontend && npm install @tiptap/react @tiptap/starter-kit @tiptap/extension-placeholder
```

These three packages are the only additions needed:
- `@tiptap/react` — React bindings for TipTap
- `@tiptap/starter-kit` — includes bold, italic, headings, paragraphs, lists, undo/redo, history
- `@tiptap/extension-placeholder` — placeholder text when the editor is empty

---

## TASK 2 — Replace the textarea editor with a TipTap rich text editor in LetterTemplatesTab

**File to edit:** `frontend/src/components/settings/LetterTemplatesTab.tsx`

This is a significant rewrite of the editor view. The list view does NOT change — only the editor section changes.

### Step 1 — Update imports

Replace the existing import block at the top with:

```tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import api from '@/lib/api'
import { toast } from 'sonner'
```

### Step 2 — Add RichTextEditor sub-component

Add this component definition before the `LetterTemplatesTab` function. This is the self-contained editor component:

```tsx
interface RichTextEditorProps {
  content: string
  onChange: (html: string) => void
  onInsertVariable: (insertFn: (text: string) => void) => void
}

function RichTextEditor({ content, onChange, onInsertVariable }: RichTextEditorProps) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Placeholder.configure({
        placeholder: 'Start writing your engagement letter here...',
      }),
    ],
    content,
    onUpdate({ editor }) {
      onChange(editor.getHTML())
    },
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none min-h-[400px] px-6 py-6 text-[13px] leading-relaxed',
        style: 'font-family: Georgia, serif; color: #111;',
      },
    },
  })

  // Expose insert function to parent
  useEffect(() => {
    if (!editor) return
    onInsertVariable((text: string) => {
      editor.chain().focus().insertContent(text).run()
    })
  }, [editor, onInsertVariable])

  if (!editor) return null

  return (
    <div className="flex flex-col rounded-[6px] border border-surface-border dark:border-dark-border overflow-hidden bg-white">
      {/* Formatting toolbar */}
      <div className="flex items-center gap-0.5 px-2 py-1.5 border-b border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card flex-wrap">
        {/* Bold */}
        <button
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={`h-7 w-7 rounded flex items-center justify-center text-[13px] font-bold transition-colors ${
            editor.isActive('bold')
              ? 'bg-brand text-white'
              : 'text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page'
          }`}
          title="Bold (Ctrl+B)"
        >
          B
        </button>

        {/* Italic */}
        <button
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`h-7 w-7 rounded flex items-center justify-center text-[13px] italic transition-colors ${
            editor.isActive('italic')
              ? 'bg-brand text-white'
              : 'text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page'
          }`}
          title="Italic (Ctrl+I)"
        >
          I
        </button>

        <div className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1" />

        {/* Heading 2 */}
        <button
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          className={`h-7 px-2 rounded flex items-center justify-center text-[11px] font-medium transition-colors ${
            editor.isActive('heading', { level: 2 })
              ? 'bg-brand text-white'
              : 'text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page'
          }`}
          title="Heading"
        >
          H2
        </button>

        {/* Paragraph */}
        <button
          onClick={() => editor.chain().focus().setParagraph().run()}
          className={`h-7 px-2 rounded flex items-center justify-center text-[11px] font-medium transition-colors ${
            editor.isActive('paragraph')
              ? 'bg-brand text-white'
              : 'text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page'
          }`}
          title="Paragraph"
        >
          ¶
        </button>

        <div className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1" />

        {/* Bullet list */}
        <button
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={`h-7 px-2 rounded flex items-center justify-center text-[11px] transition-colors ${
            editor.isActive('bulletList')
              ? 'bg-brand text-white'
              : 'text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page'
          }`}
          title="Bullet list"
        >
          • List
        </button>

        <div className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1" />

        {/* Undo */}
        <button
          onClick={() => editor.chain().focus().undo().run()}
          disabled={!editor.can().undo()}
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
          title="Undo (Ctrl+Z)"
        >
          ↩ Undo
        </button>

        {/* Redo */}
        <button
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
          title="Redo (Ctrl+Shift+Z)"
        >
          ↪ Redo
        </button>

        <div className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1" />

        {/* Horizontal rule */}
        <button
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
          title="Horizontal line"
        >
          — Line
        </button>
      </div>

      {/* Editor content — always white background */}
      <div className="bg-white" style={{ minHeight: '400px' }}>
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
```

### Step 3 — Add insertFn ref to LetterTemplatesTab

Inside the `LetterTemplatesTab` function, add a ref to hold the insert function:

```tsx
import { useState, useEffect, useCallback, useRef } from 'react'
```

Update the import at the top (add `useRef`).

Inside the component body, add:
```tsx
const insertVariableFnRef = useRef<((text: string) => void) | null>(null)
```

### Step 4 — Update insertVariable function

Replace the existing `insertVariable` function with:

```tsx
function insertVariable(key: string) {
  const tag = `{{${key}}}`
  if (insertVariableFnRef.current) {
    insertVariableFnRef.current(tag)
  }
}
```

### Step 5 — Remove editPreview state and Preview button

The rich text editor IS the preview — what you see is what the client gets. Remove:
- `const [editPreview, setEditPreview] = useState(false)`
- The Preview/Edit toggle button from the editor header
- The `renderPreview` function
- The entire `{editPreview ? (...) : (...)}` conditional block
- The `editPreview` reset in `openNew`, `openEdit`, and `cancelEdit`

### Step 6 — Replace the textarea JSX with RichTextEditor

In the editor view JSX, replace the entire textarea section (the `{editPreview ? ... : ...}` block or just the textarea div if preview was already removed) with:

```tsx
{/* Variable insertion toolbar */}
<div className="flex flex-col gap-2">
  <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
    Insert Variable at Cursor
  </p>
  <div className="flex flex-wrap gap-1.5">
    {SUPPORTED_VARIABLES.map((v) => (
      <button
        key={v.key}
        onClick={() => insertVariable(v.key)}
        className="text-[11px] font-medium px-2 py-1 rounded-[4px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] hover:bg-[#D5D8DE] dark:hover:bg-[#444444] transition-colors font-mono"
      >
        {`{{${v.key}}}`}
      </button>
    ))}
  </div>
</div>

{/* Rich text editor */}
<div className="flex flex-col gap-1.5">
  <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
    Letter Body <span className="text-red-500">•</span>
  </label>
  <RichTextEditor
    content={editBody}
    onChange={setEditBody}
    onInsertVariable={(fn) => { insertVariableFnRef.current = fn }}
  />
  <p className="text-[11px] text-[#6B7280]">
    Format text using the toolbar above. Click any variable button to insert it at your cursor position.
    Use Ctrl+Z to undo, Ctrl+B for bold, Ctrl+I for italic.
  </p>
</div>
```

### Step 7 — Add TipTap CSS

TipTap requires a small amount of CSS for the editor to render correctly. Add this to `frontend/src/app/globals.css` at the end of the file:

```css
/* TipTap editor styles */
.ProseMirror {
  outline: none;
}

.ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  float: left;
  color: #9CA3AF;
  pointer-events: none;
  height: 0;
}

.ProseMirror p {
  margin-bottom: 0.75em;
}

.ProseMirror strong {
  font-weight: 600;
}

.ProseMirror h2 {
  font-size: 1.1em;
  font-weight: 600;
  margin-bottom: 0.5em;
  margin-top: 1em;
}

.ProseMirror ul {
  list-style-type: disc;
  padding-left: 1.5em;
  margin-bottom: 0.75em;
}

.ProseMirror hr {
  border: none;
  border-top: 1px solid #111;
  margin: 1em 0;
}
```

---

## EXECUTION ORDER

1. Task 1 — install npm packages (run in frontend/ directory)
2. Task 2, Steps 1-7 — rewrite LetterTemplatesTab.tsx
3. Task 2, Step 7 — add CSS to globals.css

After all tasks: report every file modified and confirm no TypeScript errors.