// frontend/src/components/templates/TaxOrganizerTemplates.tsx
'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { Pencil, Trash2, X, GripVertical, Plus, MoreVertical } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { cn } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

type QuestionType = 'text' | 'number' | 'boolean' | 'select' | 'textarea'

interface TaxOrganizerQuestion {
  id: string
  label: string
  type: QuestionType
  required?: boolean
  options?: string[]
}

interface TaxOrganizerSection {
  id: string
  title: string
  description?: string
  questions: TaxOrganizerQuestion[]
}

interface TaxOrganizerTemplate {
  id: string
  name: string
  organizer_type: string
  is_default: boolean
  is_active: boolean
  sections: TaxOrganizerSection[]
  created_at: string
  updated_at: string
}

const ORGANIZER_TYPE_LABELS: Record<string, string> = {
  individual: 'Individual',
  business: 'Business',
  rental: 'Rental',
  custom: 'Custom',
}

const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  text: 'Short answer',
  number: 'Number',
  boolean: 'Yes / No',
  select: 'Multiple choice',
  textarea: 'Long answer',
}

const ORGANIZER_TYPE_OPTIONS = [
  { value: 'individual', label: 'Individual' },
  { value: 'business', label: 'Business' },
  { value: 'rental', label: 'Rental' },
  { value: 'custom', label: 'Custom' },
]

function newQuestion(): TaxOrganizerQuestion {
  return { id: crypto.randomUUID(), label: '', type: 'text', required: false }
}

function newSection(): TaxOrganizerSection {
  return { id: crypto.randomUUID(), title: '', questions: [newQuestion()] }
}

// ── Question Row ──────────────────────────────────────────────────────────────

interface QuestionRowProps {
  question: TaxOrganizerQuestion
  onChange: (q: TaxOrganizerQuestion) => void
  onDelete: () => void
  dragHandleProps: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragOver: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
    onDragEnd: () => void
    className?: string
  }
  isDragTarget: boolean
}

function QuestionRow({ question, onChange, onDelete, dragHandleProps, isDragTarget }: QuestionRowProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-2 p-3 rounded-[6px] border transition-colors',
        isDragTarget
          ? 'border-dashed border-[#4A7FA5] bg-[#EBF5FF] dark:bg-[#1a2d3d]'
          : 'border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page',
      )}
      {...dragHandleProps}
    >
      <div className="flex items-center gap-2">
        <div className="cursor-grab text-[#9CA3AF] flex-shrink-0">
          <GripVertical className="h-4 w-4" />
        </div>
        <input
          type="text"
          value={question.label}
          onChange={(e) => onChange({ ...question, label: e.target.value })}
          placeholder="Question"
          className="flex-1 h-8 px-2 rounded-[4px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
        />
        <select
          value={question.type}
          onChange={(e) => onChange({ ...question, type: e.target.value as QuestionType, options: e.target.value === 'select' ? [''] : undefined })}
          className="h-8 px-2 rounded-[4px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-[#4A7FA5]"
        >
          {(Object.entries(QUESTION_TYPE_LABELS) as [QuestionType, string][]).map(([val, label]) => (
            <option key={val} value={val}>{label}</option>
          ))}
        </select>
        <button
          onClick={() => onChange({ ...question, required: !question.required })}
          className={cn(
            'h-6 px-2 rounded-full text-[10px] font-medium flex-shrink-0 transition-colors',
            question.required
              ? 'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300 border border-amber-300 dark:border-amber-600'
              : 'bg-[#F3F4F6] dark:bg-[#333] text-[#6B7280] border border-surface-border dark:border-dark-border',
          )}
        >
          Required
        </button>
        <button
          onClick={onDelete}
          className="h-7 w-7 flex items-center justify-center rounded text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Multiple choice options */}
      {question.type === 'select' && (
        <div className="ml-6 flex flex-col gap-1.5">
          {(question.options ?? []).map((opt, i) => (
            <div key={i} className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#9CA3AF] flex-shrink-0" />
              <input
                type="text"
                value={opt}
                onChange={(e) => {
                  const next = [...(question.options ?? [])]
                  next[i] = e.target.value
                  onChange({ ...question, options: next })
                }}
                placeholder={`Option ${i + 1}`}
                className="flex-1 h-7 px-2 rounded-[4px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
              />
              {(question.options ?? []).length > 1 && (
                <button
                  onClick={() => onChange({ ...question, options: (question.options ?? []).filter((_, j) => j !== i) })}
                  className="text-[#9CA3AF] hover:text-red-500 transition-colors"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          ))}
          <button
            onClick={() => onChange({ ...question, options: [...(question.options ?? []), ''] })}
            className="text-[11px] text-[#4A7FA5] hover:underline text-left"
          >
            + Add option
          </button>
        </div>
      )}
    </div>
  )
}

