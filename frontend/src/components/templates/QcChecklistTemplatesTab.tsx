'use client'

import { useState, useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import { Plus, Pencil, Trash2, X, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'
import { formatEngagementType } from '@/lib/utils'

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

interface QcTemplate {
  id: string
  name: string
  engagement_type: string | null
  items: string[]
  is_active: boolean
}

interface ModalProps {
  editTemplate: QcTemplate | null
  onClose: () => void
  onSaved: () => void
}

function QcTemplateModal({ editTemplate, onClose, onSaved }: ModalProps) {
  const [name, setName] = useState(editTemplate?.name ?? '')
  const [engagementType, setEngagementType] = useState(editTemplate?.engagement_type ?? '')
  const [items, setItems] = useState<string[]>(editTemplate?.items ?? [])
  const [saving, setSaving] = useState(false)

  function addItem() {
    setItems((prev) => [...prev, ''])
  }

  function updateItem(idx: number, value: string) {
    setItems((prev) => {
      const next = [...prev]
      next[idx] = value
      return next
    })
  }

  function removeItem(idx: number) {
    setItems((prev) => prev.filter((_, i) => i !== idx))
  }

  async function handleSave() {
    if (!name.trim()) {
      toast.error('Template name is required')
      return
    }
    setSaving(true)
    const body = {
      name: name.trim(),
      engagement_type: engagementType || null,
      items: items.filter((i) => i.trim()),
    }
    try {
      if (editTemplate) {
        await api.patch(`/qc-checklists/templates/${editTemplate.id}`, body)
        toast.success('Template updated')
      } else {
        await api.post('/qc-checklists/templates/', body)
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
            {editTemplate ? 'Edit QC Checklist' : 'New QC Checklist'}
          </h2>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Template name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. 1040 QC Checklist"
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF] mb-1">
              Engagement type
            </label>
            <select
              value={engagementType}
              onChange={(e) => setEngagementType(e.target.value)}
              className="w-full h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] focus:outline-none focus:border-brand-light"
            >
              <option value="">All engagement types (manual only)</option>
              {ENGAGEMENT_TYPES.map((et) => (
                <option key={et.value} value={et.value}>{et.label}</option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[12px] font-medium text-[#374151] dark:text-[#9CA3AF]">
                Checklist items
              </label>
              <button
                type="button"
                onClick={addItem}
                className="flex items-center gap-1 text-[11px] text-brand-light hover:underline"
              >
                <Plus className="h-3 w-3" /> Add item
              </button>
            </div>
            <div className="space-y-2">
              {items.map((item, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={item}
                    onChange={(e) => updateItem(idx, e.target.value)}
                    placeholder="e.g. Verify prior year carryforward"
                    className="flex-1 h-8 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[12px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light"
                  />
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

export default function QcChecklistTemplatesTab() {
  const { user } = useAuth()
  const isManager = user?.role === 'firm_owner' || user?.role === 'manager'

  const [templates, setTemplates] = useState<QcTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editTemplate, setEditTemplate] = useState<QcTemplate | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<QcTemplate | null>(null)
  const [deleting, setDeleting] = useState(false)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/qc-checklists/templates/')
      const all = Array.isArray(data) ? data : []
      setTemplates(
        all.map((t: Record<string, unknown>) => ({
          id: String(t.id),
          name: String(t.name ?? ''),
          engagement_type: t.engagement_type ? String(t.engagement_type) : null,
          items: Array.isArray(t.items) ? (t.items as string[]) : [],
          is_active: Boolean(t.is_active ?? true),
        }))
      )
    } catch {
      toast.error('Failed to load QC checklist templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await api.delete(`/qc-checklists/templates/${deleteTarget.id}`)
      toast.success('Template deleted')
      setDeleteTarget(null)
      fetchTemplates()
    } catch {
      toast.error('Failed to delete template')
    } finally {
      setDeleting(false)
    }
  }

  const filtered = templates.filter((t) =>
    t.name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col gap-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search QC checklists..."
          className="h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light w-64"
        />
        {isManager && (
          <button
            onClick={() => setCreateOpen(true)}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5"
          >
            <Plus className="h-4 w-4" /> New QC Checklist
          </button>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex flex-col gap-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-14 rounded-[8px] bg-[#D5D8DE] dark:bg-[#333] animate-pulse" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            {search ? 'No matching templates' : 'No QC checklist templates yet'}
          </p>
          <p className="text-[12px] text-[#6B7280] text-center max-w-sm">
            {search ? 'Try a different search term.' : 'Create one to standardize your review process.'}
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
                    {t.engagement_type
                      ? formatEngagementType(t.engagement_type)
                      : 'All engagement types'}
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
                    onClick={() => setDeleteTarget(t)}
                    className="p-1.5 rounded text-[#6B7280] hover:text-red-500 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20 transition-colors"
                    title="Delete"
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
        <QcTemplateModal
          editTemplate={null}
          onClose={() => setCreateOpen(false)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Edit modal */}
      {editTemplate && (
        <QcTemplateModal
          editTemplate={editTemplate}
          onClose={() => setEditTemplate(null)}
          onSaved={fetchTemplates}
        />
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white dark:bg-[#1E1E1E] rounded-xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0] mb-2">Delete template?</h3>
            <p className="text-[13px] text-[#6B7280] mb-6">
              &ldquo;{deleteTarget.name}&rdquo; will be archived and moved to Deleted.
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
    </div>
  )
}
