// frontend/src/components/engagements/ExtensionPanel.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { CalendarClock } from 'lucide-react'
import { useFetch } from '@/lib/hooks/useFetch'
import { useAuth } from '@/lib/hooks/useAuth'
import { extensionsApi, type ExtensionRecord, type ExtensionFileRequest, type ExtensionUpdateRequest } from '@/lib/api/extensionsApi'

interface ExtensionPanelProps {
  engagementId: string
  clientId: string
}

const FORM_OPTIONS: { value: '4868' | '7004' | '8868'; label: string; description: string; deadline: string }[] = [
  { value: '4868', label: 'Form 4868', description: 'Individual income tax extension', deadline: 'Oct 15' },
  { value: '7004', label: 'Form 7004', description: 'Business return extension', deadline: 'Sep 15' },
  { value: '8868', label: 'Form 8868', description: 'Exempt organization extension', deadline: 'Nov 15' },
]

const FORM_DESCRIPTIONS: Record<string, string> = {
  '4868': 'Individual income tax extension',
  '7004': 'Business return extension',
  '8868': 'Exempt organization extension',
}

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function deadlineColor(dateStr: string): string {
  const deadline = new Date(dateStr)
  const now = new Date()
  const diffMs = deadline.getTime() - now.getTime()
  const diffDays = diffMs / (1000 * 60 * 60 * 24)
  if (diffDays < 0) return 'text-[#DC2626]'
  if (diffDays <= 30) return 'text-[#92400E]'
  return ''
}

function StatusBadgePill({ status }: { status: ExtensionRecord['status'] }) {
  const styles: Record<ExtensionRecord['status'], string> = {
    not_filed: 'bg-[#E5E7EB] text-[#1F3148] border border-[0.5px] border-[#1F3148]',
    filed: 'bg-[#DBEAFE] text-[#1E40AF]',
    confirmed: 'bg-[#D1FAE5] text-[#065F46]',
  }
  const labels: Record<ExtensionRecord['status'], string> = {
    not_filed: 'Not Filed',
    filed: 'Filed',
    confirmed: 'Confirmed',
  }
  return (
    <span
      className={`inline-flex items-center h-[22px] px-[10px] rounded-full text-[11px] font-medium ${styles[status]}`}
    >
      {labels[status]}
    </span>
  )
}

