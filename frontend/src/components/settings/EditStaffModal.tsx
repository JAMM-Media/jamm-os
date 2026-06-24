// frontend/src/components/settings/EditStaffModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { staffApi, type StaffMember } from '@/lib/api/staffApi'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const labelClass = 'block text-[12px] font-medium text-brand dark:text-[#EDEEF0] mb-1'

interface Props {
  open: boolean
  onClose: () => void
  onSaved: () => void
  member: StaffMember | null
}

export function EditStaffModal({ open, onClose, onSaved, member }: Props) {
  const [fullName, setFullName] = useState('')
  const [role, setRole] = useState('staff')
  const [isActive, setIsActive] = useState('true')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || !member) return
    setFullName(member.full_name ?? '')
    setRole(member.role)
    setIsActive(member.is_active ? 'true' : 'false')
    setError(null)
  }, [open, member])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!member) return
    setError(null)
    setSubmitting(true)
    try {
      await staffApi.updateUser(member.id, {
        full_name: fullName || undefined,
        role,
        is_active: isActive === 'true',
      })
      onSaved()
      onClose()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ?? 'Failed to update team member.'
      setError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const displayName = member?.full_name || member?.email || ''

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit Team Member"
      size="sm"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[13px] text-brand dark:text-[#EDEEF0] hover:opacity-80 transition-opacity"
          >
            Cancel
          </button>
          <button
            type="submit"
            form="edit-staff-form"
            disabled={submitting}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save Changes'}
          </button>
        </>
      }
    >
      <form id="edit-staff-form" onSubmit={handleSubmit} className="flex flex-col gap-4">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{displayName}</p>

        {error && (
          <p className="text-[12px] text-[#DC2626]">{error}</p>
        )}

        <div>
          <label className={labelClass}>Full Name</label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="Full name"
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className={inputClass}
          >
            <option value="staff">Staff</option>
            <option value="manager">Manager</option>
            <option value="firm_owner">Firm Owner</option>
          </select>
          <div className="mt-2 px-3 py-2 bg-[#FEF3C7] rounded text-[12px] text-[#92400E]">
            Changing a staff member&apos;s role takes effect immediately and invalidates their current
            session. They will need to log in again.
          </div>
        </div>

        <div>
          <label className={labelClass}>Status</label>
          <select
            value={isActive}
            onChange={(e) => setIsActive(e.target.value)}
            className={inputClass}
          >
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>
      </form>
    </Modal>
  )
}
