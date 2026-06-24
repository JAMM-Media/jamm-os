// frontend/src/components/staff/CPEModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { staffApi, type CPERecord, type StaffMember } from '@/lib/api/staffApi'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const labelClass = 'block text-[12px] font-medium text-brand dark:text-[#EDEEF0] mb-1'

interface Props {
  open: boolean
  onClose: () => void
  onSaved: () => void
  staff: StaffMember[]
  editing: CPERecord | null
}

export function CPEModal({ open, onClose, onSaved, staff, editing }: Props) {
  const [userId, setUserId] = useState('')
  const [periodStart, setPeriodStart] = useState('')
  const [periodEnd, setPeriodEnd] = useState('')
  const [hoursRequired, setHoursRequired] = useState('0')
  const [hoursCompleted, setHoursCompleted] = useState('0')
  const [deadline, setDeadline] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    if (editing) {
      setUserId(editing.user_id)
      setPeriodStart(editing.reporting_period_start)
      setPeriodEnd(editing.reporting_period_end)
      setHoursRequired(String(editing.hours_required))
      setHoursCompleted(String(editing.hours_completed))
      setDeadline(editing.deadline ?? '')
      setNotes(editing.notes ?? '')
    } else {
      setUserId('')
      setPeriodStart('')
      setPeriodEnd('')
      setHoursRequired('0')
      setHoursCompleted('0')
      setDeadline('')
      setNotes('')
    }
    setError(null)
  }, [open, editing])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!userId) { setError('Please select a staff member.'); return }
    if (!periodStart || !periodEnd) { setError('Reporting period is required.'); return }
    setSubmitting(true)
    try {
      const payload = {
        user_id: userId,
        reporting_period_start: periodStart,
        reporting_period_end: periodEnd,
        hours_required: parseFloat(hoursRequired) || 0,
        hours_completed: parseFloat(hoursCompleted) || 0,
        deadline: deadline || null,
        notes: notes || null,
      }
      if (editing) {
        const { user_id: _u, ...updatePayload } = payload
        void _u
        await staffApi.updateCPERecord(editing.id, updatePayload)
      } else {
        await staffApi.createCPERecord(payload)
      }
      onSaved()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail ?? 'Failed to save CPE record.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? 'Edit CPE Record' : 'Add CPE Record'}
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="cpe-form"
            disabled={submitting}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save'}
          </button>
        </>
      }
    >
      <form id="cpe-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        {error && (
          <p className="text-[12px] text-[#DC2626]">{error}</p>
        )}

        <div>
          <label className={labelClass}>Staff Member</label>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            disabled={!!editing}
            required
            className={inputClass + (editing ? ' opacity-60 cursor-not-allowed' : '')}
          >
            <option value="">Select staff member...</option>
            {staff.map((s) => (
              <option key={s.id} value={s.id}>
                {s.full_name || s.email}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Reporting Period Start</label>
            <input
              type="date"
              value={periodStart}
              onChange={(e) => setPeriodStart(e.target.value)}
              required
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Reporting Period End</label>
            <input
              type="date"
              value={periodEnd}
              onChange={(e) => setPeriodEnd(e.target.value)}
              required
              className={inputClass}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Hours Required</label>
            <input
              type="number"
              value={hoursRequired}
              onChange={(e) => setHoursRequired(e.target.value)}
              step="0.5"
              min="0"
              required
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Hours Completed</label>
            <input
              type="number"
              value={hoursCompleted}
              onChange={(e) => setHoursCompleted(e.target.value)}
              step="0.5"
              min="0"
              required
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Deadline</label>
          <input
            type="date"
            value={deadline}
            onChange={(e) => setDeadline(e.target.value)}
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className={inputClass + ' h-auto py-2 resize-none'}
          />
        </div>
      </form>
    </Modal>
  )
}