function humanStatus(status: ExtensionRecord['status']): string {
  return status.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

export function ExtensionPanel({ engagementId, clientId }: ExtensionPanelProps) {
  const { user } = useAuth()
  const isManager = user?.role === 'manager' || user?.role === 'firm_owner'

  const { data: listData, isLoading, refetch } = useFetch<ExtensionRecord[]>(
    () => extensionsApi.listForEngagement(engagementId).then((r) => r.data),
    [engagementId]
  )

  const extension = listData?.[0] ?? null

  // File Extension modal state
  const [fileModalOpen, setFileModalOpen] = useState(false)
  const [formType, setFormType] = useState<'4868' | '7004' | '8868'>('4868')
  const [filedAt, setFiledAt] = useState('')
  const [overrideDeadline, setOverrideDeadline] = useState('')
  const [fileNotes, setFileNotes] = useState('')
  const [filing, setFiling] = useState(false)

  // Update Status modal state
  const [updateModalOpen, setUpdateModalOpen] = useState(false)
  const [updateStatus, setUpdateStatus] = useState<ExtensionRecord['status']>('not_filed')
  const [updateNotes, setUpdateNotes] = useState('')
  const [updating, setUpdating] = useState(false)

  function openFileModal() {
    setFormType('4868')
    setFiledAt('')
    setOverrideDeadline('')
    setFileNotes('')
    setFileModalOpen(true)
  }

  function openUpdateModal(ext: ExtensionRecord) {
    setUpdateStatus(ext.status)
    setUpdateNotes(ext.notes ?? '')
    setUpdateModalOpen(true)
  }

  async function handleFile(e: React.FormEvent) {
    e.preventDefault()
    setFiling(true)
    const payload: ExtensionFileRequest = {
      engagement_id: engagementId,
      client_id: clientId,
      form_type: formType,
    }
    if (filedAt) payload.filed_at = filedAt
    if (overrideDeadline) payload.extended_deadline = overrideDeadline
    if (fileNotes.trim()) payload.notes = fileNotes.trim()
    try {
      const { data } = await extensionsApi.file(payload)
      setFileModalOpen(false)
      refetch()
      toast.success(`Extension filed. New deadline: ${formatDate(data.extended_deadline)}.`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ?? (err as { message?: string })?.message ?? 'Failed to file extension.'
      toast.error(msg)
    } finally {
      setFiling(false)
    }
  }

  async function handleUpdate(e: React.FormEvent) {
    e.preventDefault()
    if (!extension) return
    setUpdating(true)
    const payload: ExtensionUpdateRequest = {
      status: updateStatus,
      notes: updateNotes.trim() || undefined,
    }
    try {
      await extensionsApi.update(extension.id, payload)
      setUpdateModalOpen(false)
      refetch()
      toast.success('Extension updated.')
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail ?? (err as { message?: string })?.message ?? 'Failed to update extension.'
      toast.error(msg)
    } finally {
      setUpdating(false)
    }
  }

  return (
    <>
      <div className="bg-surface-card dark:bg-dark-card rounded-[8px] border border-[0.5px] border-surface-border dark:border-dark-border p-4">
        {isLoading ? (
          <div className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <div className="h-4 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              <div className="h-5 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full" />
            </div>
            <div className="grid grid-cols-2 gap-3 mt-1">
              {[1, 2, 3, 4].map((j) => (
                <div key={j} className="flex flex-col gap-1">
                  <div className="h-2.5 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </div>
              ))}
            </div>
          </div>
        ) : extension ? (
          <>
            {/* Header row */}
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">Extension</span>
              <StatusBadgePill status={extension.status} />
            </div>

            {/* Content grid */}
            <div className="grid grid-cols-2 gap-3 mt-3">
              <div className="flex flex-col gap-1">
                <span className={labelClass}>Form Type</span>
                <span className={valueClass}>Form {extension.form_type}</span>
                <span className="text-[11px] text-[#6B7280]">{FORM_DESCRIPTIONS[extension.form_type]}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className={labelClass}>Filed</span>
                <span className={valueClass}>{formatDate(extension.filed_at)}</span>
              </div>
              <div className="flex flex-col gap-1">
                <span className={labelClass}>New Deadline</span>
                <span className={`text-[13px] ${deadlineColor(extension.extended_deadline) || 'text-brand dark:text-[#EDEEF0]'}`}>
                  {formatDate(extension.extended_deadline)}
                </span>
              </div>
              <div className="flex flex-col gap-1">
                <span className={labelClass}>Status</span>
                <span className={valueClass}>{humanStatus(extension.status)}</span>
              </div>
            </div>

            {/* Notes row */}
            {extension.notes && (
              <div className="flex flex-col gap-1 mt-3">
                <span className={labelClass}>Notes</span>
                <span className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{extension.notes}</span>
              </div>
            )}

            {/* Footer row */}
            {isManager && (
              <div className="flex items-center gap-2 mt-3">
                <button
                  onClick={() => openUpdateModal(extension)}
                  className="h-8 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] bg-transparent text-[#1F3148] dark:text-[#EDEEF0] text-[12px] font-medium hover:opacity-80 transition-opacity"
                >
                  Update Status
                </button>
                <button
                  onClick={openFileModal}
                  className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
                >
                  + File New Extension
                </button>
              </div>
            )}
          </>
        ) : (
          /* Empty state */
          <div className="flex flex-col items-center justify-center py-6 gap-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-[8px] bg-[#F3F4F6] dark:bg-[#2A2A2A]">
              <CalendarClock className="w-[18px] h-[18px] text-[#6B7280]" />
            </div>
            <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">No extension filed</p>
            <p className="text-[12px] text-[#6B7280] text-center">
              File an extension to move this engagement&apos;s deadline.
            </p>
            {isManager && (
              <button
                onClick={openFileModal}
                className="mt-1 h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
              >
                + File Extension
              </button>
            )}
          </div>
        )}
      </div>

      {/* File Extension Modal */}
      {fileModalOpen && (
        <FileExtensionModalContent
          formType={formType}
          setFormType={setFormType}
          filedAt={filedAt}
          setFiledAt={setFiledAt}
          overrideDeadline={overrideDeadline}
          setOverrideDeadline={setOverrideDeadline}
          fileNotes={fileNotes}
          setFileNotes={setFileNotes}
          filing={filing}
          onSubmit={handleFile}
          onClose={() => setFileModalOpen(false)}
        />
      )}

      {/* Update Status Modal */}
      {updateModalOpen && extension && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={(e) => { if (e.target === e.currentTarget) setUpdateModalOpen(false) }}
        >
          <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border p-6 w-full max-w-md shadow-xl">
            <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0] mb-4">Update Extension Status</h2>
            <form onSubmit={handleUpdate} className="flex flex-col gap-4">
              {/* Status radio group */}
              <div className="flex flex-col gap-2">
                <label className={labelClass}>Status</label>
                <div className="flex flex-col gap-2">
                  {(['not_filed', 'filed', 'confirmed'] as const).map((s) => (
                    <label key={s} className="flex items-center gap-3 cursor-pointer">
                      <input
                        type="radio"
                        name="status"
                        value={s}
                        checked={updateStatus === s}
                        onChange={() => setUpdateStatus(s)}
                        className="accent-brand"
                        required
                      />
                      <span className="text-[13px] text-brand dark:text-[#EDEEF0]">{humanStatus(s)}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Notes */}
              <div className="flex flex-col gap-1.5">
                <label className={labelClass}>Notes</label>
                <textarea
                  value={updateNotes}
                  onChange={(e) => setUpdateNotes(e.target.value)}
                  placeholder="Any notes about this extension..."
                  rows={3}
                  className="px-3 py-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] resize-none placeholder:text-[#9CA3AF]"
                />
              </div>

              <div className="flex items-center justify-end gap-2 mt-1">
                <button
                  type="button"
                  onClick={() => setUpdateModalOpen(false)}
                  className="h-8 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] bg-transparent text-[#1F3148] dark:text-[#EDEEF0] text-[12px] font-medium hover:opacity-80 transition-opacity"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updating}
                  className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {updating ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}

interface FileExtensionModalContentProps {
  formType: '4868' | '7004' | '8868'
  setFormType: (v: '4868' | '7004' | '8868') => void
  filedAt: string
  setFiledAt: (v: string) => void
  overrideDeadline: string
  setOverrideDeadline: (v: string) => void
  fileNotes: string
  setFileNotes: (v: string) => void
  filing: boolean
  onSubmit: (e: React.FormEvent) => void
  onClose: () => void
}

function FileExtensionModalContent({
  formType, setFormType, filedAt, setFiledAt,
  overrideDeadline, setOverrideDeadline, fileNotes, setFileNotes,
  filing, onSubmit, onClose,
}: FileExtensionModalContentProps) {
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto flex flex-col">
        <div className="sticky top-0 bg-surface-card dark:bg-dark-card z-10 flex items-center justify-between p-4 border-b border-surface-border dark:border-dark-border">
          <h2 className="text-[15px] font-medium text-brand dark:text-[#EDEEF0]">File Extension</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors text-[18px] leading-none"
          >
            ×
          </button>
        </div>
        <form onSubmit={onSubmit} className="flex flex-col gap-4 p-6">
          {/* Form type radio group */}
          <div className="flex flex-col gap-2">
            <label className={labelClass}>Form Type</label>
            <div className="flex flex-col gap-2">
              {FORM_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="radio"
                    name="form_type"
                    value={opt.value}
                    checked={formType === opt.value}
                    onChange={() => setFormType(opt.value)}
                    className="mt-0.5 accent-brand"
                    required
                  />
                  <div>
                    <span className="text-[13px] text-brand dark:text-[#EDEEF0]">
                      {opt.label} — {opt.description} (extends to {opt.deadline})
                    </span>
                    <p className="text-[11px] text-[#6B7280]">{opt.description}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          {/* Filed date */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Filed date</label>
            <input
              type="date"
              value={filedAt}
              onChange={(e) => setFiledAt(e.target.value)}
              className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0]"
            />
            <span className="text-[11px] text-[#6B7280]">Defaults to today if left blank.</span>
          </div>

          {/* Override deadline */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Override deadline</label>
            <input
              type="date"
              value={overrideDeadline}
              onChange={(e) => setOverrideDeadline(e.target.value)}
              className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0]"
            />
            <span className="text-[11px] text-[#6B7280]">Leave blank to use the standard extended deadline for this form type.</span>
          </div>

          {/* Notes */}
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Notes</label>
            <textarea
              value={fileNotes}
              onChange={(e) => setFileNotes(e.target.value)}
              placeholder="Any notes about this extension..."
              rows={3}
              className="px-3 py-2 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[13px] text-brand dark:text-[#EDEEF0] resize-none placeholder:text-[#9CA3AF]"
            />
          </div>

          <div className="flex items-center justify-end gap-2 mt-1">
            <button
              type="button"
              onClick={onClose}
              className="h-8 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] bg-transparent text-[#1F3148] dark:text-[#EDEEF0] text-[12px] font-medium hover:opacity-80 transition-opacity"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={filing}
              className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {filing ? 'Filing...' : 'File Extension'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
