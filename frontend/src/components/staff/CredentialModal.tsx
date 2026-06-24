// frontend/src/components/staff/CredentialModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { staffApi, type StaffCredential, type StaffMember } from '@/lib/api/staffApi'

const CREDENTIAL_TYPES = [
  { value: 'cpa_license', label: 'CPA License' },
  { value: 'ea_enrollment', label: 'EA Enrollment' },
  { value: 'ptin', label: 'PTIN' },
  { value: 'state_license', label: 'State License' },
  { value: 'other', label: 'Other' },
]

const inputClass =
  'w-full h-9 px-3 rounded-[6px] bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const labelClass = 'block text-[12px] font-medium text-brand dark:text-[#EDEEF0] mb-1'

interface Props {
  open: boolean
  onClose: () => void
  onSaved: () => void
  staff: StaffMember[]
  editing: StaffCredential | null
}

export function CredentialModal({ open, onClose, onSaved, staff, editing }: Props) {
  const [userId, setUserId] = useState('')
  const [credentialType, setCredentialType] = useState('cpa_license')
  const [credentialNumber, setCredentialNumber] = useState('')
  const [state, setState] = useState('')
  const [issuedAt, setIssuedAt] = useState('')
  const [expiresAt, setExpiresAt] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    if (editing) {
      setUserId(editing.user_id)
      setCredentialType(editing.credential_type)
      setCredentialNumber(editing.credential_number ?? '')
      setState(editing.state ?? '')
      setIssuedAt(editing.issued_at ?? '')
      setExpiresAt(editing.expires_at ?? '')
      setNotes(editing.notes ?? '')
    } else {
      setUserId('')
      setCredentialType('cpa_license')
      setCredentialNumber('')
      setState('')
      setIssuedAt('')
      setExpiresAt('')
      setNotes('')
    }
    setError(null)
  }, [open, editing])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!userId) { setError('Please select a staff member.'); return }
    setSubmitting(true)
    try {
      const payload = {
        user_id: userId,
        credential_type: credentialType,
        credential_number: credentialNumber || null,
        state: state || null,
        issued_at: issuedAt || null,
        expires_at: expiresAt || null,
        notes: notes || null,
      }
      if (editing) {
        const { user_id: _u, ...updatePayload } = payload
        void _u
        await staffApi.updateCredential(editing.id, updatePayload)
      } else {
        await staffApi.createCredential(payload)
      }
      onSaved()
      onClose()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })
        ?.response?.data?.detail ?? 'Failed to save credential.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={editing ? 'Edit Credential' : 'Add Credential'}
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
            form="credential-form"
            disabled={submitting}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save'}
          </button>
        </>
      }
    >
      <form id="credential-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
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

        <div>
          <label className={labelClass}>Credential Type</label>
          <select
            value={credentialType}
            onChange={(e) => setCredentialType(e.target.value)}
            required
            className={inputClass}
          >
            {CREDENTIAL_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass}>Credential Number</label>
          <input
            type="text"
            value={credentialNumber}
            onChange={(e) => setCredentialNumber(e.target.value)}
            placeholder="e.g. CPA123456"
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>State (if applicable)</label>
          <input
            type="text"
            value={state}
            onChange={(e) => setState(e.target.value)}
            placeholder="e.g. NH"
            className={inputClass}
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className={labelClass}>Issued Date</label>
            <input
              type="date"
              value={issuedAt}
              onChange={(e) => setIssuedAt(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label className={labelClass}>Expiry Date</label>
            <input
              type="date"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            className={inputClass + ' h-auto py-2 resize-none'}
          />
        </div>
      </form>
    </Modal>
  )
}
