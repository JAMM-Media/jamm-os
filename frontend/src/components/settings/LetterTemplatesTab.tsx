// frontend/src/components/settings/LetterTemplatesTab.tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import api from '@/lib/api'
import { toast } from 'sonner'

interface LetterTemplate {
  id: string
  name: string
  engagement_type: string | null
  body_html: string
  variable_fields: string[]
  is_active: boolean
  created_at: string
  updated_at: string
}

// All supported merge variables from letter_renderer.py
const SUPPORTED_VARIABLES = [
  { key: 'client_name', label: 'Client Name' },
  { key: 'client_email', label: 'Client Email' },
  { key: 'firm_name', label: 'Firm Name' },
  { key: 'firm_owner_name', label: 'Firm Owner Name' },
  { key: 'engagement_name', label: 'Engagement Name' },
  { key: 'engagement_type', label: 'Engagement Type' },
  { key: 'fee_amount', label: 'Fee Amount' },
  { key: 'engagement_date', label: 'Engagement Date' },
  { key: 'due_date', label: 'Due Date' },
]

const ENGAGEMENT_TYPE_OPTIONS = [
  { value: '', label: 'All engagement types (generic)' },
  { value: 'tax_return_1040', label: '1040 — Individual' },
  { value: 'tax_return_1120', label: '1120 — C-Corporation' },
  { value: 'tax_return_1120s', label: '1120-S — S-Corporation' },
  { value: 'tax_return_1065', label: '1065 — Partnership' },
  { value: 'tax_return_1041', label: '1041 — Trust / Estate Income' },
  { value: 'tax_return_706', label: '706 — Estate Tax' },
  { value: 'amended_return_1040x', label: '1040-X — Amended Return' },
  { value: 'extension_4868', label: '4868 — Individual Extension' },
  { value: 'extension_7004', label: '7004 — Business Extension' },
  { value: 'extension_8868', label: '8868 — Exempt Org Extension' },
  { value: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
  { value: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
  { value: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
  { value: 'tax_planning_advisory', label: 'Tax Planning / Advisory' },
  { value: 'audit_representation', label: 'Audit Representation' },
  { value: 'custom', label: 'Other / Custom' },
]

// Extract all {{variable}} keys used in the body_html
function extractVariableFields(html: string): string[] {
  const matches = html.matchAll(/\{\{(\w+)\}\}/g)
  return [...new Set([...matches].map((m) => m[1]))]
}

// Format engagement type for display
function formatEngType(val: string | null): string {
  if (!val) return 'Generic'
  const found = ENGAGEMENT_TYPE_OPTIONS.find((o) => o.value === val)
  return found ? found.label : val
}

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
              : 'text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page'
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
              : 'text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page'
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
              : 'text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page'
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
              : 'text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page'
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
              : 'text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page'
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
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
          title="Undo (Ctrl+Z)"
        >
          ↩ Undo
        </button>

        {/* Redo */}
        <button
          onClick={() => editor.chain().focus().redo().run()}
          disabled={!editor.can().redo()}
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page disabled:opacity-30 transition-colors"
          title="Redo (Ctrl+Shift+Z)"
        >
          ↪ Redo
        </button>

        <div className="w-px h-4 bg-surface-border dark:bg-dark-border mx-1" />

        {/* Horizontal rule */}
        <button
          onClick={() => editor.chain().focus().setHorizontalRule().run()}
          className="h-7 px-2 rounded flex items-center justify-center text-[11px] text-[#374151] dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
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

export default function LetterTemplatesTab() {
  const [templates, setTemplates] = useState<LetterTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState<LetterTemplate | null>(null)
  const [isNew, setIsNew] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  // Editor state
  const [editName, setEditName] = useState('')
  const [editType, setEditType] = useState('')
  const [editBody, setEditBody] = useState('')
  const [saving, setSaving] = useState(false)
  const insertVariableFnRef = useRef<((text: string) => void) | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/esign/templates?limit=50')
      setTemplates(res.data?.items ?? [])
    } catch {
      toast.error('Failed to load templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  function openNew() {
    setIsNew(true)
    setEditing(null)
    setEditName('')
    setEditType('')
    setEditBody('')
  }

  function openEdit(t: LetterTemplate) {
    setIsNew(false)
    setEditing(t)
    setEditName(t.name)
    setEditType(t.engagement_type ?? '')
    setEditBody(t.body_html)
  }

  function cancelEdit() {
    setEditing(null)
    setIsNew(false)
  }

  function insertVariable(key: string) {
    const tag = `{{${key}}}`
    if (insertVariableFnRef.current) {
      insertVariableFnRef.current(tag)
    }
  }

  async function handleSave() {
    if (!editName.trim()) { toast.error('Template name is required'); return }
    if (!editBody.trim()) { toast.error('Template body is required'); return }

    const variable_fields = extractVariableFields(editBody)
    setSaving(true)
    try {
      if (isNew) {
        await api.post('/esign/templates', {
          name: editName.trim(),
          engagement_type: editType || null,
          body_html: editBody,
          variable_fields,
          is_active: true,
        })
        toast.success('Template created')
      } else if (editing) {
        await api.patch(`/esign/templates/${editing.id}`, {
          name: editName.trim(),
          engagement_type: editType || null,
          body_html: editBody,
          variable_fields,
        })
        toast.success('Template saved')
      }
      cancelEdit()
      fetchTemplates()
    } catch {
      toast.error('Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  async function handleToggleActive(t: LetterTemplate) {
    try {
      await api.patch(`/esign/templates/${t.id}`, { is_active: !t.is_active })
      setTemplates((prev) => prev.map((x) => x.id === t.id ? { ...x, is_active: !x.is_active } : x))
    } catch {
      toast.error('Failed to update template')
    }
  }

  async function handleDelete(id: string) {
    try {
      await api.delete(`/esign/templates/${id}`)
      setTemplates((prev) => prev.filter((t) => t.id !== id))
      setDeleteConfirm(null)
      toast.success('Template deleted')
    } catch {
      toast.error('Failed to delete template')
    }
  }

  // ─── EDITOR VIEW ───────────────────────────────────────────────────────────
  if (editing !== null || isNew) {
    return (
      <div className="flex flex-col gap-4 max-w-4xl">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">
              {isNew ? 'New Template' : 'Edit Template'}
            </h2>
            <p className="text-[12px] text-[#6B7280] mt-0.5">
              Use {'{{variable}}'} tags to insert dynamic content. Click a variable button to insert at cursor.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={cancelEdit}
              className="h-8 px-3 rounded-[6px] border border-surface-border dark:border-dark-border text-[12px] font-medium text-[#6B7280] hover:text-brand transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium disabled:opacity-50 transition-colors"
            >
              {saving ? 'Saving...' : 'Save Template'}
            </button>
          </div>
        </div>

        {/* Template name + type */}
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
              Template Name <span className="text-red-500">•</span>
            </label>
            <input
              value={editName}
              onChange={(e) => setEditName(e.target.value)}
              placeholder="e.g. Individual Tax Return Engagement Letter"
              className="h-9 px-3 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">
              Engagement Type
            </label>
            <select
              value={editType}
              onChange={(e) => setEditType(e.target.value)}
              className="h-9 px-3 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-[#4A7FA5] cursor-pointer"
            >
              {ENGAGEMENT_TYPE_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        </div>

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
      </div>
    )
  }

  // ─── LIST VIEW ─────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Letter Templates</h2>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Manage your engagement letter templates. Templates are used to generate PDFs for client signature.
          </p>
        </div>
        <button
          onClick={openNew}
          className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
        >
          + New Template
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          {[1,2,3,4].map((i) => (
            <div key={i} className="h-16 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2.5">
          <div className="w-10 h-10 rounded-[8px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card flex items-center justify-center">
            <svg width="18" height="18" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" className="text-[#6B7280]">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
            </svg>
          </div>
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No templates yet</p>
          <p className="text-[12px] text-[#6B7280]">Create your first engagement letter template.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border"
            >
              {/* Active dot */}
              <div className={`w-2 h-2 rounded-full flex-shrink-0 ${t.is_active ? 'bg-[#10B981]' : 'bg-[#C8CDD6]'}`} />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] truncate">{t.name}</p>
                <p className="text-[11px] text-[#6B7280] mt-0.5">{formatEngType(t.engagement_type)}</p>
              </div>

              {/* Variables used */}
              <div className="hidden sm:flex items-center gap-1 flex-shrink-0">
                {t.variable_fields.slice(0, 3).map((v) => (
                  <span key={v} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-surface-page dark:bg-dark-page text-[#6B7280] border border-surface-border dark:border-dark-border">
                    {`{{${v}}}`}
                  </span>
                ))}
                {t.variable_fields.length > 3 && (
                  <span className="text-[10px] text-[#6B7280]">+{t.variable_fields.length - 3}</span>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 flex-shrink-0">
                {/* Active toggle */}
                <button
                  onClick={() => handleToggleActive(t)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                    t.is_active ? 'bg-brand dark:bg-brand-btn' : 'bg-[#C8CDD6] dark:bg-[#484848]'
                  }`}
                >
                  <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                    t.is_active ? 'translate-x-4' : 'translate-x-0.5'
                  }`} />
                </button>

                {/* Edit */}
                <button
                  onClick={() => openEdit(t)}
                  className="h-7 px-2.5 rounded-[6px] border border-surface-border dark:border-dark-border text-[11px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                >
                  Edit
                </button>

                {/* Delete */}
                {deleteConfirm === t.id ? (
                  <div className="flex items-center gap-1">
                    <span className="text-[11px] text-[#6B7280]">Delete?</span>
                    <button
                      onClick={() => handleDelete(t.id)}
                      className="h-7 px-2 rounded-[4px] bg-[#991B1B] text-white text-[11px] font-medium"
                    >
                      Yes
                    </button>
                    <button
                      onClick={() => setDeleteConfirm(null)}
                      className="h-7 px-2 rounded-[4px] border border-surface-border dark:border-dark-border text-[11px] text-[#6B7280]"
                    >
                      No
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setDeleteConfirm(t.id)}
                    className="h-7 w-7 rounded-[6px] border border-surface-border dark:border-dark-border text-[#6B7280] hover:text-[#991B1B] hover:border-[#991B1B] flex items-center justify-center transition-colors"
                  >
                    <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
