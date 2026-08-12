// path: frontend/src/app/(dashboard)/templates/page.tsx
'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { onConciergeAction, setFormDirty } from '@/lib/events/conciergeEvents'
import { toast } from 'sonner'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import { clientsApi } from '@/lib/api'
import api from '@/lib/api'
import { formatEngagementType } from '@/lib/utils'
import { Pencil, Trash2, LayoutTemplate, X, Plus, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import LetterTemplatesTab from '@/components/settings/LetterTemplatesTab'
import TaxOrganizerTemplates from '@/components/templates/TaxOrganizerTemplates'
import DeletedTemplates from '@/components/templates/DeletedTemplates'
import QcChecklistTemplatesTab from '@/components/templates/QcChecklistTemplatesTab'

// ---- Types ----

interface TaskTemplateItem {
  title: string
  description: string
  order: number
}

interface Template {
  id: string
  name: string
  description: string | null
  engagement_type: string | null
  estimated_hours: number | null
  task_templates: TaskTemplateItem[]
  document_checklist: string[]
  notes: string | null
  is_active: boolean
  use_count: number
  is_recurring: boolean
  recurrence_cadence: string | null
  recurrence_day: number | null
  recurrence_month: number | null
  recurrence_advance_days: number | null
  last_spawned_at: string | null
  created_at: string
  updated_at: string
}

function mapTemplate(raw: Record<string, unknown>): Template {
  return {
    id: String(raw.id),
    name: String(raw.name ?? ''),
    description: raw.description ? String(raw.description) : null,
    engagement_type: raw.engagement_type ? String(raw.engagement_type) : null,
    estimated_hours: raw.estimated_hours != null ? Number(raw.estimated_hours) : null,
    task_templates: Array.isArray(raw.task_templates) ? (raw.task_templates as TaskTemplateItem[]) : [],
    document_checklist: Array.isArray(raw.document_checklist) ? (raw.document_checklist as string[]) : [],
    notes: raw.notes ? String(raw.notes) : null,
    is_active: Boolean(raw.is_active ?? true),
    use_count: Number(raw.use_count ?? 0),
    is_recurring: Boolean(raw.is_recurring ?? false),
    recurrence_cadence: raw.recurrence_cadence ? String(raw.recurrence_cadence) : null,
    recurrence_day: raw.recurrence_day != null ? Number(raw.recurrence_day) : null,
    recurrence_month: raw.recurrence_month != null ? Number(raw.recurrence_month) : null,
    recurrence_advance_days: raw.recurrence_advance_days != null ? Number(raw.recurrence_advance_days) : 14,
    last_spawned_at: raw.last_spawned_at ? String(raw.last_spawned_at) : null,
    created_at: String(raw.created_at ?? ''),
    updated_at: String(raw.updated_at ?? ''),
  }
}

const ENGAGEMENT_TYPES = [
  { value: 'tax_return_1040', label: 'Tax Return — 1040' },
  { value: 'tax_return_1120', label: 'Tax Return — 1120' },
  { value: 'tax_return_1120s', label: 'Tax Return — 1120-S' },
  { value: 'tax_return_1065', label: 'Tax Return — 1065' },
  { value: 'tax_return_1041', label: 'Tax Return — 1041' },
  { value: 'tax_return_706', label: 'Tax Return — 706' },
  { value: 'amended_return_1040x', label: 'Amended — 1040-X' },
  { value: 'extension_4868', label: 'Extension — 4868' },
  { value: 'extension_7004', label: 'Extension — 7004' },
  { value: 'extension_8868', label: 'Extension — 8868' },
  { value: 'payroll_tax_941', label: 'Payroll — 941' },
  { value: 'tax_planning_advisory', label: 'Tax Planning Advisory' },
  { value: 'bookkeeping_monthly', label: 'Bookkeeping — Monthly' },
  { value: 'bookkeeping_quarterly', label: 'Bookkeeping — Quarterly' },
  { value: 'audit_representation', label: 'Audit Representation' },
  { value: 'other_advisory', label: 'Other Advisory' },
  { value: 'custom', label: 'Custom' },
]

// ---- Create/Edit Modal ----

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

interface TemplateFormData {
  name: string
  description: string
  engagement_type: string
  estimated_hours: string
  task_templates: { title: string; description: string }[]
  document_checklist: string[]
  notes: string
  is_recurring: boolean
  recurrence_cadence: string
  recurrence_day: string
  recurrence_month: string
  recurrence_advance_days: string
}

function emptyForm(): TemplateFormData {
  return {
    name: '',
    description: '',
    engagement_type: '',
    estimated_hours: '',
    task_templates: [],
    document_checklist: [],
    notes: '',
    is_recurring: false,
    recurrence_cadence: '',
    recurrence_day: '',
    recurrence_month: '',
    recurrence_advance_days: '14',
  }
}

function templateToForm(t: Template): TemplateFormData {
  return {
    name: t.name,
    description: t.description ?? '',
    engagement_type: t.engagement_type ?? '',
    estimated_hours: t.estimated_hours != null ? String(t.estimated_hours) : '',
    task_templates: t.task_templates.map((tt) => ({ title: tt.title, description: tt.description ?? '' })),
    document_checklist: [...t.document_checklist],
    notes: t.notes ?? '',
    is_recurring: t.is_recurring,
    recurrence_cadence: t.recurrence_cadence ?? '',
    recurrence_day: t.recurrence_day != null ? String(t.recurrence_day) : '',
    recurrence_month: t.recurrence_month != null ? String(t.recurrence_month) : '',
    recurrence_advance_days: t.recurrence_advance_days != null ? String(t.recurrence_advance_days) : '14',
  }
}

interface TemplateModalProps {
  editTemplate: Template | null
  onClose: () => void
  onSaved: () => void
}

function TemplateModal({ editTemplate, onClose, onSaved }: TemplateModalProps) {
  const [form, setForm] = useState<TemplateFormData>(
    editTemplate ? templateToForm(editTemplate) : emptyForm()
  )
  const [saving, setSaving] = useState(false)

  function setField<K extends keyof TemplateFormData>(key: K, value: TemplateFormData[K]) {
    setFormDirty(true)
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function addTask() {
    setField('task_templates', [...form.task_templates, { title: '', description: '' }])
  }

  function updateTask(idx: number, field: 'title' | 'description', value: string) {
    const next = [...form.task_templates]
    next[idx] = { ...next[idx], [field]: value }
    setField('task_templates', next)
  }

  function removeTask(idx: number) {
    setField('task_templates', form.task_templates.filter((_, i) => i !== idx))
  }

  function addDoc() {
    setField('document_checklist', [...form.document_checklist, ''])
  }

  function updateDoc(idx: number, value: string) {
    const next = [...form.document_checklist]
    next[idx] = value
    setField('document_checklist', next)
  }

  function removeDoc(idx: number) {
    setField('document_checklist', form.document_checklist.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (!form.name.trim()) {
      toast.error('Template name is required')
      return
    }
    setSaving(true)
    const body = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      engagement_type: form.engagement_type || null,
      estimated_hours: form.estimated_hours ? Number(form.estimated_hours) : null,
      task_templates: form.task_templates
        .filter((t) => t.title.trim())
        .map((t, i) => ({ title: t.title.trim(), description: t.description.trim() || null, order: i })),
      document_checklist: form.document_checklist.filter((d) => d.trim()),
      notes: form.notes.trim() || null,
      is_recurring: form.is_recurring,
      recurrence_cadence: form.is_recurring ? form.recurrence_cadence || null : null,
      recurrence_day: form.is_recurring && form.recurrence_day ? Number(form.recurrence_day) : null,
      recurrence_month: form.is_recurring && form.recurrence_cadence === 'annually' && form.recurrence_month ? Number(form.recurrence_month) : null,
      recurrence_advance_days: form.is_recurring && form.recurrence_advance_days ? Number(form.recurrence_advance_days) : null,
    }
    try {
      if (editTemplate) {
        await api.patch(`/api/v1/engagement-templates/${editTemplate.id}`, body)
        toast.success('Template updated')
      } else {
        await api.post('/api/v1/engagement-templates/', body)
        toast.success('Template created')
      }
      setFormDirty(false)
      onSaved()
      onClose()
    } catch {
      toast.error('Failed to save template')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E5E7EB] dark:border-[#333]">
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">
            {editTemplate ? 'Edit Template' : 'New Template'}
          </h2>
          <button onClick={() => { setFormDirty(false); onClose() }} className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Name */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Template name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setField('name', e.target.value)}
              placeholder="e.g. Individual Tax Return — 1040"
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Description
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setField('description', e.target.value)}
              rows={2}
              placeholder="Brief description of this template..."
              className="w-full px-3 py-2 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light resize-none"
            />
          </div>

          {/* Engagement type */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Engagement type
            </label>
            <select
              value={form.engagement_type}
              onChange={(e) => setField('engagement_type', e.target.value)}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light"
            >
              <option value="">— None —</option>
              {ENGAGEMENT_TYPES.map((et) => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </select>
          </div>

          {/* Estimated hours */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Estimated hours
            </label>
            <input
              type="number"
              min="0"
              step="0.5"
              value={form.estimated_hours}
              onChange={(e) => setField('estimated_hours', e.target.value)}
              placeholder="e.g. 4.5"
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          {/* Default tasks */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Default Tasks
              </label>
              <button
                type="button"
                onClick={addTask}
                className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
              >
                <Plus className="h-3 w-3" /> Add Task
              </button>
            </div>
            <div className="space-y-2">
              {form.task_templates.map((task, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={task.title}
                    onChange={(e) => updateTask(idx, 'title', e.target.value)}
                    placeholder="Task title"
                    className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <button
                    type="button"
                    onClick={() => removeTask(idx)}
                    className="text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {form.task_templates.length === 0 && (
                <p className="text-[11px] text-[#9CA3AF]">No tasks yet. Click &ldquo;Add Task&rdquo; to add one.</p>
              )}
            </div>
          </div>

          {/* Document checklist */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Document Checklist
              </label>
              <button
                type="button"
                onClick={addDoc}
                className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
              >
                <Plus className="h-3 w-3" /> Add Document
              </button>
            </div>
            <div className="space-y-2">
              {form.document_checklist.map((doc, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={doc}
                    onChange={(e) => updateDoc(idx, e.target.value)}
                    placeholder='e.g. W-2, 1099-INT, Prior year return'
                    className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <button
                    type="button"
                    onClick={() => removeDoc(idx)}
                    className="text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {form.document_checklist.length === 0 && (
                <p className="text-[11px] text-[#9CA3AF]">No documents yet. Click &ldquo;Add Document&rdquo; to add one.</p>
              )}
            </div>
          </div>

          {/* Internal notes */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Internal notes
            </label>
            <textarea
              value={form.notes}
              onChange={(e) => setField('notes', e.target.value)}
              rows={2}
              placeholder="Notes visible to staff when using this template..."
              className="w-full px-3 py-2 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light resize-none"
            />
            <p className="text-[11px] text-[#9CA3AF] mt-1">Only visible to staff, not clients</p>
          </div>

          {/* Repeat section */}
          <div className="border-t border-[#E5E7EB] dark:border-[#333] pt-4">
            <div className="flex items-center justify-between">
              <span className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Repeat this template on a schedule
              </span>
              <button
                type="button"
                onClick={() => setField('is_recurring', !form.is_recurring)}
                className={cn(
                  'relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none',
                  form.is_recurring ? 'bg-brand dark:bg-brand-btn' : 'bg-[#D1D5DB] dark:bg-[#555]',
                )}
                role="switch"
                aria-checked={form.is_recurring}
              >
                <span
                  className={cn(
                    'pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200',
                    form.is_recurring ? 'translate-x-4' : 'translate-x-0',
                  )}
                />
              </button>
            </div>

            {form.is_recurring && (
              <div className="mt-4 space-y-3">
                {/* Cadence */}
                <div>
                  <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
                    Cadence <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={form.recurrence_cadence}
                    onChange={(e) => setField('recurrence_cadence', e.target.value)}
                    className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light"
                  >
                    <option value="">— Select cadence —</option>
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly</option>
                    <option value="annually">Annually</option>
                  </select>
                </div>

                {/* Day of month */}
                <div>
                  <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
                    Create on day <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="28"
                    value={form.recurrence_day}
                    onChange={(e) => setField('recurrence_day', e.target.value)}
                    placeholder="e.g. 1"
                    className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <p className="text-[11px] text-[#9CA3AF] mt-0.5">We cap at day 28 to avoid month-end issues.</p>
                </div>

                {/* Month of year — only for annually */}
                {form.recurrence_cadence === 'annually' && (
                  <div>
                    <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
                      Month <span className="text-red-500">*</span>
                    </label>
                    <select
                      value={form.recurrence_month}
                      onChange={(e) => setField('recurrence_month', e.target.value)}
                      className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light"
                    >
                      <option value="">— Select month —</option>
                      {MONTH_NAMES.map((m, i) => (
                        <option key={i + 1} value={String(i + 1)}>{m}</option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Advance days */}
                <div>
                  <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
                    Create this many days before the due date
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={form.recurrence_advance_days}
                    onChange={(e) => setField('recurrence_advance_days', e.target.value)}
                    className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <p className="text-[11px] text-[#9CA3AF] mt-0.5">Leave at 14 to give staff two weeks of lead time.</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-[#E5E7EB] dark:border-[#333]">
          <button
            onClick={onClose}
            className="h-8 px-4 text-[12px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-8 px-4 rounded-md bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity flex items-center gap-1.5"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {editTemplate ? 'Save Changes' : 'Create Template'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---- Use Template Modal ----

interface UseTemplateModalProps {
  template: Template
  onClose: () => void
}

interface Client {
  id: string
  name: string
}

function UseTemplateModal({ template, onClose }: UseTemplateModalProps) {
  const router = useRouter()
  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
  const clients: Client[] = (clientsData?.items ?? []).map((c) => ({ id: c.id, name: c.name }))

  const [clientId, setClientId] = useState('')
  const [clientSearch, setClientSearch] = useState('')
  const [engagementName, setEngagementName] = useState(template.name)
  const [assignedStaffId, setAssignedStaffId] = useState('')
  const [taxYear, setTaxYear] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [done, setDone] = useState<{ engagementId: string } | null>(null)

  const filteredClients = clients.filter((c) =>
    c.name.toLowerCase().includes(clientSearch.toLowerCase())
  )

  async function handleCreate() {
    if (!clientId) {
      toast.error('Please select a client')
      return
    }
    setSubmitting(true)
    try {
      const { data } = await api.post(`/api/v1/engagement-templates/${template.id}/use`, {
        client_id: clientId,
        engagement_name: engagementName.trim() || null,
        assigned_staff_id: assignedStaffId || null,
        tax_year: taxYear ? Number(taxYear) : null,
      })
      setDone({ engagementId: String(data.engagement_id) })
      toast.success('Engagement created successfully')
    } catch {
      toast.error('Failed to create engagement')
    } finally {
      setSubmitting(false)
    }
  }

  if (done) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
        <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-md p-6 flex flex-col items-center gap-4">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-green-100 dark:bg-green-900/30">
            <span className="text-2xl">✓</span>
          </div>
          <p className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Engagement created successfully</p>
          <div className="flex gap-3">
            <button
              onClick={() => router.push(`/engagements/${done.engagementId}`)}
              className="h-9 px-4 rounded-md bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
            >
              View Engagement
            </button>
            <button
              onClick={onClose}
              className="h-9 px-4 rounded-md border border-[#D1D5DB] dark:border-[#444] text-[13px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E5E7EB] dark:border-[#333]">
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">Use Template</h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div className="bg-surface-card dark:bg-[#252525] rounded-lg p-4 space-y-2">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{template.name}</p>
            {template.description && (
              <p className="text-[12px] text-[#6B7280]">{template.description}</p>
            )}
            {template.engagement_type && (
              <span className="inline-block px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-[11px] text-blue-700 dark:text-blue-300">
                {formatEngagementType(template.engagement_type)}
              </span>
            )}
            {template.task_templates.length > 0 && (
              <div className="mt-2">
                <p className="text-[11px] font-medium text-[#6B7280] mb-1">Tasks that will be created:</p>
                <ul className="space-y-0.5">
                  {template.task_templates.map((t, i) => (
                    <li key={i} className="text-[11px] text-[#374151] dark:text-[#9CA3AF] flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[#9CA3AF] flex-shrink-0" />
                      {t.title}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {template.document_checklist.length > 0 && (
              <div className="mt-2">
                <p className="text-[11px] font-medium text-[#6B7280] mb-1">Documents that will be requested:</p>
                <ul className="space-y-0.5">
                  {template.document_checklist.map((d, i) => (
                    <li key={i} className="text-[11px] text-[#374151] dark:text-[#9CA3AF] flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[#9CA3AF] flex-shrink-0" />
                      {d}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Client <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={clientSearch}
              onChange={(e) => { setClientSearch(e.target.value); setClientId('') }}
              placeholder="Search clients..."
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light mb-1"
            />
            {clientSearch && !clientId && (
              <div className="border border-[#D1D5DB] dark:border-[#444] rounded-md max-h-40 overflow-y-auto">
                {filteredClients.length === 0 ? (
                  <p className="px-3 py-2 text-[12px] text-[#9CA3AF]">No clients found</p>
                ) : (
                  filteredClients.map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => { setClientId(c.id); setClientSearch(c.name) }}
                      className="w-full text-left px-3 py-2 text-[12px] text-[#374151] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
                    >
                      {c.name}
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Engagement name
            </label>
            <input
              type="text"
              value={engagementName}
              onChange={(e) => setEngagementName(e.target.value)}
              placeholder={template.name}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Tax year
            </label>
            <input
              type="number"
              value={taxYear}
              onChange={(e) => setTaxYear(e.target.value)}
              placeholder={String(new Date().getFullYear())}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 px-5 py-4 border-t border-[#E5E7EB] dark:border-[#333]">
          <button
            onClick={onClose}
            className="h-8 px-4 text-[12px] font-medium text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={submitting || !clientId}
            className="h-8 px-4 rounded-md bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 disabled:opacity-60 transition-opacity flex items-center gap-1.5"
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create Engagement
          </button>
        </div>
      </div>
    </div>
  )
}

// ---- Template Card ----

interface TemplateCardProps {
  template: Template
  isManager: boolean
  onEdit: () => void
  onDelete: () => void
  onUse: () => void
}

function recurringLabel(template: Template): string | null {
  if (!template.is_recurring || !template.recurrence_cadence) return null
  const day = template.recurrence_day ?? '?'
  if (template.recurrence_cadence === 'monthly') return `Repeats monthly on day ${day}`
  if (template.recurrence_cadence === 'quarterly') return `Repeats quarterly on day ${day}`
  if (template.recurrence_cadence === 'annually') {
    const monthName = template.recurrence_month ? MONTH_NAMES[template.recurrence_month - 1] : '?'
    return `Repeats annually on ${monthName} ${day}`
  }
  return null
}

function TemplateCard({ template, isManager, onEdit, onDelete, onUse }: TemplateCardProps) {
  const recurringText = recurringLabel(template)
  return (
    <div className="bg-surface-card dark:bg-dark-card rounded-card border border-[0.5px] border-surface-border dark:border-dark-border p-4">
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] truncate">{template.name}</p>
            {template.is_recurring && (
              <span className="px-2 py-0.5 rounded-full text-[11px] font-medium" style={{ background: '#DBEAFE', color: '#1E40AF' }}>
                Recurring
              </span>
            )}
          </div>
          {recurringText && (
            <p className="text-[11px] text-[#6B7280] mt-0.5">{recurringText}</p>
          )}
          {template.description && (
            <p className="text-[12px] text-[#6B7280] mt-0.5 line-clamp-2">{template.description}</p>
          )}
        </div>
        {isManager && (
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={onEdit}
              className="p-1.5 rounded text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
              title="Edit template"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            <button
              onClick={onDelete}
              className="p-1.5 rounded text-[#6B7280] hover:text-red-500 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20 transition-colors"
              title="Delete template"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      <div className="flex items-center flex-wrap gap-2 mt-3">
        {template.engagement_type && (
          <span className="px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-[10px] font-medium text-blue-700 dark:text-blue-300">
            {formatEngagementType(template.engagement_type)}
          </span>
        )}
        <span className="text-[11px] text-[#6B7280]">{template.task_templates.length} task{template.task_templates.length !== 1 ? 's' : ''}</span>
        <span className="text-[11px] text-[#9CA3AF]">·</span>
        <span className="text-[11px] text-[#6B7280]">{template.document_checklist.length} document{template.document_checklist.length !== 1 ? 's' : ''}</span>
        <span className="text-[11px] text-[#9CA3AF]">·</span>
        <span className="text-[11px] text-[#6B7280]">Used {template.use_count} time{template.use_count !== 1 ? 's' : ''}</span>
      </div>

      <button
        onClick={onUse}
        className="mt-3 w-full h-8 rounded-md border border-[0.5px] border-surface-border dark:border-dark-border text-[12px] font-medium text-brand dark:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
      >
        Use Template
      </button>
    </div>
  )
}

// ---- Sub-tab definitions ----

type SubTab = 'engagement' | 'letters' | 'tax_organizers' | 'qc_checklists' | 'deleted'

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: 'engagement', label: 'Engagement Templates' },
  { key: 'letters', label: 'Engagement Letters' },
  { key: 'tax_organizers', label: 'Tax Organizers' },
  { key: 'qc_checklists', label: 'QC Checklists' },
  { key: 'deleted', label: 'Deleted' },
]

// ---- Main Page ----

export default function TemplatesPage() {
  const { user } = useAuth()
  const isManager = user?.role === 'firm_owner' || user?.role === 'manager'

  const [activeTab, setActiveTab] = useState<SubTab>('engagement')

  const [templates, setTemplates] = useState<Template[]>([])
  const [loading, setLoading] = useState(true)
  const [createOpen, setCreateOpen] = useState(false)
  const [editTemplate, setEditTemplate] = useState<Template | null>(null)
  const [useTemplate, setUseTemplate] = useState<Template | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<Template | null>(null)
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.modal === 'new-template') setCreateOpen(true)
    })
  }, [])

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/v1/engagement-templates/')
      const items = Array.isArray(data) ? data : []
      setTemplates(items.map((r: Record<string, unknown>) => mapTemplate(r)))
    } catch {
      toast.error('Failed to load templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTemplates()
  }, [fetchTemplates])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.delete(`/api/v1/engagement-templates/${deleteTarget.id}`)
      toast.success('Template deleted')
      setDeleteTarget(null)
      fetchTemplates()
    } catch {
      toast.error('Failed to delete template')
    } finally {
      setDeleting(false)
    }
  }

  const activeTabLabel = SUB_TABS.find((t) => t.key === activeTab)?.label ?? ''

  return (<>
      <div className="flex flex-col p-6 gap-0">
        {/* Header */}
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <LayoutTemplate className="h-5 w-5 text-[#6B7280]" />
            <div>
              <h1 className="text-[20px] font-medium text-brand dark:text-[#EDEEF0]">Templates</h1>
              <p className="text-[12px] text-[#6B7280]">{activeTabLabel}</p>
            </div>
          </div>
          {isManager && activeTab === 'engagement' && (
            <button
              onClick={() => setCreateOpen(true)}
              className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5"
            >
              <Plus className="h-4 w-4" /> New Template
            </button>
          )}
        </div>

        {/* Sub-tab bar */}
        <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border mb-6">
          {SUB_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-[13px] transition-colors relative',
                activeTab === tab.key
                  ? 'text-brand dark:text-[#4A7FA5] font-medium'
                  : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal',
              )}
            >
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand dark:bg-[#4A7FA5]" />
              )}
            </button>
          ))}
        </div>

        {/* Engagement Templates tab */}
        {activeTab === 'engagement' && (
          <>
            {loading ? (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="bg-surface-card dark:bg-dark-card rounded-card border border-[0.5px] border-surface-border dark:border-dark-border p-4">
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <div className="flex-1 flex flex-col gap-1.5">
                        <div className="h-3 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                        <div className="h-2.5 w-56 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <div className="h-6 w-6 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                        <div className="h-6 w-6 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-wrap mt-3">
                      <div className="h-4 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
                      <div className="h-3 w-14 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                      <div className="h-3 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                    </div>
                    <div className="h-8 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-md mt-3" />
                  </div>
                ))}
              </div>
            ) : templates.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 gap-3">
                <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
                  <LayoutTemplate className="h-6 w-6 text-[#9CA3AF]" />
                </div>
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No templates yet</p>
                <p className="text-[12px] text-[#6B7280] text-center max-w-sm">
                  Create your first template to speed up engagement creation.
                </p>
                {isManager && (
                  <button
                    onClick={() => setCreateOpen(true)}
                    className="mt-2 h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
                  >
                    Create Template
                  </button>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {templates.map((tmpl) => (
                  <TemplateCard
                    key={tmpl.id}
                    template={tmpl}
                    isManager={isManager}
                    onEdit={() => setEditTemplate(tmpl)}
                    onDelete={() => setDeleteTarget(tmpl)}
                    onUse={() => setUseTemplate(tmpl)}
                  />
                ))}
              </div>
            )}
          </>
        )}

        {/* Engagement Letters tab */}
        {activeTab === 'letters' && <LetterTemplatesTab />}

        {/* Tax Organizers tab */}
        {activeTab === 'tax_organizers' && <TaxOrganizerTemplates />}

        {/* QC Checklists tab */}
        {activeTab === 'qc_checklists' && <QcChecklistTemplatesTab />}

        {/* Deleted tab */}
        {activeTab === 'deleted' && <DeletedTemplates />}
      </div>

      {/* Create modal */}
      {createOpen && (
        <TemplateModal
          editTemplate={null}
          onClose={() => setCreateOpen(false)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Edit modal */}
      {editTemplate && (
        <TemplateModal
          editTemplate={editTemplate}
          onClose={() => setEditTemplate(null)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Use template modal */}
      {useTemplate && (
        <UseTemplateModal
          template={useTemplate}
          onClose={() => setUseTemplate(null)}
        />
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0] mb-2">Delete template?</h3>
            <p className="text-[13px] text-[#6B7280] mb-6">
              &ldquo;{deleteTarget.name}&rdquo; will be archived. This cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setDeleteTarget(null)}
                className="h-8 px-4 text-[12px] font-medium text-[#6B7280] hover:text-brand transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="h-8 px-4 rounded-md bg-red-600 text-white text-[12px] font-medium hover:bg-red-700 disabled:opacity-60 transition-colors flex items-center gap-1.5"
              >
                {deleting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
  </>)
}
