// frontend/src/components/settings/DeleteStaffModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { AlertTriangle } from 'lucide-react'
import { staffApi, type StaffMember } from '@/lib/api/staffApi'

const inputClass =
  'w-full h-9 px-3 rounded-[6px] bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-[#4A7FA5] transition-colors'
const ghostBtn =
  'h-9 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[13px] text-brand dark:text-[#EDEEF0] hover:opacity-80 transition-opacity'

interface Props {
  open: boolean
  onClose: () => void
  onDeleted: () => void
  member: StaffMember | null
}

export function DeleteStaffModal({ open, onClose, onDeleted, member }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [emailConfirmation, setEmailConfirmation] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) {
      setStep(1)
      setEmailConfirmation('')
      setDeleting(false)
      setDeleteError(null)
    }
  }, [open])

  if (!open || !member) return null

  const displayName = member.full_name || member.email

  async function handleDelete() {
    setDeleting(true)
    setDeleteError(null)
    try {
      await staffApi.deleteUser(member!.id)
      onDeleted()
      onClose()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } }; message?: string })
          ?.response?.data?.detail ?? 'Failed to delete team member.'
      setDeleteError(msg)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
    >
      <div className="absolute inset-0 bg-black/35" onClick={onClose} />

      <div className="relative z-10 w-full max-w-[480px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-[0.5px] border-surface-border dark:border-dark-border shadow-lg overflow-hidden">

        {/* Step 1 */}
        {step === 1 && (
          <>
            <div className="bg-[#FEE2E2] rounded-t-[10px] px-5 py-4 flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-[#991B1B] flex-shrink-0" />
              <span className="text-[14px] font-medium text-[#991B1B]">Delete Team Member</span>
            </div>
            <div className="px-5 py-4 flex flex-col gap-3">
              <ul className="flex flex-col gap-2">
                {[
                  'This staff member will immediately lose access to JAMM PX.',
                  'All tasks and engagements assigned to them will remain but will show as unassigned.',
                  'Their historical activity and behavioral data is preserved for firm intelligence.',
                  'This action cannot be undone.',
                ].map((line) => (
                  <li key={line} className="flex items-start gap-2 text-[13px] text-brand dark:text-[#EDEEF0]">
                    <span className="text-[#991B1B] mt-0.5 flex-shrink-0">•</span>
                    {line}
                  </li>
                ))}
              </ul>
              <div className="flex items-center justify-end gap-2 pt-2">
                <button onClick={onClose} className={ghostBtn}>Cancel</button>
                <button
                  onClick={() => setStep(2)}
                  className="h-9 px-3 rounded-[6px] bg-[#F59E0B] text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
                >
                  I understand, continue
                </button>
              </div>
            </div>
          </>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <>
            <div className="bg-[#FEE2E2] rounded-t-[10px] px-5 py-4 flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-[#991B1B] flex-shrink-0" />
              <span className="text-[14px] font-medium text-[#991B1B]">
                Confirm deletion of {displayName}
              </span>
            </div>
            <div className="px-5 py-4 flex flex-col gap-4">
              <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
                Type the staff member&apos;s email address to confirm deletion.
              </p>
              <input
                type="text"
                value={emailConfirmation}
                onChange={(e) => setEmailConfirmation(e.target.value)}
                placeholder={member.email}
                className={inputClass}
                autoFocus
              />
              <div className="flex items-center justify-end gap-2">
                <button onClick={() => setStep(1)} className={ghostBtn}>Back</button>
                <button
                  onClick={() => setStep(3)}
                  disabled={emailConfirmation !== member.email}
                  className="h-9 px-3 rounded-[6px] bg-[#DC2626] text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Continue
                </button>
              </div>
            </div>
          </>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <>
            <div className="bg-[#991B1B] rounded-t-[10px] px-5 py-4 flex items-center gap-3">
              <AlertTriangle className="h-6 w-6 text-white flex-shrink-0" />
              <span className="text-[14px] font-medium text-white">Delete Team Member</span>
            </div>
            <div className="px-5 py-4 flex flex-col gap-4">
              <p className="text-[13px] text-brand dark:text-[#EDEEF0]">
                You are about to permanently delete <strong>{displayName}</strong>. There is no undo.
              </p>
              {deleteError && (
                <p className="text-[12px] text-[#DC2626]">{deleteError}</p>
              )}
              <div className="flex items-center justify-end gap-2">
                <button onClick={onClose} className={ghostBtn}>Cancel</button>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="h-9 px-3 rounded-[6px] bg-[#991B1B] text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                >
                  {deleting ? 'Deleting...' : 'Delete Permanently'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
