'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, X, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { formatEngagementType } from '@/lib/utils'

const ENGAGEMENT_TYPES = [
  { value: 'tax_return_1040', label: 'Tax Return - 1040' },
  { value: 'tax_return_1120', label: 'Tax Return - 1120' },
  { value: 'tax_return_1120s', label: 'Tax Return - 1120-S' },
  { value: 'tax_return_1065', label: 'Tax Return - 1065' },
  { value: 'tax_return_1041', label: 'Tax Return - 1041' },
  { value: 'tax_return_706', label: 'Tax Return - 706' },
  { value: 'amended_return_1040x', label: 'Amended - 1040-X' },
  { value: 'extension_4868', label: 'Extension - 4868' },
  { value: 'extension_7004', label: 'Extension - 7004' },
  { value: 'extension_8868', label: 'Extension - 8868' },
  { value: 'payroll_tax_941', label: 'Payroll - 941' },
  { value: 'tax_planning_advisory', label: 'Tax Planning Advisory' },
  { value: 'bookkeeping_monthly', label: 'Bookkeeping - Monthly' },
  { value: 'bookkeeping_quarterly', label: 'Bookkeeping - Quarterly' },
  { value: 'audit_representation', label: 'Audit Representation' },
  { value: 'other_advisory', label: 'Other Advisory' },
  { value: 'custom', label: 'Custom' },
]

const PRESET_ITEMS: Record<string, string[]> = {
  tax_return_1040: ['W-2', '1099-INT / 1099-DIV', 'Prior Year Tax Return', '1098 Mortgage Interest Statement'],
  tax_return_1120: ['Prior Year Tax Return', 'Trial Balance / General Ledger', 'Bank Statements', 'Fixed Asset Schedule'],
  tax_return_1120s: ['Prior Year Tax Return', 'Trial Balance / General Ledger', 'Bank Statements', 'Shareholder Basis Schedule'],
  tax_return_1065: ['Prior Year Tax Return', 'Trial Balance / General Ledger', 'Bank Statements', 'Partner Capital Account Schedules'],
  tax_return_1041: ['Prior Year Tax Return', 'Trust or Estate Documents', 'Bank and Brokerage Statements', 'K-1s Received'],
  tax_return_706: ['Death Certificate', 'Asset Valuation Documents', 'Prior Gift Tax Returns'],
  amended_return_1040x: ['Original Filed Return', 'Corrected Supporting Documents', 'Explanation of Changes'],
  payroll_tax_941: ['Payroll Register', 'Prior Filed 941', 'Bank Statements'],
  bookkeeping_monthly: ['Bank Statements', 'Credit Card Statements', 'Receipts and Invoices'],
  bookkeeping_quarterly: ['Bank Statements', 'Credit Card Statements', 'Receipts and Invoices', 'Payroll Reports'],
}

interface FormRow {
  label: string
  isRequired: boolean
}

const emptyRow = (): FormRow => ({ label: '', isRequired: true })
const initialRows = (): FormRow[] => [emptyRow(), emptyRow(), emptyRow()]

interface DRTemplate {
  id: string
  name: string
  engagement_type: string
  title_default: string | null
  items: { label: string; is_required: boolean }[]
  is_active: boolean
  use_count: number
}

interface ModalProps {
  editTemplate: DRTemplate | null
  onClose: () => void
  onSaved: () => void
}