// ── Section Card ──────────────────────────────────────────────────────────────

interface SectionCardProps {
  section: TaxOrganizerSection
  onChange: (s: TaxOrganizerSection) => void
  onDelete: () => void
  onDuplicate: () => void
  dragHandleProps: {
    draggable: boolean
    onDragStart: (e: React.DragEvent) => void
    onDragOver: (e: React.DragEvent) => void
    onDrop: (e: React.DragEvent) => void
    onDragEnd: () => void
  }
  isDragTarget: boolean
  dragQuestionFromSection: string | null
  dragQuestionIndex: number | null
  onQuestionDragStart: (sectionId: string, qIdx: number) => void
  onQuestionDragOver: (e: React.DragEvent, sectionId: string, qIdx: number) => void
  onQuestionDrop: (e: React.DragEvent, sectionId: string, qIdx: number) => void
  onQuestionDragEnd: () => void
  dragTargetQuestion: { sectionId: string; qIdx: number } | null
}

function SectionCard({
  section, onChange, onDelete, onDuplicate,
  dragHandleProps, isDragTarget,
  dragQuestionFromSection, dragQuestionIndex,
  onQuestionDragStart, onQuestionDragOver, onQuestionDrop, onQuestionDragEnd,
  dragTargetQuestion,
}: SectionCardProps) {
  const [showDesc, setShowDesc] = useState(!!section.description)
  const [menuOpen, setMenuOpen] = useState(false)

  function updateQuestion(idx: number, q: TaxOrganizerQuestion) {
    const next = [...section.questions]
    next[idx] = q
    onChange({ ...section, questions: next })
  }

  function removeQuestion(idx: number) {
    onChange({ ...section, questions: section.questions.filter((_, i) => i !== idx) })
  }

  function addQuestion() {
    onChange({ ...section, questions: [...section.questions, newQuestion()] })
  }

  return (
    <div
      className={cn(
        'rounded-[8px] border transition-colors',
        isDragTarget
          ? 'border-dashed border-[#4A7FA5] bg-[#EBF5FF] dark:bg-[#1a2d3d]'
          : 'border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card',
      )}
      onDragOver={dragHandleProps.onDragOver}
      onDrop={dragHandleProps.onDrop}
    >
      {/* Section header */}
      <div className="flex items-start gap-2 p-4 pb-2">
        <div
          draggable={dragHandleProps.draggable}
          onDragStart={dragHandleProps.onDragStart}
          onDragEnd={dragHandleProps.onDragEnd}
          className="cursor-grab text-[#9CA3AF] mt-1 flex-shrink-0"
        >
          <GripVertical className="h-4 w-4" />
        </div>
        <div className="flex-1 flex flex-col gap-1.5">
          <input
            type="text"
            value={section.title}
            onChange={(e) => onChange({ ...section, title: e.target.value })}
            placeholder="Section title"
            className="w-full h-8 px-2 rounded-[4px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] font-medium text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5]"
          />
          {showDesc ? (
            <textarea
              value={section.description ?? ''}
              onChange={(e) => onChange({ ...section, description: e.target.value })}
              placeholder="Section description (optional)"
              rows={2}
              className="w-full px-2 py-1 rounded-[4px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-[#6B7280] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] resize-none"
            />
          ) : (
            <button
              onClick={() => setShowDesc(true)}
              className="text-[11px] text-[#9CA3AF] hover:text-[#6B7280] text-left"
            >
              + Add description
            </button>
          )}
        </div>
        <div className="relative flex-shrink-0">
          <button
            onClick={() => setMenuOpen((p) => !p)}
            className="h-7 w-7 flex items-center justify-center rounded text-[#9CA3AF] hover:text-brand hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
          >
            <MoreVertical className="h-4 w-4" />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-8 z-10 w-40 rounded-[6px] border border-surface-border dark:border-dark-border bg-white dark:bg-[#1E1E1E] shadow-lg py-1">
              <button
                onClick={() => { onDuplicate(); setMenuOpen(false) }}
                className="w-full text-left px-3 py-1.5 text-[12px] text-brand dark:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333]"
              >
                Duplicate section
              </button>
              <button
                onClick={() => { onDelete(); setMenuOpen(false) }}
                className="w-full text-left px-3 py-1.5 text-[12px] text-red-600 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20"
              >
                Delete section
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Questions */}
      <div className="px-4 pb-3 flex flex-col gap-2">
        {section.questions.map((q, qIdx) => {
          const isQTarget =
            dragTargetQuestion?.sectionId === section.id &&
            dragTargetQuestion?.qIdx === qIdx
          return (
            <QuestionRow
              key={q.id}
              question={q}
              onChange={(updated) => updateQuestion(qIdx, updated)}
              onDelete={() => removeQuestion(qIdx)}
              isDragTarget={isQTarget}
              dragHandleProps={{
                draggable: true,
                onDragStart: () => onQuestionDragStart(section.id, qIdx),
                onDragOver: (e) => onQuestionDragOver(e, section.id, qIdx),
                onDrop: (e) => onQuestionDrop(e, section.id, qIdx),
                onDragEnd: onQuestionDragEnd,
              }}
            />
          )
        })}
        <button
          onClick={addQuestion}
          className="text-[12px] text-[#4A7FA5] hover:underline text-left mt-1"
        >
          + Add Question
        </button>
      </div>
    </div>
  )
}