function DRTemplateModal({ editTemplate, onClose, onSaved }: ModalProps) {
  const [name, setName] = useState(editTemplate?.name ?? '')
  const [engagementType, setEngagementType] = useState(editTemplate?.engagement_type ?? '')
  const [titleDefault, setTitleDefault] = useState(editTemplate?.title_default ?? '')
  const [items, setItems] = useState<FormRow[]>(
    editTemplate
      ? editTemplate.items.map((i) => ({ label: i.label, isRequired: i.is_required }))
      : initialRows()
  )
  const [saving, setSaving] = useState(false)
  const [suggestionLoading, setSuggestionLoading] = useState(false)

  // Tracks what was last auto-applied (initial blank rows or a preset).
  // Used to detect whether the user has made manual edits before applying a new preset.
  const autoAppliedItemsRef = useRef<FormRow[]>(initialRows())

  // Tracks the last auto-suggested template name so we can tell whether the
  // current name was typed by the user or is still the auto-suggestion.
  const lastNameSuggestionRef = useRef('')

  // Incremented each time handleEngagementTypeChange fires. The async fetch
  // captures the count at call time and only applies its result if the count
  // still matches, preventing a slow response from overwriting a newer selection.
  const fetchCounterRef = useRef(0)

  async function handleEngagementTypeChange(newType: string) {
    // Never apply presets when editing an existing template.
    if (editTemplate !== null) {
      setEngagementType(newType)
      return
    }

    setEngagementType(newType)

    // Check whether current items still exactly match what was last auto-applied.
    const current = items
    const last = autoAppliedItemsRef.current
    const stillAutoApplied =
      current.length === last.length &&
      current.every((row, i) => row.label === last[i].label && row.isRequired === last[i].isRequired)

    if (!stillAutoApplied) return

    // Capture counter before async work; only apply result if it still matches.
    const myCount = ++fetchCounterRef.current

    let newItems: FormRow[]

    setSuggestionLoading(true)
    try {
      const { data } = await api.get(
        `/api/v1/document-request-templates/suggested?engagement_type=${encodeURIComponent(newType)}`
      )
      if (fetchCounterRef.current !== myCount) return
      newItems = Array.isArray(data?.items)
        ? data.items.map((i: { label: string; is_required: boolean }) => ({
            label: i.label,
            isRequired: i.is_required,
          }))
        : initialRows()
    } catch {
      if (fetchCounterRef.current !== myCount) return
      const presetLabels = PRESET_ITEMS[newType]
      newItems = presetLabels
        ? presetLabels.map((label) => ({ label, isRequired: true }))
        : initialRows()
    } finally {
      if (fetchCounterRef.current === myCount) setSuggestionLoading(false)
    }

    autoAppliedItemsRef.current = newItems
    setItems(newItems)

    // Auto-suggest a template name from the engagement type label if the name
    // field is empty or still matches the last auto-suggestion.
    const typeLabel = ENGAGEMENT_TYPES.find((et) => et.value === newType)?.label ?? ''
    if (typeLabel) {
      const suggestion = `${typeLabel} Documents`
      setName((prev) => {
        if (prev === '' || prev === lastNameSuggestionRef.current) {
          lastNameSuggestionRef.current = suggestion
          return suggestion
        }
        return prev
      })
    }
  }

  function addItem() {
    if (items.length >= 20) return
    setItems((prev) => [...prev, emptyRow()])
  }

  function updateItem(idx: number, updates: Partial<FormRow>) {
    setItems((prev) => prev.map((row, i) => (i === idx ? { ...row, ...updates } : row)))
  }

  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error('Template name is required')
      return
    }
    if (!engagementType) {
      toast.error('Engagement type is required')
      return
    }
    const validItems = items.filter((i) => i.label.trim())
    setSaving(true)
    const body = {
      name: name.trim(),
      engagement_type: engagementType,
      title_default: titleDefault.trim() || null,
      items: validItems.map((i) => ({ label: i.label.trim(), is_required: i.isRequired })),
    }
    try {
      if (editTemplate) {
        await api.patch(`/api/v1/document-request-templates/${editTemplate.id}`, body)
        toast.success('Template updated')
      } else {
        await api.post('/api/v1/document-request-templates/', body)
        toast.success('Template created')
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#E5E7EB] dark:border-[#333]">
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">
            {editTemplate ? 'Edit Document Request Template' : 'New Document Request Template'}
          </h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors">
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
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 1040 Tax Season Documents"
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          {/* Engagement type */}
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Engagement type <span className="text-red-500">*</span>
            </label>
            <select
              value={engagementType}
              onChange={(e) => handleEngagementTypeChange(e.target.value)}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light"
            >
              <option value="">Select engagement type...</option>
              {ENGAGEMENT_TYPES.map((et) => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </select>
          </div>

          {/* Title default -- optional, lighter weight */}
          <div>
            <label className="block text-[11px] text-[#9CA3AF] dark:text-[#6B7280] mb-1">
              Default request title <span className="italic">(optional)</span>
            </label>
            <input
              type="text"
              value={titleDefault}
              onChange={(e) => setTitleDefault(e.target.value)}
              placeholder="e.g. 2025 Tax Season Documents"
              className="w-full h-8 px-3 rounded-md border border-[#E5E7EB] dark:border-[#333] bg-white dark:bg-[#252525] text-[12px] text-[#6B7280] dark:text-[#9CA3AF] placeholder:text-[#D1D5DB] focus:outline-none focus:border-brand-light"
            />
            <p className="mt-0.5 text-[11px] text-[#D1D5DB] dark:text-[#444]">
              Pre-fills the request title when this template is applied.
            </p>
          </div>

          {/* Checklist items */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="flex items-center gap-1.5 text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Checklist items
                {suggestionLoading && <Loader2 className="h-3 w-3 animate-spin text-[#9CA3AF]" />}
              </label>
              {items.length < 20 && (
                <button
                  type="button"
                  onClick={addItem}
                  className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
                >
                  <Plus className="h-3 w-3" /> Add item
                </button>
              )}
            </div>
            <div className="space-y-2">
              {items.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={item.label}
                    onChange={(e) => updateItem(idx, { label: e.target.value })}
                    placeholder="e.g. W-2, 1099-DIV..."
                    className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
                  <label className="flex items-center gap-1 text-[11px] text-[#6B7280] cursor-pointer whitespace-nowrap select-none">
                    <input
                      type="checkbox"
                      checked={item.isRequired}
                      onChange={(e) => updateItem(idx, { isRequired: e.target.checked })}
                      className="w-3 h-3"
                    />
                    Req.
                  </label>
                  <button
                    type="button"
                    onClick={() => removeItem(idx)}
                    className="text-[#9CA3AF] hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
              {items.length === 0 && (
                <p className="text-[11px] text-[#9CA3AF]">No items yet. Click &ldquo;Add item&rdquo; to add one.</p>
              )}
            </div>
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

export default function DocumentRequestTemplatesTab() {
  const { user, isLoading: authLoading } = useAuth()
  const isManager = user?.role === 'firm_owner' || user?.role === 'manager'

  const [templates, setTemplates] = useState<DRTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editTemplate, setEditTemplate] = useState<DRTemplate | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<DRTemplate | null>(null)
  const [archiving, setArchiving] = useState(false)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/v1/document-request-templates/')
      const all = Array.isArray(data) ? data : []
      setTemplates(
        all.map((t: Record<string, unknown>) => ({
          id: String(t.id),
          name: String(t.name ?? ''),
          engagement_type: String(t.engagement_type ?? ''),
          title_default: t.title_default ? String(t.title_default) : null,
          items: Array.isArray(t.items)
            ? (t.items as { label: string; is_required: boolean }[])
            : [],
          is_active: Boolean(t.is_active ?? true),
          use_count: Number(t.use_count ?? 0),
        }))
      )
    } catch {
      toast.error('Failed to load document request templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleArchive() {
    if (!archiveTarget) return
    setArchiving(true)
    try {
      await api.delete(`/api/v1/document-request-templates/${archiveTarget.id}`)
      toast.success('Template archived')
      setArchiveTarget(null)
      fetchTemplates()
    } catch {
      toast.error('Failed to archive template')
    } finally {
      setArchiving(false)
    }
  }

  const filtered = templates.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase())
  )

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-[13px] text-muted-foreground text-center py-6">Loading...</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Hint */}
      <p className="text-[11px] text-[#9CA3AF]">
        Selecting an engagement type will suggest checklist items from your most recently saved template for that type.
      </p>

      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search document request templates..."
          className="h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light w-72"
        />
        {isManager && (
          <button
            onClick={() => setCreateOpen(true)}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" /> New Template
          </button>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-3 flex items-center justify-between">
              <div className="flex flex-col gap-1 min-w-0">
                <div className="h-3 w-44 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2.5 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <div className="h-6 w-8 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-6 w-8 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
            </div>
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            {search ? 'No matching templates' : 'No document request templates yet'}
          </p>
          <p className="text-[12px] text-[#6B7280] text-center max-w-sm">
            {search
              ? 'Try a different search term.'
              : 'Create one to pre-fill checklists when sending document requests.'}
          </p>
          {isManager && !search && (
            <button
              onClick={() => setCreateOpen(true)}
              className="mt-2 h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
            >
              Create Template
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((t) => (
            <div
              key={t.id}
              className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-3 flex items-center justify-between group"
            >
              <div className="flex flex-col gap-0.5 min-w-0">
                <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] truncate">
                  {t.name}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[12px] text-[#6B7280]">
                    {formatEngagementType(t.engagement_type)}
                  </span>
                  <span className="text-[11px] text-[#9CA3AF]">·</span>
                  <span className="text-[11px] text-[#9CA3AF]">
                    {t.items.length} item{t.items.length !== 1 ? 's' : ''}
                  </span>
                </div>
              </div>
              {isManager && (
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                  <button
                    onClick={() => setEditTemplate(t)}
                    className="p-1.5 rounded text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333] transition-colors"
                    title="Edit"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  <button
                    onClick={() => setArchiveTarget(t)}
                    className="p-1.5 rounded text-[#6B7280] hover:text-red-500 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20 transition-colors"
                    title="Archive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Create modal */}
      {createOpen && (
        <DRTemplateModal
          editTemplate={null}
          onClose={() => setCreateOpen(false)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Edit modal */}
      {editTemplate && (
        <DRTemplateModal
          editTemplate={editTemplate}
          onClose={() => setEditTemplate(null)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Archive confirm */}
      {archiveTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0] mb-2">Archive template?</h3>
            <p className="text-[13px] text-[#6B7280] mb-6">
              &ldquo;{archiveTarget.name}&rdquo; will be archived and moved to Deleted.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setArchiveTarget(null)}
                className="h-8 px-4 text-[12px] font-medium text-[#6B7280] hover:text-brand transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleArchive}
                disabled={archiving}
                className="h-8 px-4 rounded-md bg-red-600 text-white text-[12px] font-medium hover:bg-red-700 disabled:opacity-60 transition-colors flex items-center gap-1.5"
              >
                {archiving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                Archive
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