// ── Editor Modal ──────────────────────────────────────────────────────────────

interface EditorModalProps {
  template: TaxOrganizerTemplate | null
  onClose: () => void
  onSaved: () => void
}

function EditorModal({ template, onClose, onSaved }: EditorModalProps) {
  const isNew = template === null
  const [name, setName] = useState(template?.name ?? '')
  const [organizerType, setOrganizerType] = useState(template?.organizer_type ?? 'custom')
  const [sections, setSections] = useState<TaxOrganizerSection[]>(
    template?.sections ? JSON.parse(JSON.stringify(template.sections)) : [newSection()]
  )
  const [saving, setSaving] = useState(false)

  // Section drag state
  const dragSectionIdx = useRef<number | null>(null)
  const [dragTargetSection, setDragTargetSection] = useState<number | null>(null)

  // Question drag state
  const dragQuestion = useRef<{ sectionId: string; qIdx: number } | null>(null)
  const [dragTargetQuestion, setDragTargetQuestion] = useState<{ sectionId: string; qIdx: number } | null>(null)

  function updateSection(idx: number, s: TaxOrganizerSection) {
    setSections((prev) => { const n = [...prev]; n[idx] = s; return n })
  }

  function deleteSection(idx: number) {
    setSections((prev) => prev.filter((_, i) => i !== idx))
  }

  function duplicateSection(idx: number) {
    setSections((prev) => {
      const copy: TaxOrganizerSection = JSON.parse(JSON.stringify(prev[idx]))
      copy.id = crypto.randomUUID()
      copy.questions = copy.questions.map((q) => ({ ...q, id: crypto.randomUUID() }))
      const next = [...prev]
      next.splice(idx + 1, 0, copy)
      return next
    })
  }

  // Section drag handlers
  function onSectionDragStart(idx: number) {
    dragSectionIdx.current = idx
  }
  function onSectionDragOver(e: React.DragEvent, idx: number) {
    e.preventDefault()
    setDragTargetSection(idx)
  }
  function onSectionDrop(e: React.DragEvent, toIdx: number) {
    e.preventDefault()
    const from = dragSectionIdx.current
    if (from === null || from === toIdx) { setDragTargetSection(null); return }
    setSections((prev) => {
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(toIdx, 0, moved)
      return next
    })
    dragSectionIdx.current = null
    setDragTargetSection(null)
  }
  function onSectionDragEnd() {
    dragSectionIdx.current = null
    setDragTargetSection(null)
  }

  // Question drag handlers
  function onQuestionDragStart(sectionId: string, qIdx: number) {
    dragQuestion.current = { sectionId, qIdx }
  }
  function onQuestionDragOver(e: React.DragEvent, sectionId: string, qIdx: number) {
    e.preventDefault()
    setDragTargetQuestion({ sectionId, qIdx })
  }
  function onQuestionDrop(e: React.DragEvent, toSectionId: string, toQIdx: number) {
    e.preventDefault()
    const from = dragQuestion.current
    if (!from) { setDragTargetQuestion(null); return }
    setSections((prev) => {
      const next = prev.map((s) => ({ ...s, questions: [...s.questions] }))
      const fromSection = next.find((s) => s.id === from.sectionId)
      const toSection = next.find((s) => s.id === toSectionId)
      if (!fromSection || !toSection) return prev
      const [moved] = fromSection.questions.splice(from.qIdx, 1)
      if (from.sectionId === toSectionId) {
        const adjustedTo = toQIdx > from.qIdx ? toQIdx - 1 : toQIdx
        fromSection.questions.splice(adjustedTo, 0, moved)
      } else {
        toSection.questions.splice(toQIdx, 0, moved)
      }
      return next
    })
    dragQuestion.current = null
    setDragTargetQuestion(null)
  }
  function onQuestionDragEnd() {
    dragQuestion.current = null
    setDragTargetQuestion(null)
  }

  async function handleSave() {
    if (!name.trim()) { toast.error('Template name is required'); return }
    setSaving(true)
    const body = { name: name.trim(), organizer_type: organizerType, sections }
    try {
      if (isNew) {
        await api.post('/tax-organizers/templates', body)
        toast.success('Template created')
      } else {
        await api.patch(`/tax-organizers/templates/${template!.id}`, { sections, name: name.trim() })
        toast.success('Template saved')
      }
      onSaved()
      onClose()
    } catch {
      toast.error('Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        className="bg-surface-page dark:bg-dark-page rounded-xl shadow-2xl w-full max-w-3xl flex flex-col"
        style={{ minHeight: '80vh', maxHeight: '95vh' }}
      >
        {/* Modal header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-surface-border dark:border-dark-border flex-shrink-0">
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Template name"
            className="flex-1 text-[18px] font-medium text-brand dark:text-[#EDEEF0] bg-transparent border-none outline-none placeholder:text-[#9CA3AF]"
          />
          <select
            value={organizerType}
            onChange={(e) => setOrganizerType(e.target.value)}
            className="h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-[#4A7FA5]"
          >
            {ORGANIZER_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium disabled:opacity-60 transition-colors"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
          <button
            onClick={onClose}
            className="h-8 w-8 flex items-center justify-center rounded text-[#6B7280] hover:text-brand transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Sections */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">
          {sections.map((section, sIdx) => (
            <SectionCard
              key={section.id}
              section={section}
              onChange={(s) => updateSection(sIdx, s)}
              onDelete={() => deleteSection(sIdx)}
              onDuplicate={() => duplicateSection(sIdx)}
              isDragTarget={dragTargetSection === sIdx}
              dragHandleProps={{
                draggable: true,
                onDragStart: () => onSectionDragStart(sIdx),
                onDragOver: (e) => onSectionDragOver(e, sIdx),
                onDrop: (e) => onSectionDrop(e, sIdx),
                onDragEnd: onSectionDragEnd,
              }}
              dragQuestionFromSection={dragQuestion.current?.sectionId ?? null}
              dragQuestionIndex={dragQuestion.current?.qIdx ?? null}
              onQuestionDragStart={onQuestionDragStart}
              onQuestionDragOver={onQuestionDragOver}
              onQuestionDrop={onQuestionDrop}
              onQuestionDragEnd={onQuestionDragEnd}
              dragTargetQuestion={dragTargetQuestion}
            />
          ))}

          {/* Add Section button */}
          <button
            onClick={() => setSections((prev) => [...prev, newSection()])}
            className="w-full py-3 rounded-[8px] border-2 border-dashed border-[#D1D5DB] dark:border-[#444] text-[13px] text-[#6B7280] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
          >
            + Add Section
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function TaxOrganizerTemplates() {
  const { user } = useAuth()
  const isManager = user?.role === 'firm_owner' || user?.role === 'manager'

  const [allTemplates, setAllTemplates] = useState<TaxOrganizerTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [editorTemplate, setEditorTemplate] = useState<TaxOrganizerTemplate | null | undefined>(undefined)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [previewTemplate, setPreviewTemplate] = useState<TaxOrganizerTemplate | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.get('/tax-organizers/templates')
      setAllTemplates(res.data ?? [])
    } catch {
      toast.error('Failed to load tax organizer templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  const templates = allTemplates.filter((t) => t.is_active !== false)

  async function handleDelete(id: string) {
    try {
      await api.patch(`/tax-organizers/templates/${id}`, { is_active: false })
      setAllTemplates((prev) => prev.map((t) => t.id === id ? { ...t, is_active: false } : t))
      setDeleteConfirm(null)
      toast.success('Template deleted')
    } catch {
      toast.error('Failed to delete template')
    }
  }

  function totalQuestions(t: TaxOrganizerTemplate): number {
    return t.sections.reduce((sum, s) => sum + (s.questions?.length ?? 0), 0)
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">
            Tax Organizer Templates
          </h2>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Reusable templates for client tax organizers.
          </p>
        </div>
        {isManager && (
          <button
            onClick={() => setEditorTemplate(null)}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" /> New Template
          </button>
        )}
      </div>

      {/* Template list */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444] animate-pulse" />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2.5">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            No templates yet
          </p>
          {isManager && (
            <p className="text-[12px] text-[#6B7280]">
              Click &ldquo;New Template&rdquo; to create your first template.
            </p>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {templates.map((t) => (
            <div
              key={t.id}
              className="flex items-center gap-3 px-4 py-3 rounded-[8px] bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border"
            >
              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                    {t.name}
                  </span>
                  {t.is_default && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[#E5E7EB] dark:bg-[#333] text-[#6B7280]">
                      Default
                    </span>
                  )}
                  <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
                    {ORGANIZER_TYPE_LABELS[t.organizer_type] ?? t.organizer_type}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-0.5">
                  <span className="text-[11px] text-[#6B7280]">
                    {t.sections.length} section{t.sections.length !== 1 ? 's' : ''}
                  </span>
                  <span className="text-[11px] text-[#9CA3AF]">·</span>
                  <span className="text-[11px] text-[#6B7280]">
                    {totalQuestions(t)} question{totalQuestions(t) !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>

              {/* Actions */}
              {isManager && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    onClick={() => setPreviewTemplate(t)}
                    className="h-7 px-2.5 rounded-[6px] border border-surface-border dark:border-dark-border text-[11px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
                  >
                    Preview
                  </button>
                  <button
                    onClick={() => setEditorTemplate(t)}
                    className="p-1.5 rounded text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
                    title="Edit template"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
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
                      className="p-1.5 rounded text-[#6B7280] hover:text-red-500 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20 transition-colors"
                      title="Delete template"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Editor modal — undefined = closed, null = new, template = edit */}
      {editorTemplate !== undefined && (
        <EditorModal
          template={editorTemplate}
          onClose={() => setEditorTemplate(undefined)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Preview modal */}
      {previewTemplate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}
          onClick={() => setPreviewTemplate(null)}
        >
          <div
            className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border dark:border-dark-border w-full max-w-2xl max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-surface-border dark:border-dark-border flex-shrink-0">
              <div>
                <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">
                  {previewTemplate.name}
                </p>
                <p className="text-[11px] text-[#6B7280] mt-0.5">
                  Client view -- read only
                </p>
              </div>
              <button
                onClick={() => setPreviewTemplate(null)}
                className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
              >
                <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Scrollable content */}
            <div className="overflow-y-auto flex-1 px-5 py-4 flex flex-col gap-6">
              {(previewTemplate.sections ?? []).map((section: TaxOrganizerSection, si: number) => (
                <div key={si} className="flex flex-col gap-3">
                  <div>
                    <p className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0]">
                      {section.title}
                    </p>
                    {section.description && (
                      <p className="text-[12px] text-[#6B7280] mt-0.5">
                        {section.description}
                      </p>
                    )}
                  </div>
                  {(section.questions ?? []).map((q: TaxOrganizerQuestion, qi: number) => (
                    <div key={qi} className="flex flex-col gap-1">
                      <label className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                        {q.label}
                        {q.required && (
                          <span className="text-red-500 ml-1">*</span>
                        )}
                      </label>
                      {q.type === 'boolean' && (
                        <div className="flex gap-3">
                          <span className="text-[12px] px-3 py-1 rounded-[6px] border border-surface-border dark:border-dark-border text-[#6B7280]">
                            Yes
                          </span>
                          <span className="text-[12px] px-3 py-1 rounded-[6px] border border-surface-border dark:border-dark-border text-[#6B7280]">
                            No
                          </span>
                        </div>
                      )}
                      {q.type === 'select' && q.options && (
                        <div className="flex flex-wrap gap-2">
                          {q.options.map((opt: string, oi: number) => (
                            <span key={oi} className="text-[12px] px-3 py-1 rounded-[6px] border border-surface-border dark:border-dark-border text-[#6B7280]">
                              {opt}
                            </span>
                          ))}
                        </div>
                      )}
                      {(q.type === 'text' || q.type === 'number') && (
                        <div className="h-8 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page" />
                      )}
                      {q.type === 'textarea' && (
                        <div className="h-16 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page" />
                      )}
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Modal footer */}
            <div className="px-5 py-3 border-t border-surface-border dark:border-dark-border flex-shrink-0 flex justify-end">
              <button
                onClick={() => setPreviewTemplate(null)}
                className="h-8 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
